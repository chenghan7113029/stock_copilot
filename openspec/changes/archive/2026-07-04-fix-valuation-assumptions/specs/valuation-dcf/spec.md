## ADDED Requirements

### Requirement: DCF 折现率使用 AssumptionProvider.get_discount_rate（含 β-CAPM）
`DCF.calculate(stock)` 使用的折现率 SHALL 来自 `AssumptionProvider.get_discount_rate(stock)`，该方法在 β 配置可用时使用 CAPM 推算（`china_10y_yield + beta × equity_risk_premium`），而不再 fallback 到全局固定 10%。当 `stock.proto="value_growth"` 且配置 `beta_by_proto.value_growth=0.6` 时，折现率 SHALL 为 5.4%（而非 10%）。

#### Scenario: value_growth 原型 DCF 使用 CAPM 折现率
- **WHEN** stock.proto="value_growth"，beta_by_proto.value_growth=0.6，china_10y_yield=1.8，equity_risk_premium=6.0
- **THEN** DCF 使用折现率 5.4，ValuationResult.details["discount_rate"] = 5.4

#### Scenario: proto 未知时 DCF fallback 到全局 discount_rate
- **WHEN** stock.proto="" 且 app.yaml discount_rate=10.0
- **THEN** DCF 使用折现率 10.0（与修复前行为一致）
