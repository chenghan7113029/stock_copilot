## ADDED Requirements

### Requirement: dual 摘要安全边际与 value 一致
`report dual` 摘要中的安全边际展示 MUST 与同一分析结果下 `report value` 使用相同的百分数点语义与量级。

#### Scenario: 不再二次缩放
- **WHEN** `margin_of_safety` 约为 `-0.8` 且本地数据可生成 dual 与 value 报告
- **THEN** dual 摘要中的安全边际 SHALL 显示约 `-0.8%`，SHALL NOT 显示约 `-80%`

### Requirement: dual 默认带入 value/tech 讲解
`report dual` 的默认人类可读文本输出在证据分桶之后，SHALL 附加与 `report value` / `report tech` 同源的讲解内容（估值方法卡片与/或价值陷阱拆解、技术指标注释）。讲解 MUST 默认开启。证据列表（bull/bear）的 Level 0 结构 MUST 保留，供 Skill 继续消费。

#### Scenario: 文本 dual 含讲解分区
- **WHEN** 用户执行 `report dual <code>`（非 `--json`）且价值与技术结果均可用
- **THEN** 输出在多方/空方证据之后 SHALL 包含可识别的价值面讲解与技术面讲解内容（例如独立小节标题）

#### Scenario: JSON 向后兼容
- **WHEN** 用户执行 `report dual <code> --json`
- **THEN** 输出 SHALL 仍包含 `bull_evidence` 与 `bear_evidence` 字段；若增加讲解字段，MUST 为附加键且不得删除或重命名既有证据字段
