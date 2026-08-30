# cli-report-persona-stress Specification

## Purpose

CLI 暴露 persona 压力测试。

## Requirements

### Requirement: report persona-stress subcommand

系统 SHALL 提供 `python -m apps.cli report persona-stress <code> [--narrate] [--json] [--output] [--confrontation-id N]`。

#### Scenario: Level 0 only
- **WHEN** 不带 `--narrate`
- **THEN** SHALL 输出三 persona 的「待 narrate」占位或仅 evidence 摘要（documented）

#### Scenario: 固定免责声明
- **WHEN** 任意 narrate 成功
- **THEN** 输出 SHALL 含「persona 为思维透镜，不构成买卖建议」类固定文案
