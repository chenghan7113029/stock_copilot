# akshare-default-retirement Specification

## Purpose
TBD - created by archiving change retire-akshare-default. Update Purpose after archive.
## Requirements
### Requirement: 默认配置不含 AKShare
`config/app.example.yaml` 与 `cloud_bootstrap`（及等价模板）在生成/示例的 `data_sources` 中 MUST 仅包含 `tushare`（priority=1，需 token）与 `baostock`（priority=2），MUST NOT 默认写入 `akshare` 条目。

#### Scenario: 全新 bootstrap
- **WHEN** 在无既有 app.yaml 环境下执行 bootstrap 且提供 Tushare token
- **THEN** 生成的配置 enabled 列表不含 akshare

### Requirement: 生产路径零默认 AKShare 无参构造
`src/` 生产路径中 MUST NOT 存在 `AKShareFetcher()` 无参默认构造（实时叠加、K 线备源等）。AKShare 仅可在显式配置启用且经 Router 实例化时出现。

#### Scenario: 静态检查
- **WHEN** 对 `src/` 检索 `AKShareFetcher()`
- **THEN** 无「无参构造」命中（测试与 legacy 模块除外）

### Requirement: AKShare 遗留测试隔离
依赖真实 AKShare 网络或默认启用 akshare 的测试 SHALL 标记为 `akshare_legacy`（或等价），默认 `pytest -m "not network"` / CI 主路径 MUST NOT 运行这些用例。

#### Scenario: 默认 CI 不跑 legacy
- **WHEN** 执行仓库默认单测命令
- **THEN** 不收集或跳过 `akshare_legacy` 用例

