## ADDED Requirements

### Requirement: value_trap High 专项警示与置信度降级

`ValuationAggregator.aggregate()` SHALL 在 `results` 包含 `value_trap` 方法结果、且其 `details.overall_risk == "High"` 时：

1. 生成独立于 `warnings` 列表的醒目提示文案，写入 `AggregateResult.value_trap_alert: str | None`；文案 SHALL 列出至少一个判定为 `"High"` 的具体维度（`financial_health`/`business_deterioration`/`moat_erosion`/`ai_vulnerability`/`dividend_sustainability`）
2. 对既有 `confidence` 计算结果做一级降级：`"High"→"Medium"`、`"Medium"→"Low"`、`"Low"`/`"不可信"` 保持不变
3. `value_trap` 的既有 `_score_summary()` 摘要行 SHALL 仍照常追加到 `warnings` 列表，不因新增专项警示而移除

`overall_risk` 为 `"Medium"`/`"Low"`/`"Limited"`（或 `value_trap` 结果缺失）时，`AggregateResult.value_trap_alert` SHALL 为 `None`，且 `confidence` 不受本条规则影响。

#### Scenario: High 风险触发专项警示与降级

- **WHEN** `results["value_trap"].details == {"overall_risk": "High", "financial_health": "High", ...}`，且原始 confidence 计算结果为 `"High"`
- **THEN** `AggregateResult.value_trap_alert` 非空且包含 `"financial_health"` 对应的中文维度描述
- **THEN** `AggregateResult.confidence == "Medium"`（相对原始计算结果降一级）

#### Scenario: Medium/Low 风险不触发专项警示

- **WHEN** `results["value_trap"].details.overall_risk` 为 `"Medium"` 或 `"Low"`
- **THEN** `AggregateResult.value_trap_alert is None`
- **THEN** `confidence` 保持既有计算逻辑（`_confidence()` + 核心方法全 N/A 检测）的结果，不做降级

#### Scenario: 已处于「不可信」状态时降级不再生效

- **WHEN** 核心锚定方法全部 N/A 触发 `confidence = "不可信"`，同时 `value_trap.details.overall_risk == "High"`
- **THEN** `AggregateResult.confidence` 仍为 `"不可信"`（降级映射表对该值无操作）
- **THEN** `AggregateResult.value_trap_alert` 仍按规则 1 正常生成（警示与 confidence 降级是两条独立规则）
