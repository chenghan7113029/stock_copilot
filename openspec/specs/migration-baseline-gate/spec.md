# migration-baseline-gate Specification

## Purpose
离线迁移基线（golden baseline）采集与对比硬门禁，保证同一 seed + 同一 `as_of` 下 tech/value/dual 报告零漂移。

## Requirements

### Requirement: 迁移离线基线采集
系统 SHALL 提供 `scripts/capture_migration_baseline.py`：基于 `data/fixtures/stock_copilot_seed.db`（或副本），对样本代码至少包含 `600519`、`601398`、`601939`，以严格离线方式生成 `report tech|value|dual --json`，规范化后写入 `test/fixtures/migration_baseline/seed/`，并生成含 git sha、采集时间与 **`as_of`（ISO 日期 `YYYY-MM-DD`）** 的 `manifest.json`。采集与对比所用离线 K 线窗口 MUST 以该 `as_of` 为观察日（`end=as_of`，`start=as_of - kline_days`），MUST NOT 依赖墙钟 `date.today()`。规范化 MUST 剔除 `data_timestamp`、绝对路径等非确定性字段。

#### Scenario: 采集写入 seed
- **WHEN** 在干净环境下运行采集脚本且 seed DB 可用
- **THEN** `test/fixtures/migration_baseline/seed/` 下存在对应 JSON 文件且 manifest 含 git sha 与 `as_of`

#### Scenario: manifest 含 as_of
- **WHEN** 采集完成
- **THEN** `manifest.json` 的 `as_of` 为合法 ISO 日期，且与本次离线窗口观察日一致

### Requirement: 迁移基线对比硬门禁
系统 SHALL 提供 `scripts/compare_migration_baseline.py`：读取 manifest 的 `as_of`，以同一观察日重新跑离线报告并与 baseline **逐 key** 比较。对 seed 三板报告，整数与日期字符串 MUST 完全一致；浮点默认相对误差 ≤ `1e-6`（或 manifest 登记豁免）。若 manifest 缺少 `as_of`，脚本 MUST 以非零退出码失败并提示重新采集。对比失败时 MUST 以非零退出码结束，并可写出 diff 报告路径。

#### Scenario: 无漂移通过
- **WHEN** 当前代码在相同 seed 与相同 `as_of` 上复现报告且与 baseline 一致
- **THEN** 对比脚本退出码为 0

#### Scenario: 漂移失败
- **WHEN** 任一关键数值字段超出容差
- **THEN** 对比脚本退出码非 0

#### Scenario: 缺少 as_of 失败
- **WHEN** manifest 无 `as_of` 字段
- **THEN** 对比脚本退出码非 0

#### Scenario: 墙钟滑动不改变对比结果
- **WHEN** 固定 seed 与 manifest.`as_of`，在不同系统日期下运行对比
- **THEN** 对比结论（通过/失败及关键字段）MUST 一致

### Requirement: 预期 schema 演进后的 re-baseline
当离线报告因**已归档产品变更**出现结构性差异（例如 dual evidence 由字符串变为 `{index,text}`，或新增确定性字段如 `methodology_applicable`），维护者 SHALL 在修复非确定性（含 `as_of`）之后重新运行 capture 更新 `seed/` 与 manifest，并在变更说明中登记原因。MUST NOT 仅靠放宽 `float_rel_tol` 掩盖时钟或算法漂移。

#### Scenario: 登记后重录通过
- **WHEN** 已实现 as_of 且仅残留已文档化的 schema 演进 diff
- **THEN** 运行 capture 更新 fixtures 后 compare 退出码为 0

### Requirement: 阶段 A PR 最低测试门禁
阶段 A 合并前，CI 或 Agent 验收 MUST 满足：`pytest -q -m "not network"` 全绿，且 `compare_migration_baseline.py` 通过。联网 E2E 对本阶段 MAY 跳过。

#### Scenario: 缺 baseline 对比不可视为通过
- **WHEN** 未运行或跳过 `compare_migration_baseline.py`
- **THEN** 不得将阶段 A 标为验收完成
