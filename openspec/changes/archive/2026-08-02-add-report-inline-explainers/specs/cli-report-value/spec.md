## ADDED Requirements

### Requirement: 默认嵌入估值方法讲解与价值陷阱说明
`report value` 的默认人类可读文本输出 SHALL 对每个 Applicable 估值方法嵌入完整讲解卡片（含义、适用、公式、本次入参与来源、结果），并对价值陷阱（若存在该方法结果）嵌入白话拆解。Not Applicable 方法 SHALL 以中文说明不适用原因。讲解 MUST 默认开启，本期无需用户传入额外 flag。

#### Scenario: 文本报告含方法卡片
- **WHEN** 用户执行 `report value <code>`（非 `--json`）且存在至少一个 Applicable 方法
- **THEN** stdout 文本 SHALL 包含该方法的讲解卡片关键要素（至少：含义或适用说明、公式或「公式未提供」、结果中文评估）

#### Scenario: 价值陷阱详解出现在 value 报告
- **WHEN** 方法结果含 `value_trap` 且可解析 overall_risk
- **THEN** 文本报告 SHALL 包含价值陷阱总体风险的中文解释与维度拆解

#### Scenario: 评估词中文化
- **WHEN** 方法评估原值为 `Undervalued` / `Overvalued` 等英文词
- **THEN** 默认文本报告的方法行或卡片结果区 SHALL 优先显示中文「低估」/「高估」等对应词
