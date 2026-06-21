## ADDED Requirements

### Requirement: AltmanZScore 破产预测评分
系统 SHALL 实现 `AltmanZScore`，公式 `Z = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 1.0X₅`。
`details.z_score` 写入计算结果；`fair_value` 可为 0；`details.output_type = "score"`。
Z > 2.99 → 安全区；Z < 1.81 →  distress 区。

#### Scenario: 正常 Z-Score 计算
- **WHEN** total_assets、total_liabilities、current_price、shares_outstanding 齐全，ebit/revenue 可推导
- **THEN** `details.z_score` 与 ref ±0.1%，`analysis` 含区间判定

#### Scenario: total_assets 为 None 时 missing_fields
- **WHEN** `StockData.total_assets = None`
- **THEN** `missing_fields` 含 `total_assets`

### Requirement: PiotroskiFScore 财务质量九项评分
系统 SHALL 实现 `PiotroskiFScore`，9 项二元指标求和得 F-Score（0–9）。
`details.f_score` 写入结果；F ≥ 7 强，F ≤ 2 弱。

#### Scenario: 完整 prior 字段时正常计分
- **WHEN** 当期与 prior_* 对比字段齐全
- **THEN** `details.f_score` 为 0–9 整数，与 ref 一致

#### Scenario: prior 字段缺失时 Limited
- **WHEN** 任一 prior_* 对比字段为 None
- **THEN** `applicability = "Limited"`，`warnings` 说明缺失项，不抛异常

### Requirement: BeneishMScore 盈余操纵检测
系统 SHALL 实现 `BeneishMScore`，8 变量加权得 M-Score。
`details.m_score` 写入结果；M > -2.22 疑似操纵。

#### Scenario: 8 组件齐全时正常计分
- **WHEN** Beneish 8 组件字段（或可从财报推导）齐全
- **THEN** `details.m_score` 与 ref ±0.1%

#### Scenario: 组件缺失时 Limited
- **WHEN** 关键组件无法计算
- **THEN** `applicability = "Limited"`，`error` 或 `warnings` 说明，不抛异常
