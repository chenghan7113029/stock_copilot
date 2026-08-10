# cli-report-dashboard Specification

## Purpose
TBD - created by archiving change add-stock-dashboard. Update Purpose after archive.
## Requirements
### Requirement: CLI `report dashboard` 命令——严格离线的单页汇总
系统 SHALL 提供 `python -m apps.cli report dashboard <code> [--json] [--output] [--quiet]`。命令 SHALL 严格离线（不发起任何网络请求），内部调用 `DashboardBuilder.build(code)`，输出结果 SHALL 与 `report tech`/`report value`/`report dual` 的 `--json`/`--output`/`--quiet` 行为语义一致。

#### Scenario: 默认输出单页汇总
- **WHEN** 运行 `report dashboard 600519`（本地已有价值快照与 K 线缓存）
- **THEN** SHALL 输出含价值面、技术面、情绪面（占位）、Checklist（占位）、综合摘要五个分区的文本，不发起任何网络请求

#### Scenario: 无本地数据时明确报错
- **WHEN** 运行 `report dashboard <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0

#### Scenario: --json 输出结构化字段
- **WHEN** 运行 `report dashboard 600519 --json`
- **THEN** SHALL 输出合法 JSON，字段覆盖 `value_section`/`tech_section`/`sentiment_section`/`checklist_section`/`combined_summary`

