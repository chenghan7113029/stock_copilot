# valuation-ddm Specification

## Purpose
TBD - created by archiving change add-valuation-methods-core. Update Purpose after archive.
## Requirements
### Requirement: DDM（Gordon Growth Model）计算股息折现价值
系统 SHALL 实现 `DDM`（Dividend Discount Model / Gordon Growth Model）估值方法，
公式：`P = D₁ / (r - g) = D₀ × (1 + g) / (r - g)`，
其中 r = `cost_of_capital`（来自 `AssumptionProvider`），g = `dividend_growth_rate`。
`g ≥ r` 时 SHALL 返回错误（Gordon 模型数学不收敛）。
`dividend_per_share ≤ 0` 时 SHALL 返回 `missing_fields = ["dividend_per_share"]`。
股息增长率超过 `MAX_GROWTH_RATE`（默认 12%）时在 `warnings` 中提示可持续性风险。

#### Scenario: 正常 Gordon 成长计算
- **WHEN** `StockData.dividend_per_share = 1.2`, `cost_of_capital = 10.0`, 使用 `dividend_growth_rate = 4.0`
- **THEN** `fair_value = 1.2 × 1.04 / (0.10 - 0.04) = 20.8`，与 ref/valueinvest.DDM 偏差 ≤ ±0.1%

#### Scenario: g ≥ r 时返回错误
- **WHEN** `dividend_growth_rate = 12.0`, `cost_of_capital = 10.0`
- **THEN** `error` 非空，提示增长率须小于折现率，`fair_value = 0`

#### Scenario: dividend_per_share 为 None 时 missing_fields
- **WHEN** `StockData.dividend_per_share = None`
- **THEN** `missing_fields = ["dividend_per_share"]`，不抛异常

#### Scenario: 高 payout_ratio 触发 warning
- **WHEN** `StockData.payout_ratio = 95.0`（派息率 95%）
- **THEN** `warnings` 包含 payout ratio 过高的提示

### Requirement: TwoStageDDM 两阶段股息折现
系统 SHALL 实现 `TwoStageDDM` 估值方法，
第一阶段（`stage1_years` 期，默认 5）以 `growth_stage1`（默认 5%）增长，
第二阶段以 `growth_stage2`（默认 2%，永续）增长。
公式：`V = Σ[t=1..n] D₀×(1+g₁)^t / (1+r)^t  +  D_n×(1+g₂) / (r-g₂) / (1+r)^n`。
所有增长率和折现率均可通过 `__init__` 参数覆盖。

#### Scenario: 两阶段正常计算
- **WHEN** `StockData.dividend_per_share = 0.8`, `cost_of_capital = 9.0`，g₁=6%, n=5, g₂=3%
- **THEN** `fair_value > 0`，第一阶段现值 + 终值现值，与 ref/valueinvest.TwoStageDDM 偏差 ≤ ±0.1%

#### Scenario: g₂ ≥ r 时返回错误
- **WHEN** `growth_stage2 = 10.0`, `cost_of_capital = 9.0`
- **THEN** `error` 非空，`fair_value = 0`

#### Scenario: 第二阶段增长率低于第一阶段（正常过渡场景）
- **WHEN** `growth_stage1 = 8.0`, `growth_stage2 = 2.0`, `cost_of_capital = 10.0`
- **THEN** `fair_value > 0`，`applicability = "Applicable"`，无错误

