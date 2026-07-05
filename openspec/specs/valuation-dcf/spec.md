# valuation-dcf Specification

## Purpose
TBD - created by archiving change add-valuation-methods-full. Update Purpose after archive.
## Requirements
### Requirement: DCF 三阶段自由现金流折现
系统 SHALL 实现 `DCF` 方法，使用 WACC 折现三阶段 FCF：
- 第 1–5 年：增长率 `growth_rate_1_5`（默认 5%）
- 第 6–10 年：增长率 `growth_rate_6_10`（默认 3%）
- 终值：Gordon 增长 `terminal_growth`（默认 2%）
FCF 基数取自 `StockData.fcf`；缺失时尝试 `operating_cash_flow - abs(capex)` 推导。

#### Scenario: 正常 DCF 计算
- **WHEN** `StockData.fcf > 0`、shares_outstanding、current_price 齐全，WACC 可计算
- **THEN** `fair_value > 0`，与 `ref/valueinvest.DCF` 同输入偏差 ≤ ±0.1%

#### Scenario: fcf 为 None 且无法推导时 missing_fields
- **WHEN** `StockData.fcf = None` 且 operating_cash_flow/capex 均缺失
- **THEN** `missing_fields` 含 `fcf`，`error` 非空

### Requirement: ReverseDCF 反推市场隐含增长率
系统 SHALL 实现 `ReverseDCF`，从 `current_price` 反推使 DCF 公允价等于现价的隐含永续增长率（或等效参数），结果写入 `details.implied_growth_rate`。

#### Scenario: 正常反推隐含增长率
- **WHEN** 与 DCF 相同输入且 current_price 在 DCF 公允价附近
- **THEN** `details.implied_growth_rate` 为有限正数，与 ref ±0.1% 相对误差

#### Scenario: 无解时返回错误
- **WHEN** current_price 极端偏离导致二分法不收敛
- **THEN** `error` 非空，不抛异常

### Requirement: DCF 折现率使用 AssumptionProvider.get_discount_rate（含 β-CAPM）
`DCF.calculate(stock)` 使用的折现率 SHALL 来自 `AssumptionProvider.get_discount_rate(stock)`，该方法在 β 配置可用时使用 CAPM 推算（`china_10y_yield + beta × equity_risk_premium`），而不再 fallback 到全局固定 10%。当 `stock.proto="value_growth"` 且配置 `beta_by_proto.value_growth=0.6` 时，折现率 SHALL 为 5.4%（而非 10%）。

#### Scenario: value_growth 原型 DCF 使用 CAPM 折现率
- **WHEN** stock.proto="value_growth"，beta_by_proto.value_growth=0.6，china_10y_yield=1.8，equity_risk_premium=6.0
- **THEN** DCF 使用折现率 5.4，ValuationResult.details["discount_rate"] = 5.4

#### Scenario: proto 未知时 DCF fallback 到全局 discount_rate
- **WHEN** stock.proto="" 且 app.yaml discount_rate=10.0
- **THEN** DCF 使用折现率 10.0（与修复前行为一致）

