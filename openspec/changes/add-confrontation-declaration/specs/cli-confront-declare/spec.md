# cli-confront-declare Specification

## Purpose

CLI 提交与查询用户 confrontation 声明。

## Requirements

### Requirement: confront declare command

系统 SHALL 提供 `python -m apps.cli confront declare <confrontation_id>` 与 `--json-file <path>`。

#### Scenario: 交互式采集
- **WHEN** 无 `--json-file`
- **THEN** SHALL 通过 prompt 收集 schema 字段并校验

#### Scenario: JSON 文件提交
- **WHEN** `--json-file declare.json`
- **THEN** SHALL 解析 JSON 并执行相同 validator

### Requirement: confront show command

系统 SHALL 提供 `confront show <code> [--json]` 列出该 code 的 confrontation 记录（含 evidence 摘要、narrate_status、declare 状态）。

#### Scenario: 无记录
- **WHEN** code 无 confrontation 历史
- **THEN** SHALL 输出明确提示而非空异常
