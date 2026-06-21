## ADDED Requirements

### Requirement: PEG Ratio 成长估值
系统 SHALL 实现 `PEG`，公式 `PEG = P/E ÷ 增长率`，公允价 = EPS × 增长率 × fair_peg（默认 fair_peg=1.0）。
growth_rate ≤ 0 时返回 error。

#### Scenario: 正常 PEG 计算
- **WHEN** eps > 0、growth_rate > 0、current_price 齐全
- **THEN** `fair_value` 与 ref ±0.1%

### Requirement: GARP 合理价格成长估值
系统 SHALL 实现 `GARP`（Growth At Reasonable Price），结合 PEG 与 P/E 上限给出公允价区间。

#### Scenario: 正常 GARP 计算
- **WHEN** eps、growth_rate、pe_ratio 可计算
- **THEN** `fair_value > 0`，与 ref ±0.1%

### Requirement: RuleOf40 SaaS/高成长健康度
系统 SHALL 实现 `RuleOf40`，指标 = 收入增长率 + 利润率（%）。
`details.rule_of_40_score` 写入结果；≥ 40 健康。`fair_value` 可为 0，`details.output_type = "score"`。

#### Scenario: 正常 Rule of 40
- **WHEN** revenue_growth 与 operating_margin 齐全
- **THEN** `details.rule_of_40_score` 与 ref 一致

### Requirement: EVEBITDA 企业价值倍数估值
系统 SHALL 实现 `EVEBITDA`，公允价 = (行业基准 EV/EBITDA × EBITDA - net_debt) / shares。
`ev_ebitda_multiple` 可配置（默认来自 AssumptionProvider 或方法 __init__）。

#### Scenario: 正常 EV/EBITDA 计算
- **WHEN** ebitda > 0、shares_outstanding、net_debt 齐全
- **THEN** `fair_value` 与 ref ±0.1%

#### Scenario: ebitda 为 None 时 missing_fields
- **WHEN** `StockData.ebitda = None` 且无法从 ebit+depreciation 推导
- **THEN** `missing_fields` 含 `ebitda`
