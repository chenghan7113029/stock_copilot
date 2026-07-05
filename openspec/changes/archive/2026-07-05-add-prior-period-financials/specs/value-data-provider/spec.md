## MODIFIED Requirements

### Requirement: prior_* 字段从始终 None 变为可由 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `prior_*` 字段合并到 `StockData` 对应属性。这些字段不参与 `_derive_*` 推导；直接来自 Tushare API。

#### Scenario: Tushare 提供 prior_roa 后字段非空
- **WHEN** sync 600519，Tushare 成功返回 prior_roa
- **THEN** `StockData.prior_roa is not None`，`field_sources["prior_roa"] = "tushare"`

#### Scenario: 仅 Baostock 时 prior_* 为 None
- **WHEN** Tushare 未启用
- **THEN** 所有 `prior_*` 字段为 None，Piotroski/Beneish 部分指标退化为 Not Applicable
