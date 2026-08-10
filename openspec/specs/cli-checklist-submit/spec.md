# cli-checklist-submit Specification

## Purpose
TBD - created by archiving change add-decision-checklist. Update Purpose after archive.
## Requirements
### Requirement: CLI 交互式 Checklist 提交
系统 SHALL 提供 `python -m apps.cli checklist submit <code> [--action buy|sell]`，通过一系列 prompt 依次收集价值理由（多条，空行结束）、技术面配合情况、情绪位置及解读、止损点、止盈点，采集完毕后调用 `ChecklistValidator` 校验并持久化结果（`passed=True/False` 均写入）。

#### Scenario: 校验通过
- **WHEN** 用户在交互中填写了满足所有规则的字段
- **THEN** SHALL 输出「Checklist 提交成功（合规）」，记录 SHALL 以 `passed=True` 落库

#### Scenario: 校验失败仍留痕
- **WHEN** 用户填写的价值理由只有 1 条
- **THEN** SHALL 输出明确的拒绝原因列表与「本次提交不构成合规 Checklist」提示，记录 SHALL 以 `passed=False` 落库（不做静默丢弃）

### Requirement: CLI 历史查询
系统 SHALL 提供 `python -m apps.cli checklist show <code>`，列出该代码的历史 Checklist 提交记录，SHALL 显示每条记录的 `action`/`passed`/`created_at`/关键字段摘要。

#### Scenario: 无历史记录
- **WHEN** 该代码从未提交过 Checklist
- **THEN** SHALL 输出「暂无 <code> 的 Checklist 记录」，不抛异常

