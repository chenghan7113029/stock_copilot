# confrontation-narrate-api Specification

## Purpose

通过应用内置 LLM API 将红蓝证据分桶（Level 0）升级为 grounded 互驳叙事（Level 1），并持久化 confrontation 记录供 declare / 复盘关联。

## Requirements

### Requirement: Numbered evidence contract

系统 SHALL 在 `report dual --json` 与 `report confront --json` 输出中为 `bull_evidence` 与 `bear_evidence` 各条目提供 **1-based** `index` 字段；两侧列表独立编号。

#### Scenario: JSON 含 index
- **WHEN** 运行 `report dual 600519 --json`
- **THEN** 每条 evidence 对象 SHALL 含 `index` 与 `text`，且 index 从 1 连续递增

### Requirement: ConfrontationNarrator grounded narrate

系统 SHALL 提供 `ConfrontationNarrator.narrate(buckets, code) -> NarrateResult`，仅基于 numbered evidence 调用 `narrate()`，并对合成文本执行 `check_grounded()`。

#### Scenario: Grounded 成功
- **WHEN** LLM 输出通过 schema 与 grounded 校验
- **THEN** 返回结构化 JSON（含 bull_thesis、bear_thesis、rebuttals）并 `narrate_status=ok`

#### Scenario: Grounded 失败
- **WHEN** 重试用尽仍无法通过 grounded
- **THEN** SHALL 不写入 narrative_json，设置 `narrate_status=failed`，CLI 仍输出 Level 0 evidence

### Requirement: Confrontation persistence

系统 SHALL 在 `report confront` 执行后写入 `confrontation_records`（至少含 code、evidence_json、narrate_status、created_at）。

#### Scenario: 无 --narrate
- **WHEN** `report confront 600519` 不带 `--narrate`
- **THEN** SHALL 写入 record，`narrate_status=skipped`，narrative_json 为 null

### Requirement: CLI report confront

系统 SHALL 提供 `python -m apps.cli report confront <code> [--narrate] [--json] [--output]`；Level 0 阶段 SHALL NOT 联网。

#### Scenario: --narrate 无 LLM 配置
- **WHEN** 未配置 LLM 且传入 `--narrate`
- **THEN** SHALL 输出 Level 0 并提示配置 LLM；exit code 非 0 或 documented warning（design 实现时二选一并单测）
