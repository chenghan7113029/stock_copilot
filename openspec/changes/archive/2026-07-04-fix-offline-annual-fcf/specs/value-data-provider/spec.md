## MODIFIED Requirements

### Requirement: 离线快照按来源取最新 fetched_at
`get_stock_data_offline()` 在同 `source` 存在多条 `report_period` 快照时，SHALL 对字段类型分层选源：
- **行情字段**（`current_price`、`shares_outstanding`、`market_cap`、`pe_ratio`、`pb_ratio`、`data_timestamp` 等）：选取该 source 下 `fetched_at` 最新的一条快照。
- **财报字段**（`FINANCIAL_STATEMENT_FIELDS`：`revenue`、`fcf`、`capex`、`net_debt`、`ebit`、`depreciation`、`total_assets`、`total_liabilities`、`bvps`、`roic`、`net_income`）：优先选取 `report_period` 以 `1231` 结尾的最新年报快照；若无年报快照，fallback 到 `fetched_at` 最新快照。

合并顺序：先合并行情快照的非财报字段，再合并财报快照的财报字段（财报字段 SHALL 使用 `override_field` 以确保覆盖）。

#### Scenario: 同 source 多 report_period — 行情取最新、FCF 取年报
- **WHEN** `tushare` 同时存在 `report_period=20260331`（fetched_at 较新，fcf=263亿）与 `report_period=20251231`（fcf=584亿）
- **THEN** 离线合并 SHALL 使用 20260331 的 `current_price`（若更新），但 `fcf=584亿` 来自 20251231 年报

#### Scenario: 同 source 仅行情快照与年报快照
- **WHEN** `tushare` 存在 `report_period=20260628`（仅行情）与 `report_period=20251231`（含完整财报）
- **THEN** 离线合并 SHALL 使用 20260628 的行情字段与 20251231 的财报字段，`revenue`/`total_assets`/`fcf` 非空

#### Scenario: 无年报快照时 fallback
- **WHEN** 某 source 仅有季报快照（无 `1231` report_period）
- **THEN** 财报字段 fallback 到 `fetched_at` 最新快照，系统不报错
