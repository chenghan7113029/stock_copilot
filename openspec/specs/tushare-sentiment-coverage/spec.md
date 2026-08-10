# tushare-sentiment-coverage Specification

## Purpose
TBD - created by archiving change align-tushare-coverage. Update Purpose after archive.
## Requirements
### Requirement: Tushare 情绪分量替代
系统 SHALL 提供基于 Tushare 的市场情绪取数路径（新建 fetcher 或扩展现有），至少覆盖：两融汇总（`margin`，在积分允许时）以及基于全市场 `daily(trade_date)` 的涨跌停/涨跌家数**近似**聚合。当 AKShare 未启用时，`sync market` SHALL 仍可写入情绪快照；部分分量缺失时 MUST 在结果 `warnings` 中说明降级，MUST NOT 因缺少 AKShare 而强制 exit 1（硬门控移除可与阶段 C 一并验收，本阶段至少提供 Tushare 成功路径）。

#### Scenario: 无 AKShare 有 Tushare 可写快照
- **WHEN** 配置启用 tushare、未启用 akshare，运行 `sync market`
- **THEN** 情绪快照写入成功或带明确 missing 警告的部分成功，进程不因「必须 akshare」而失败

#### Scenario: 近似涨跌停不冒充精确名单
- **WHEN** 使用 daily 聚合近似涨跌停家数
- **THEN** 文档或 warnings 标明为近似，不声称等同 `limit_list_d` 精确列表

