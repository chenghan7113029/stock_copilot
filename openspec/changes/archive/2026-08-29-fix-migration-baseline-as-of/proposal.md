## Why

L3 迁移基线门禁（`compare_migration_baseline.py`）在「同一份 seed DB、不联网」前提下仍随墙钟漂移：`KlineProvider.get_kline` 用 `date.today()` 切缓存窗口，seed 末交易日停在 2026-06/07，导致 601398 跌破 20 根整票归零、600519 MACD「数据不足」等伪漂移（约 86 diffs）。这违反 MRD §12「离线 seed 报告零漂移」，且单纯 re-baseline 会在日历再滑动后复发。现在决策护航 V2 已引入 dual evidence `{index,text}` 与 `methodology_applicable`，需要先修好确定性再合法重录 golden。

## What Changes

- 为 migration baseline 引入 **`as_of` 观察日**：`manifest.json` 登记；`capture` / `compare` 用同一 `as_of` 跑离线 tech/value/dual，不依赖墙钟。
- 将 `as_of` 注入离线 K 线读取路径（最终影响 `get_kline` 的日期窗口），使生产库也可在指定观察日下复现/比对，而**默认联网生产路径仍用真实 today**。
- 修时钟后：对比 → 登记预期 schema 演进（numbered evidence、`methodology_applicable`）→ **re-baseline** seed JSON + manifest。
- 补充单测：固定 `as_of` 时，模拟不同墙钟日期，L3 对比结果不变。
- 更新 `docs/mrd/features/data-source-migration.md` §12（as_of 约定与 re-baseline 登记）。

## Capabilities

### New Capabilities

- （无）本变更强化既有门禁，不新增独立产品能力域。

### Modified Capabilities

- `migration-baseline-gate`: 要求 manifest 含 `as_of`；capture/compare 必须按 `as_of` 切离线窗口；文档化预期 schema 变更后的 re-baseline。
- （可选触及，若实现落在 provider 层）`tech-kline-provider`: 离线/测试路径支持显式 `as_of`（或等价注入），默认行为不变。

## Impact

- **代码**：`scripts/capture_migration_baseline.py`、`scripts/compare_migration_baseline.py`；`src/data_provider/kline_provider.py`（及必要时 `TechAnalyzer` / CLI offline 传参）；`src/common/migration_baseline.py`（若需规范化）；`test/fixtures/migration_baseline/**`；相关 pytest。
- **文档**：`docs/mrd/features/data-source-migration.md` §12；归档后合并进 MRD；`docs/mrd/roadmap-todo.md` 可记一条 housekeeping。
- **非目标**：不改默认联网 sync/报告的 today 语义；不放宽 `float_rel_tol`；不把 `.agents/` 等无关文件纳入本 change。
- **工程约定**：无目录/分层变更；一般无需改 `engineering-conventions.md`。
