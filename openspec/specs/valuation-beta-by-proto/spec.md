# valuation-beta-by-proto Specification

## Purpose
按股票估值原型配置默认 β，通过 CAPM 推算折现率，替代全局固定 discount_rate。

## Requirements
### Requirement: β 按原型配置并用于 CAPM 折现率推算
`AssumptionProvider` SHALL 支持从 `app.yaml` 的 `value_analysis.beta_by_proto` 读取各原型对应的 β 值。当 `get_discount_rate(stock)` 被调用且 `stock.proto` 匹配到一个 β 配置时，SHALL 使用 CAPM 公式推算折现率：
`discount_rate = china_10y_yield + beta × equity_risk_premium`
否则 fallback 到 `value_analysis.discount_rate`（默认 10.0%）。

#### Scenario: value_growth 原型使用 CAPM 折现率
- **WHEN** stock.proto="value_growth"，配置 beta_by_proto.value_growth=0.6，china_10y_yield=1.8，equity_risk_premium=6.0
- **THEN** get_discount_rate(stock) 返回 1.8 + 0.6 × 6.0 = 5.4

#### Scenario: 未知原型 fallback 到全局默认
- **WHEN** stock.proto="" 或 proto 不在 beta_by_proto 配置中
- **THEN** get_discount_rate(stock) 返回 value_analysis.discount_rate（默认 10.0）

#### Scenario: 配置缺失时系统正常工作
- **WHEN** app.yaml 中 value_analysis 未包含 beta_by_proto 键
- **THEN** AssumptionProvider 不报错，get_discount_rate 使用全局 discount_rate 默认值

### Requirement: beta_by_proto 默认值覆盖三个主要原型
`AssumptionDefaults` SHALL 为三个主要原型提供合理 β 默认值，作为未配置时的代码级 fallback：
- `value_growth`: 0.6（消费成长型，低波动）
- `high_dividend`: 0.5（防御型，稳定分红）
- `bank`: 0.9（银行，高杠杆略高风险）

#### Scenario: 代码级默认值生效
- **WHEN** AssumptionProvider 未传入任何 config 且 stock.proto="value_growth"
- **THEN** get_discount_rate(stock) 返回 1.8 + 0.6 × 6.0 = 5.4（使用代码级默认）
