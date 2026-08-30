## 1. as_of 注入（provider + analyzer）

- [x] 1.1 Modify `src/data_provider/kline_provider.py`：`get_kline` 增加 `as_of`；`None` → `date.today()`，否则用其作 end 计算窗口
- [x] 1.2 Modify `src/service/tech/analyzer.py`：`analyze(..., as_of=None)` 并下传至 `get_kline`
- [x] 1.3 Grep `date.today()` / 等价调用于 value/dual 离线路径；若影响 baseline 则同期注入同一 `as_of`（否则记注释说明无关）

## 2. capture / compare / manifest

- [x] 2.1 Modify `scripts/capture_migration_baseline.py`：接受/写入 `as_of` 到 `manifest.json`，`run_offline_json` 使用该观察日
- [x] 2.2 Modify `scripts/compare_migration_baseline.py`：读 `as_of`；缺失则非零退出；对比时使用同一观察日
- [x] 2.3 Test `test/`：为 kline `as_of` 与「固定 as_of + 伪造墙钟仍一致」补充单测（可放 `test/data_provider/` 或 `test/scripts/`）

## 3. Re-baseline 与文档

- [x] 3.1 选定观察日（建议 `2026-08-10` 或验证后写入），更新/生成 manifest，运行 compare 确认时钟伪影消失
- [x] 3.2 运行 `capture_migration_baseline.py` 重录 `test/fixtures/migration_baseline/seed/`；登记原因：as_of + numbered evidence + `methodology_applicable`
- [x] 3.3 Modify `docs/mrd/features/data-source-migration.md` §12：as_of 约定、生产库复用注意、re-baseline 登记
- [x] 3.4 确认 `python scripts/compare_migration_baseline.py` 退出码 0；相关 pytest 通过

## 4. 归档前

- [x] 4.1 将本 change 要点合并进 `docs/mrd`（§12 已更新则勾选；必要时 `roadmap-todo` 记 housekeeping）
- [x] 4.2 Archive：`openspec/changes/archive/YYYY-MM-DD-fix-migration-baseline-as-of`，同步 main specs
