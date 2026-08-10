## ADDED Requirements

### Requirement: 诚实降级标的在价值报告中去行动化展示

当 `ValueAnalysisResult.methodology_applicable is False` 时，`format_value_report`（非 `--json`）SHALL：

1. 在报告靠前位置展示诚实警告（来自 `warnings` 中的缺口文案，或等价置顶块）
2. 主评估行展示 `assessment` 原文「方法暂不适用」（不得改写成「低估」「高估」）
3. 若展示安全边际或公允区间，SHALL 附带「对照用」或等价中文标注，表明不可作为买卖依据

`--json` 模式 SHALL 原样序列化 `methodology_applicable` 与 `assessment` 字段，不做改写。

#### Scenario: 比亚迪文本报告主评估非低估

- **WHEN** `format_value_report(result)` 且 `result.code=="002594"`，`methodology_applicable=False`，`assessment=="方法暂不适用"`
- **THEN** 文本含「方法暂不适用」，含诚实警告关键语义，若出现安全边际数字则同时出现「对照用」或等价标注

#### Scenario: JSON 含 methodology_applicable

- **WHEN** `format_value_report(result, as_json=True)` 且 result 含 `methodology_applicable=False`
- **THEN** JSON 中该字段为 `false`，`assessment` 为「方法暂不适用」

#### Scenario: 正常标的展示不变

- **WHEN** `methodology_applicable=True` 且 assessment 为「低估」
- **THEN** 文本可正常显示「低估」，不强制追加「对照用」标注
