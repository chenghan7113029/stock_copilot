## ADDED Requirements

### Requirement: report value 报告头部渲染价值陷阱高危警示

`format_value_report()` 文本渲染路径 SHALL 在 `result.value_trap_alert` 非空时，于报告头部（名称/原型之后、评估/置信度之前）插入独立于文末 `--- 警告 ---` 区块的醒目警示区块，展示 `value_trap_alert` 的完整文案。`result.value_trap_alert` 为空时 SHALL 不渲染该区块，输出与现状一致。

`--json` 输出路径 SHALL 自动包含 `value_trap_alert` 字段（沿用既有 dataclass 序列化逻辑，无需额外分支）。

#### Scenario: High 风险时渲染醒目区块

- **WHEN** `result.value_trap_alert = "🚨 疑似价值陷阱（High Risk）：..."`
- **THEN** `format_value_report(result)` 返回的文本在"评估:"行之前包含该警示文案
- **THEN** 文末仍照常输出 `--- 警告 ---` 区块（包含 value_trap 的既有摘要行），两者不冲突不去重

#### Scenario: 非 High 风险时不渲染

- **WHEN** `result.value_trap_alert is None`
- **THEN** `format_value_report(result)` 输出中不出现警示区块，其余内容与本 change 之前完全一致

#### Scenario: JSON 输出包含新字段

- **WHEN** `format_value_report(result, as_json=True)` 且 `result.value_trap_alert` 非空
- **THEN** 输出 JSON 顶层包含键 `"value_trap_alert"`，值为对应文案
