# data-source-field-matrix Specification

## Purpose
TBD - created by archiving change align-tushare-coverage. Update Purpose after archive.
## Requirements
### Requirement: 数据源字段能力矩阵文档
仓库 SHALL 提供 `docs/design/data-source-field-matrix.md`，对价值面关键字段及 K 线/实时/筹码/情绪数据项，按 `tushare` / `baostock` / `akshare` 标注支持级别：`native` / `derived` / `unsupported`。实现行为 MUST 与矩阵一致；矩阵变更须与代码同 PR。

#### Scenario: 财报字段与 Baostock 一致
- **WHEN** 矩阵将某 `FINANCIAL_STATEMENT_FIELDS` 标为 baostock `unsupported`
- **THEN** `BaostockFetcher` 的 fundamentals 输出不包含该字段（或显式 missing），且单测锁定

#### Scenario: 矩阵可被评审
- **WHEN** Reviewer 打开字段矩阵文档
- **THEN** 可核对阶段 B 验收样本股（如 600519）的 `industry`/财报来源预期为 tushare native

