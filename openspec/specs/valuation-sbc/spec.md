# valuation-sbc Specification

## Purpose
TBD - created by archiving change add-valuation-methods-phase8. Update Purpose after archive.
## Requirements
### Requirement: SBCAnalysis 股权激励稀释分析
系统 SHALL 实现 `SBCAnalysis` 方法，计算股权激励（SBC）对每股盈利的稀释程度，
给出调整后 EPS 及稀释性评级（Negligible/Light/Moderate/Severe/Extreme）。
`details.output_type = "score"`，`fair_value = current_price`（不参与估值区间聚合）。
A 股 `sbc = None` 时输出 `applicability = "Not Applicable"`，不返回错误。

**关键指标：**

| 指标 | 计算公式 |
|------|---------|
| SBC/净利润 | `sbc / net_income`（%） |
| SBC/营收 | `sbc / revenue`（%） |
| 年稀释率 | `(shares_outstanding - prior_shares_outstanding) / prior_shares_outstanding`（%）；prior 缺失时省略 |
| 调整后 EPS | `(net_income - sbc) / shares_outstanding` |

**稀释性评级：**

| SBC/净利润 | 评级 |
|-----------|------|
| < 5% | Negligible |
| 5–15% | Light |
| 15–30% | Moderate |
| 30–50% | Severe |
| > 50% | Extreme |

#### Scenario: SBC 为 None 时 Not Applicable
- **WHEN** `StockData.sbc = None`
- **THEN** `applicability = "Not Applicable"`，`error = None`，不抛异常

#### Scenario: SBC 为零时 Negligible
- **WHEN** `sbc = 0.0`, `net_income = 1e10`, `shares_outstanding = 1.29e10`, `current_price = 1500.0`
- **THEN** `details.dilution_rating = "Negligible"`，`details.sbc_to_net_income = 0.0`，`details.adjusted_eps = net_income / shares_outstanding`

#### Scenario: 高 SBC 时 Extreme 评级
- **WHEN** `sbc = 1.5e9`, `net_income = 3e9`, `shares_outstanding = 5.5e10`, `current_price = 30.0`（SBC/净利润 = 50%）
- **THEN** `details.dilution_rating = "Severe"`（50% 对应 Severe），`details.adjusted_eps < eps`，`details.sbc_to_net_income ≈ 0.50`

#### Scenario: prior_shares_outstanding 缺失时省略稀释率
- **WHEN** `sbc > 0`, `prior_shares_outstanding = None`
- **THEN** `details.annual_dilution_rate = None`，`warnings` 含"prior_shares_outstanding unavailable"，其余指标正常计算

#### Scenario: net_income 为 None 时 missing_fields
- **WHEN** `sbc > 0`, `net_income = None`
- **THEN** `missing_fields` 含 `net_income`，`error` 非空，不抛异常

