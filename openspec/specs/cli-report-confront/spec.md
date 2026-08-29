# cli-report-confront Specification

## Purpose

CLI 入口暴露 confrontation Level 0/1 报告。

## Requirements

### Requirement: report confront subcommand

`apps.cli` SHALL 注册 `report confront` 子命令，行为等价于 `run_report_confront(code, narrate=..., as_json=..., output=...)`.

#### Scenario: 文本报告含水印
- **WHEN** `report confront 600519`
- **THEN** 输出 SHALL 含 evidence 列表（带序号）、可选 narrative 段、固定免责声明

#### Scenario: 写入 output 文件
- **WHEN** `--output reports/600519_confront.md`
- **THEN** SHALL 写入与 stdout 同构的 markdown 文本

### Requirement: Idempotent cache

当 `--narrate` 且 evidence 未变时，SHALL 优先读取 `LLMNarrateCache` 命中结果（与 PO-02 相同 cache key 策略）。

#### Scenario: 缓存命中
- **WHEN** 相同 code + evidence hash 再次 `--narrate`
- **THEN** SHALL NOT 重复调用 LLM API
