## ADDED Requirements

### Requirement: PBValuation 用 ROE/COE/g 推导合理 PB 倍数
系统 SHALL 实现 `PBValuation` 估值方法，
公式：`合理 P/B = (ROE - g) / (COE - g)`，`公允价 = BVPS × 合理 P/B`，
其中 g（可持续增长率）= `ROE × (1 - payout_ratio)`，COE（股权成本）来自 `AssumptionProvider`
或 `__init__` 覆盖（默认 10%）。`ROE ≤ COE` 时 SHALL 返回 `applicability="Not Applicable"`（无经济价值创造）。

#### Scenario: 正常银行 PB 计算
- **WHEN** `StockData.roe = 12.0`, `bvps = 8.0`, `current_price = 5.0`, `payout_ratio = 0.4`，COE=10%
- **THEN** `g = 12% × 0.6 = 7.2%`，`fair_pb = (12-7.2)/(10-7.2) ≈ 1.714`，
  `fair_value ≈ 8.0 × 1.714 ≈ 13.71`，与 ref/valueinvest.PBValuation 偏差 ≤ ±0.1%

#### Scenario: ROE ≤ COE 时不适用
- **WHEN** `StockData.roe = 8.0`, COE=10%
- **THEN** `applicability = "Not Applicable"`，`error` 含 "ROE" 和 "COE" 说明

#### Scenario: bvps 为 None 时 missing_fields
- **WHEN** `StockData.bvps = None`
- **THEN** `missing_fields = ["bvps"]`，`error` 非空，不抛异常

### Requirement: ResidualIncome 剩余收益模型定价银行股
系统 SHALL 实现 `ResidualIncome` 估值方法（Residual Income Model），公式：

```
V = BVPS₀ + Σ[t=1..n] BVPS_{t-1} × (ROE - COE) / (1 + COE)^t
  + 终值残差 / (COE - g_terminal) / (1 + COE)^n
```

其中 n=10（可配置），`terminal_roe`（终值 ROE，默认 8.0%）、
`payout_ratio`（默认 0.6）、`cost_of_equity`（默认 10.0%）均可配置。
每期 `book_value` 通过 `book_value × (1 + roe × retention_ratio)` 递推。

#### Scenario: 正常剩余收益计算
- **WHEN** `StockData.bvps = 10.0`, `roe = 15.0`, `current_price = 12.0`，COE=10%，years=10，terminal_roe=8%，payout=0.6
- **THEN** `fair_value > 10.0`（ROE > COE，应有溢价），与 ref/valueinvest.ResidualIncome 偏差 ≤ ±0.1%

#### Scenario: ROE 低于 COE 时产生折价
- **WHEN** `StockData.bvps = 10.0`, `roe = 6.0`，COE=10%
- **THEN** `fair_value < 10.0`（低于账面值），`assessment` 为 "Undervalued" 或反映折价

#### Scenario: roe 为 None 时 missing_fields
- **WHEN** `StockData.roe = None`
- **THEN** `missing_fields = ["roe"]`，`error` 非空
