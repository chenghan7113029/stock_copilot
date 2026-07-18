# cli-report-dual Specification

## Purpose
CLI `report dual`：严格离线输出红蓝对抗证据分桶（Level 0），供 Cursor Skill 消费。

## Requirements

### Requirement: CLI `report dual` 命令——严格离线输出证据分桶
系统 SHALL 提供 `python -m apps.cli report dual <code> [--json] [--output]`。命令 SHALL 严格离线（不发起任何网络请求），内部调用 `DualTrackAnalyzer.analyze_offline()` 与 `EvidenceBucketer`，输出证据分桶结果（含兜底内容）。命令 SHALL NOT 提供任何联网/LLM 相关 flag；互驳叙事的生成由 Cursor Skill（见 `cursor-skill-red-blue-confrontation` capability）在命令输出之外完成。命令内部 SHALL 复用 `run_report_tech`/`run_report_value` 已有的 analyzer 装配逻辑，不重新实现。

#### Scenario: 默认输出证据分桶
- **WHEN** 运行 `report dual 600519`（本地已有快照）
- **THEN** SHALL 输出 bull/bear 证据列表（含兜底条目，若触发），不发起任何网络请求

#### Scenario: 无本地快照时明确报错
- **WHEN** 运行 `report dual <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0

#### Scenario: --json 与 --output 行为对齐既有 report 命令
- **WHEN** 运行 `report dual 600519 --json` 或 `--output <path>`
- **THEN** 行为 SHALL 与 `report tech`/`report value` 的对应 flag 语义一致（JSON 序列化 / 写入文件而非打印到 stdout）；`--json` 输出 SHALL 包含 `bull_evidence`/`bear_evidence` 字段，供 Cursor Skill 解析消费
