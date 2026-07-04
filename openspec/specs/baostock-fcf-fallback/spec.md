## Purpose

Baostock FCF 三级推导链（operCashTTM → CFOToOR×revenue → net_income×fcf_rate）。

## Requirements

### Requirement: FCF 三级推导优先链
`BaostockFetcher` 的现金流处理 SHALL 按以下优先顺序填充 `StockData.fcf`，首个成功项即停止。

优先级：
1. `operCashTTM`（有值且 > 0）
2. `CFOToOR × revenue_ttm`（`CFOToOR` 来自 `query_cash_flow_data`，`revenue_ttm` 用年化值）
3. `net_income × fcf_rate`（`fcf_rate` 来自 `config.value_analysis.fcf_rate`，默认 0.85）

#### Scenario: operCashTTM 有值
- **WHEN** `query_cash_flow_data` 返回正的 `operCashTTM`
- **THEN** `fcf = operCashTTM`，无警告写入

#### Scenario: operCashTTM 为 None，CFOToOR 有值
- **WHEN** `operCashTTM` 为 None 且 `CFOToOR` 有效且 `revenue` 可获取
- **THEN** `fcf = CFOToOR × revenue_ttm`，同时写入警告：`"FCF derived from CFOToOR × revenue (operCashTTM unavailable)"`

#### Scenario: 前两级均失败，net_income 可用
- **WHEN** `operCashTTM` 为 None 且 `CFOToOR` 不可用或 `revenue` 不可用
- **THEN** `fcf = net_income × fcf_rate`，同时写入警告：`"FCF estimated from net_income × {fcf_rate} (config fallback, low confidence)"`

#### Scenario: fcf_rate 可通过 config 覆盖
- **WHEN** `config.value_analysis.fcf_rate` 被设置为具体值
- **THEN** 方案 3 使用该配置值而非默认的 0.85
