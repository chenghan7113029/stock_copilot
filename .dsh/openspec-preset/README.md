# OpenSpec preset for DSH

A user-authored **agent preset** for the DeepSeek Harness that adds OpenSpec
slash commands (`/opsx-propose`, `/opsx-apply`, `/opsx-archive`,
`/opsx-explore`) to the standard coding agent.

## What is here

- `openspec-commands.mjs` — the Cordis plugin that registers the four commands.
  Each command queues a model-visible message that drives the `openspec` CLI
  workflow (`openspec new change` / `status` / `instructions` / `list`).
- `preset.yml` — display metadata shown in the preset picker.
- The preset's `agent.cordis.yml` is **not** stored here: it is a copy of the
  shipped `standard` composition plus one extra row (see below), because the
  shipped file belongs to the deployment and must not be edited in place.

## Installed layout

The installed preset lives at:

```
%DSH_HOME%\.agent-presets\openspec\
  agent.cordis.yml        # copy of standard + the command-openspec row
  openspec-commands.mjs   # copied from this folder
  preset.yml              # copied from this folder
```

## Install / reinstall

From a shell, with `<shipped>` =
`%APPDATA%\npm\node_modules\@deepseek-ai\dsh\node_modules\@deepseek-ai\dsh-agent-presets\presets\standard`
and `<here>` = this folder:

```powershell
$src  = '<shipped>'
$dest = "$env:DSH_HOME\.agent-presets\openspec"
$here = '<here>'
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item "$src\agent.cordis.yml"  "$dest\agent.cordis.yml"
Copy-Item "$here\openspec-commands.mjs" "$dest\openspec-commands.mjs"
Copy-Item "$here\preset.yml"        "$dest\preset.yml"
Add-Content -Path "$dest\agent.cordis.yml" -Encoding utf8 -Value @'

# ── openspec commands ────────────────────────────────────────────────────────
# Registers /opsx-propose, /opsx-apply, /opsx-archive, /opsx-explore. Consumes
# the host `commands` registry only and publishes no service, so it sits loose
# like command-goal / plan-mode / command-compact.
- id: command-openspec
  name: './openspec-commands.mjs'
'@
```

## Use it

1. Start a **new session** and select the **"OpenSpec (standard + openspec commands)"**
   preset (the commands are registered per-preset, so they appear only on
   sessions composed with this preset).
2. Type `/` in the composer to see the four `opsx-*` commands, e.g.
   `/opsx-propose add value bank fallback`.
