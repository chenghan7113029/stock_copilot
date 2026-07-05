## ADDED Requirements

### Requirement: DCF 与 EPV 方法行补充语义说明
价值面报告中，`dcf` 和 `epv` 方法的输出行 SHALL 分别追加括号内的语义提示，帮助用户理解两者差异，避免直接对比公允价数值时产生误判。

- `dcf` 行：追加 `(含增长假设)` 及 DCF 所用 `g₁` 与折现率简报
- `epv` 行：追加 `(零增长地板价)`

#### Scenario: 价值报告中 DCF/EPV 行有语义提示
- **WHEN** `format_value_report(result)` 且 result 包含 dcf 与 epv 方法结果
- **THEN** dcf 方法行包含 "(含增长假设)" 字样，epv 方法行包含 "(零增长地板价)" 字样

#### Scenario: 语义提示不影响 JSON 模式
- **WHEN** `format_value_report(result, as_json=True)`
- **THEN** JSON 输出中 `method_results.dcf.analysis` 字段包含增长假设说明，不影响结构
