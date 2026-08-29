## Why

`product-overview.md` §5.2 / §8.2 将红蓝对抗（PO-03）列为 P0 决策护航机制，并要求「用户须声明采纳方及理由」可持久化备查。2026-07-18 的 `add-red-blue-confrontation` 以 **Cursor Skill + 离线证据分桶** 交付 V1，并**冻结**应用内置 LLM API 路径。

当前主使用场景已转向 **纯 CLI + LLM API**（Owner 已配置 API）。Skill 无法脚本化、无法缓存、无法与飞书推送/复盘链路集成；且 Skill 叙事**无代码级 grounded 校验**。竞品参考（`docs/mrd/competitive-reference.md` §4.1）与 explore 结论一致：应在保留 Level 0 确定性分桶的前提下，用 `narrate()` 提供产品级互驳叙事。

## What Changes

- 扩展 `report dual --json`：为 `bull_evidence[]` / `bear_evidence[]` 输出**稳定 1-based 序号**（`index` 字段或 `[n]` 前缀），供 declare / persona 引用
- 新增 CLI `report confront <code> [--narrate] [--json] [--output]`：
  - Level 0：复用 `DualTrackAnalyzer.analyze_offline()` + `EvidenceBucketer`（严格离线，不联网）
  - Level 1（`--narrate`）：调用既有 `narrate()` + `check_grounded()`，生成结构化互驳 JSON（多方/空方/互驳），失败时降级为仅证据分桶 + 明确警告
  - 成功 narrate 时写入 `ConfrontationRecord`（仅 narrative + evidence 快照，declare 字段留空，由 `add-confrontation-declaration` 填充）
- 新增 `ConfrontationNarrator`（`service/guard/`）：封装 evidence 打包、JSON Schema、grounded 重试与 `LLMNarrateCache` 幂等
- Skill 保留为 **dev/fallback**，产品主路径文档标注为 API

**不包含：**
- 用户结构化 declare（`add-confrontation-declaration`）
- Persona 压力测试（`add-confrontation-persona-stress-test`）
- 编排式 `decision audit` 单命令（保持命令分散，仅 ID 关联）
- 修改 `SignalFusion` / 自动交易信号

## Capabilities

### New Capabilities
- `confrontation-narrate-api`：`ConfrontationNarrator`、互驳 JSON Schema、grounded 校验与缓存键
- `cli-report-confront`：`report confront` 子命令与 formatter

### Modified Capabilities
- `cli-report-dual`：`--json` 输出含 evidence 序号，与 confront 共用同一编号规则
- `red-blue-confrontation`：证据分桶结果增加序号契约（确定性层）

## Impact

- **新增**：`src/service/guard/confrontation_narrator.py`、`src/service/guard/models/confrontation.py`、`src/dao/confrontation_repo.py`、`ConfrontationRecord` ORM（与 declaration change 共享表结构时仅 narrative 字段本 change 写入）
- **修改**：`src/apps/cli.py`、`formatters.py`、`evidence_bucketer.py` 或 dual JSON 序列化层
- **依赖**：消费既有 `llm-narrative-core`（解冻 PO-03 API 路径）
- **文档**：`roadmap-todo.md` PO-03 状态、`competitive-reference.md` 决策护航 ROI
