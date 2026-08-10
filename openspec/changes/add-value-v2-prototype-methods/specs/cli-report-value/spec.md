## ADDED Requirements

### Requirement: 价值报告展示 V2 情景与周期语义

当结果含情景估值或周期调整语义时，`format_value_report`（非 JSON）SHALL 以非金融可读方式展示：多档情景标签、现价相对落位说明、或周期位置说明；SHALL NOT 仅显示一个未解释的公允中枢。JSON 模式 SHALL 序列化新增字段。

#### Scenario: 比亚迪报告含三档情景标签

- **WHEN** 结果含 P1 情景结构
- **THEN** 文本出现悲观/基准/乐观（或等价中文）分档

#### Scenario: 诚实未毕业报告仍去行动化

- **WHEN** `methodology_applicable=False`
- **THEN** 主评估为方法暂不适用语义，并保留对照用标注（与诚实层一致）
