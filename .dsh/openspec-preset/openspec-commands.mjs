// OpenSpec slash commands for the DeepSeek Harness.
//
// Registers four DSH slash commands that map onto the OpenSpec workflow:
//   /opsx-propose   — create a change + proposal/design/specs/tasks artifacts
//   /opsx-apply     — implement the tasks of a change
//   /opsx-archive   — archive a completed change
//   /opsx-explore   — enter explore (thinking) mode
//
// Each handler queues one model-visible user message (via agent.followup) that
// tells the model to run the matching workflow against the `openspec` CLI and
// the `openspec/` tree in the session workspace. The command's own result text
// stays in the UI — the same pattern dsh-plan-mode and dsh-command-goal use.
//
// This plugin only CONSUMES the host `commands` registry; it publishes no
// service, so it sits loose in the agent-preset composition (like command-goal,
// plan-mode, and command-compact in the shipped `standard` preset).

import { randomUUID } from 'node:crypto';

const name = 'openspec-commands';
const inject = ['commands'];

function userMessage(text) {
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'user' },
  };
}

const HARD_GATE =
  'Project hard gate (stock_copilot, from openspec/config.yaml): checkbox completion does NOT equal change/apply/archive completion. Before claiming implementation or spec complete, or before suggesting archive, actually run the relevant tests and confirm they pass, and keep the command output you can point to. Do not default-pass on "pre-existing unrelated failures"; only the Owner may explicitly waive a named failure (record it).';

function proposePrompt(input) {
  const topic = input.trim();
  return [
    'Execute the OpenSpec propose workflow: create a new change and generate all its artifacts in one step.',
    topic === ''
      ? 'No change name or description was supplied. Ask the user (ask_user_question, open-ended) what they want to build or fix, derive a kebab-case name, then continue.'
      : `User request: ${topic}`,
    '',
    'Steps:',
    '1. Create the change directory:  openspec new change "<name>"',
    '2. Get the artifact build order:  openspec status --change "<name>" --json  (read applyRequires and artifacts).',
    '3. For each artifact that is ready, in dependency order:  openspec instructions <artifact-id> --change "<name>" --json',
    '   Read any completed dependency artifacts, then write the artifact file using the returned template. Apply context and rules as constraints but do not copy them into the file.',
    '4. Re-run  openspec status --change "<name>" --json  after each artifact; stop when every applyRequires artifact is done.',
    '5. Show the final status with  openspec status --change "<name>" .',
    '',
    HARD_GATE,
    '',
    'Guardrails: create all artifacts required for implementation; read dependencies before writing; if a change of that name already exists, ask whether to continue it or create a new one; prefer momentum but ask when context is critically unclear.'
  ].join('\n');
}

function applyPrompt(input) {
  const topic = input.trim();
  return [
    'Execute the OpenSpec apply workflow: implement the tasks of an OpenSpec change.',
    topic === ''
      ? 'No change name supplied. Infer it from conversation context if unambiguous, auto-select if only one active change exists, otherwise run  openspec list --json  and ask the user to choose.'
      : `Change to apply: ${topic}`,
    '',
    'Steps:',
    '1. Announce "Using change: <name>" and how to override.',
    '2. Run  openspec status --change "<name>" --json  to learn the schema and which artifact holds the tasks.',
    '3. Run  openspec instructions apply --change "<name>" --json  for contextFiles, progress, and the task list.',
    '4. Read every file listed under contextFiles.',
    '5. Implement pending tasks one by one, keeping changes minimal. After each task, mark it done in tasks.md:  - [ ]  ->  - [x] .',
    '6. Pause (and ask) if a task is unclear, a design issue surfaces, an error blocks you, or the user interrupts.',
    '',
    HARD_GATE,
    '',
    'Guardrails: read context before starting; do not mark a verification task complete while its tests fail; never claim complete or suggest archive while required tests fail unless the Owner explicitly waives a named failure.'
  ].join('\n');
}

function archivePrompt(input) {
  const topic = input.trim();
  return [
    'Execute the OpenSpec archive workflow: archive a completed change.',
    topic === ''
      ? 'No change name supplied. Run  openspec list --json  and ask the user to select; do not guess.'
      : `Change to archive: ${topic}`,
    '',
    'Steps:',
    '1. Run  openspec status --change "<name>" --json  and warn about any artifacts not done; confirm with the user before continuing.',
    '2. Read tasks.md and warn about any incomplete  - [ ]  tasks; confirm with the user.',
    '3. Run the verification gate: the change\'s new/changed tests plus  pytest -q -m "not network"  (and any extra gates in tasks). If tests fail, do NOT archive by default; pause and ask the Owner to fix or explicitly waive named failures.',
    '4. Assess delta specs under openspec/changes/<name>/specs/ against openspec/specs/<capability>/spec.md and show a combined summary before prompting (sync now vs archive without syncing).',
    '5. Archive: create openspec/changes/archive if needed, then move the directory to openspec/changes/archive/YYYY-MM-DD-<name> . Fail if the target already exists.',
    '6. Show a summary: change name, schema, archive location, spec-sync status, and any warnings.',
    '',
    HARD_GATE,
    '',
    'Guardrails: always prompt for selection when no name is given; preserve .openspec.yaml when moving; do not block on incomplete-artifact/task warnings alone (inform and confirm), but DO block default archive when verification fails unless the Owner explicitly waives.'
  ].join('\n');
}

function explorePrompt(input) {
  const topic = input.trim();
  return [
    'Enter OpenSpec explore mode: think through ideas, investigate problems, clarify requirements. This is a stance, not a workflow with fixed steps.',
    '',
    'Do NOT implement: you may read files, search code, and investigate, but never write application code. Creating OpenSpec artifacts (proposals, designs, specs) is allowed if the user asks.',
    '',
    'Stance: curious, not prescriptive; surface several threads and let the user follow; visualize freely with ASCII diagrams; adapt and pivot; be patient; ground discussion in the actual codebase.',
    '',
    'OpenSpec awareness: run  openspec list --json  to see active changes; if the user names a change, read its artifacts. When decisions are made, offer to capture them into proposal.md / design.md / specs / tasks.md, but let the user decide — do not auto-capture.',
    topic === '' ? '' : `User wants to explore: ${topic}`
  ].join('\n');
}

function apply(ctx) {
  const definitions = [
    ['opsx-propose', 'Create a new OpenSpec change with proposal, design, specs and tasks', '<change-name-or-description>', proposePrompt],
    ['opsx-apply', 'Implement the tasks of an OpenSpec change', '[change-name]', applyPrompt],
    ['opsx-archive', 'Archive a completed OpenSpec change', '[change-name]', archivePrompt],
    ['opsx-explore', 'Enter OpenSpec explore (thinking) mode', '[topic]', explorePrompt]
  ];

  for (const [commandName, description, hint, build] of definitions) {
    ctx.commands.register({
      name: commandName,
      description,
      input: { hint },
      handler: ({ agent, rawInput }) => {
        agent.followup(userMessage(build(rawInput)));
        return { kind: 'success', text: `Starting /${commandName} …` };
      }
    });
  }
}

export { name, inject, apply };
