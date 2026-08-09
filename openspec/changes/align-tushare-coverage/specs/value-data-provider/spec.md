## MODIFIED Requirements

### Requirement: Baostock 不产出低可信财报字段
`BaostockFetcher` 在 fundamentals / `fetch_all` 结果中 MUST NOT 写入下列字段的有效数值（可省略键或显式 missing）：`revenue`、`fcf`、`capex`、`net_debt`、`ebit`、`depreciation`、`total_assets`、`total_liabilities`、`bvps`、`roic`、`net_income`（与代码中 `FINANCIAL_STATEMENT_FIELDS` 保持同步）。在 `tushare` priority 高于 `baostock` 的配置下，这些字段 SHALL 由 Tushare（若提供）主导。

#### Scenario: Baostock 输出不含财报特例字段
- **WHEN** 仅解析 Baostock `FetchResult.data`
- **THEN** 上述字段集合不出现有效 float 值

#### Scenario: tushare 优先时行业等来自 tushare
- **WHEN** 配置 tushare(1)+baostock(2) 且 Tushare 提供 `industry`
- **THEN** 合并后 `field_sources`（或等价元数据）显示 `industry` 来自 tushare
