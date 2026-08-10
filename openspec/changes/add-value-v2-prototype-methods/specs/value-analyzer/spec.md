## ADDED Requirements

### Requirement: Analyzer 编排 V2 方法与毕业字段

`ValueAnalyzer` SHALL 对已启用 V2 prototype 运行其 method_keys，并将情景/周期等结构化结果纳入 `ValueAnalysisResult`（新增字段或 `details` 契约在实现时固定）。当 V2 专用输出满足该原型「可引用」条件时，SHALL 置 `methodology_applicable=True` 并生成非「方法暂不适用」的主评估；否则保持诚实压制。

#### Scenario: 毕业样本 methodology_applicable 为 True

- **WHEN** 样本已毕业且专用方法成功
- **THEN** `methodology_applicable is True`，`assessment != "方法暂不适用"`

#### Scenario: 未毕业样本保持压制

- **WHEN** 样本仍在诚实名单或专用输入缺失
- **THEN** `methodology_applicable is False`
