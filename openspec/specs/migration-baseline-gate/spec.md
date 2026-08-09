# migration-baseline-gate Specification

## Purpose
TBD - created by archiving change unify-data-source-router. Update Purpose after archive.
## Requirements
### Requirement: 迁移离线基线采集
系统 SHALL 提供 `scripts/capture_migration_baseline.py`：基于 `data/fixtures/stock_copilot_seed.db`（或副本），对样本代码至少包含 `600519`、`601398`、`601939`，以严格离线方式生成 `report tech|value|dual --json`，规范化后写入 `test/fixtures/migration_baseline/seed/`，并生成含 git sha / 采集时间的 `manifest.json`。规范化 MUST 剔除 `data_timestamp`、绝对路径等非确定性字段。

#### Scenario: 采集写入 seed
- **WHEN** 在干净环境下运行采集脚本且 seed DB 可用
- **THEN** `test/fixtures/migration_baseline/seed/` 下存在对应 JSON 文件且 manifest 含 git sha

### Requirement: 迁移基线对比硬门禁
系统 SHALL 提供 `scripts/compare_migration_baseline.py`：重新跑离线报告并与 baseline **逐 key** 比较。对 seed 三板报告，整数与日期字符串 MUST 完全一致；浮点默认相对误差 ≤ `1e-6`（或 manifest 登记豁免）。对比失败时 MUST 以非零退出码结束，并可写出 diff 报告路径。

#### Scenario: 无漂移通过
- **WHEN** 当前代码在相同 seed 上复现报告且与 baseline 一致
- **THEN** 对比脚本退出码为 0

#### Scenario: 漂移失败
- **WHEN** 任一关键数值字段超出容差
- **THEN** 对比脚本退出码非 0

### Requirement: 阶段 A PR 最低测试门禁
阶段 A 合并前，CI 或 Agent 验收 MUST 满足：`pytest -q -m "not network"` 全绿，且 `compare_migration_baseline.py` 通过。联网 E2E 对本阶段 MAY 跳过。

#### Scenario: 缺 baseline 对比不可视为通过
- **WHEN** 未运行或跳过 `compare_migration_baseline.py`
- **THEN** 不得将阶段 A 标为验收完成

