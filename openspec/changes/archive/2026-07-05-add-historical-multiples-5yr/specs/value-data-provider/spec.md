## ADDED Requirements

### Requirement: historical_pb 字段来源从 None 变为 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `historical_pb` 合并到 `StockData.historical_pb`，优先级高于 Baostock（Baostock 无法提供 PB 序列）。

#### Scenario: Tushare 提供 historical_pb 后字段不再为 None
- **WHEN** Tushare 启用且 `daily_basic` 成功拉取 5 年 PB 序列
- **THEN** `StockData.historical_pb` 不为 None，`field_sources["historical_pb"] = "tushare"`

#### Scenario: Tushare 不可用时 historical_pb 为 None
- **WHEN** 仅 Baostock 启用
- **THEN** `StockData.historical_pb` 保持 None，不报错，pb_relative = Not Applicable
