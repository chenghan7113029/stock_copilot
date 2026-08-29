# confrontation-persona-stress-test Specification

## Purpose

在同一 numbered evidence 上运行固定 persona lens，对抗单框架思维。

## Requirements

### Requirement: Fixed persona set

系统 SHALL 内置 3 个 persona：`value_quality`、`trend_momentum`、`risk_governor`（定义见 design）。

#### Scenario: 每 persona 独立输出
- **WHEN** `report persona-stress 600519 --narrate`
- **THEN** 输出 SHALL 含 3 段 persona 结果，互不影响

### Requirement: Persona grounded narrate

每个 persona SHALL 独立调用 `narrate()` + `check_grounded()`；失败 persona SHALL 标记 `status=failed` 且不阻塞其他 persona。

#### Scenario: 单 persona 失败
- **WHEN** trend_momentum grounded 失败
- **THEN** 其余 persona 仍 MAY 成功；整体命令 exit 0 并含 failed 摘要

### Requirement: Evidence ref in persona output

每个 persona 输出 SHALL 含 `emphasized_refs`（side + index 列表），且 validator SHALL 校验 index 合法。

#### Scenario: 非法 emphasized ref
- **WHEN** LLM 返回越界 index
- **THEN** grounded 或 post-validator SHALL 判失败并重试

### Requirement: Persistence

`report persona-stress` SHALL 写入 `persona_stress_json` 到 confrontation record（新建或 `--confrontation-id` 更新）。

#### Scenario: 挂载已有 confrontation
- **WHEN** `--confrontation-id 12`
- **THEN** SHALL 更新 id=12 的 record，不创建重复 evidence 快照
