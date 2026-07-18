## Why

`product-overview.md` §6 将「红蓝军对抗」列为 P0 决策护航机制，用于对抗确认偏差：「多空角色基于同一公开信息各出报告并互相攻击」。当前 `DualTrackAnalyzer` 已产出丰富的确定性证据（价值面各方法 assessment/warnings、技术面 signal_reasons/risk_factors），但没有机制把这些证据组织成对立的多空论述，也没有对外 CLI 入口。

**路线调整**：原方案计划依赖 `add-llm-narrative-core`（应用内置 LLM API）生成 Level 1 互驳叙事。经讨论，当前主要使用场景是「本人在 Cursor 中分析决策」，引入独立 LLM API（额外计费、Key 管理、grounded 校验工程量）在此阶段收益不高。改为：确定性部分（证据分桶）仍在代码里完成并可独立交付价值；叙事互驳部分改由 **Cursor Skill** 承接，复用 Cursor 会话本身的模型能力，零额外 API 成本。`add-llm-narrative-core` 已实现并合入主干，作为已验证但**暂不消费**的能力冻结，留给未来 Web + 独立 LLM API 阶段使用。

## What Changes

- 新增 `EvidenceBucketer`（纯规则，零 LLM）：从 `DualTrackReport` 中按既有规则将 method assessment/warnings/value_trap/signal_reasons/risk_factors 分类为 `bull_evidence[]` / `bear_evidence[]`
- 新增兜底规则：某一方证据条数过少（< 2 条）时，追加「对方核心假设脆弱性」条目（如 growth_rate 假设、原型方法适用局限、行业周期位置），保证对抗双方始终有内容
- 新增 `DualTrackAnalyzer.analyze_offline(code)`：修复现有 `analyze()` 内部调用联网版 `ValueAnalyzer.analyze()` 的问题，新增离线版本（内部转调 `ValueAnalyzer.analyze_offline()` + `TechAnalyzer.analyze(offline=True)`）
- 新增 CLI 入口 `python -m apps.cli report dual <code> [--json] [--output]`：严格离线，输出证据分桶结果（含兜底内容），格式与 `report tech`/`report value` 一致；`--json` 供 Skill 消费
- 新增 Cursor Skill（`.cursor/skills/red-blue-confrontation/SKILL.md`）：读取 `report dual --json` 的证据分桶输出，在当前 Cursor 会话中生成 Level 1 互相反驳叙事（多方论述 + 空方论述 + 互相反驳），反驳内容要求锚定证据条目、禁止编造证据外的新数字；输出到对话中，MAY 另存为 `reports/<code>_confrontation.md`

**不包含（明确推迟到 Web + LLM API 阶段）**：
- 不新增 `ConfrontationGenerator` / 应用内置 LLM 调用（复用已冻结的 `add-llm-narrative-core` 时再启用）
- 不新增 `ConfrontationRecord` DAO 持久化（Skill 产出的叙事当前无持久化消费方，避免过度设计；用户"声明拒绝哪方及理由"依赖未来 Web 界面，一并推迟）
- 不实现代码层的 grounded 数值锚定校验（Skill 模式下由 prompt 约束 + 人工核对原始证据列表承担，已知局限见 design.md）

## Capabilities

### New Capabilities
- `red-blue-confrontation`：证据分桶规则、兜底假设脆弱性规则（纯规则，零 LLM）
- `cli-report-dual`：`report dual` 子命令（严格离线，输出证据分桶结果）
- `cursor-skill-red-blue-confrontation`：Skill 的输入/输出契约（读取证据 JSON、生成互驳叙事的约束与格式）

### Modified Capabilities
- `dual-track-analyzer`：新增 `analyze_offline()` 方法（不改变现有 `analyze()` 行为，向后兼容追加）

## Impact

- **新增文件**：
  - `src/service/dual_track/evidence_bucketer.py`
  - `src/apps/cli.py`：新增 `report dual` 子命令与 `run_report_dual()`
  - `src/apps/formatters.py`：新增 `format_dual_report()`
  - `.cursor/skills/red-blue-confrontation/SKILL.md`
  - `test/service/dual_track/test_evidence_bucketer.py`
  - `test/apps/test_cli_report_dual.py`
- **修改文件**：
  - `src/service/dual_track/analyzer.py`：新增 `analyze_offline()`
- **依赖**：无（不再依赖 `add-llm-narrative-core`；该 change 保持冻结状态）
- **文档**：`docs/mrd/product-overview.md` §6/§7（PO-03 状态更新为「V1 Skill 版已实现，Web+API 版待建」）、`docs/mrd/roadmap-todo.md`（新增变更记录）
