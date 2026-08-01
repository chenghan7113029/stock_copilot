## MODIFIED Requirements

### Requirement: ValueAnalysisResult 包含规定字段

`ValueAnalysisResult` SHALL 包含：`code`、`name`、`current_price`、`prototype`、`method_keys_used`、`fair_value_range`（ValuationRange 或 None）、`margin_of_safety`（float % 或 None）、`price_percentile`（0–100 或 None）、`assessment`（str）、`confidence`（"High"/"Medium"/"Low"/"不可信"）、`method_results`（dict）、`warnings`（list[str]）、`data_timestamp`、`fundamental_report_date`、`value_score`（预留，None）、`value_trap_alert`（str 或 None，默认 None；`value_trap` 方法 `overall_risk == "High"` 时非空的醒目提示文案，语义与生成规则见 `value-aggregator` capability）。

#### Scenario: 输出类型校验

- **WHEN** 分析任意 A 股代码成功返回
- **THEN** result 为 `ValueAnalysisResult` 实例，所有必填字段不缺失（`warnings` 至少为空列表，`method_results` 至少为空字典，`value_trap_alert` 缺省为 `None`）

#### Scenario: value_trap High 时字段透传

- **WHEN** `ValuationAggregator.aggregate()` 返回的 `AggregateResult.value_trap_alert` 非空
- **THEN** `ValueAnalyzer._analyze_stock()` 构造的 `ValueAnalysisResult.value_trap_alert` 与其完全一致（透传，不做二次加工）

#### Scenario: 非 High 风险时字段为 None

- **WHEN** 分析结果中 `value_trap` 方法 `overall_risk` 不是 `"High"`（或该方法未运行）
- **THEN** `ValueAnalysisResult.value_trap_alert is None`
