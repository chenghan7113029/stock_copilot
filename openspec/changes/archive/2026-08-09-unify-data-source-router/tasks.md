## 1. 迁移基线（A 前置门禁）

- [x] 1.1 Create `scripts/capture_migration_baseline.py`：基于 seed DB 离线采集 600519/601398/601939 的 tech/value/dual JSON + `manifest.json`
- [x] 1.2 Create `scripts/compare_migration_baseline.py`：逐 key 对比，S2 容差按 MRD §12.3
- [x] 1.3 运行采集并将 `test/fixtures/migration_baseline/**` 提交入库
- [x] 1.4 Create `test/scripts/test_compare_migration_baseline.py`（或等价）：对当前 HEAD 断言对比通过

## 2. Router 与策略

- [x] 2.1 Create/Modify `src/data_provider/router.py`（或扩展 `manager.py`）：`from_config` → 按 enabled+priority 排序的 fetcher 列表
- [x] 2.2 Create `src/data_provider/strategies.py`：`ValueMergeStrategy`、`FailoverStrategy`（含命中源标签）
- [x] 2.3 Create `test/data_provider/test_router_failover.py`：mock 调用顺序与全失败路径
- [x] 2.4 Create `test/data_provider/test_provider_merge_golden.py`：固定 FetchResult → StockData；覆盖去 override 后的 golden

## 3. 价值面去 override

- [x] 3.1 Modify `src/data_provider/provider.py`：删除 `FINANCIAL_STATEMENT_FIELDS` 的 Tushare `override_field` 分支
- [x] 3.2 Modify `test/data_provider/test_provider.py`：更新/删除 `test_tushare_financials_override_baostock_estimates`，改为 priority 合并断言

## 4. K 线与实时重构

- [x] 4.1 Modify `src/data_provider/kline_provider.py`：源列表来自 Router；禁止无条件 `BaostockFetcher()`
- [x] 4.2 Modify `src/data_provider/realtime_overlay_provider.py`：禁止无参默认 AKShare；注入 failover 链
- [x] 4.3 Modify `test/data_provider/test_kline_provider.py`：覆盖 priority failover 与 disabled akshare 零调用
- [x] 4.4 Modify 相关 realtime 单测：断言未启用源不实例化

## 5. 筹码与情绪构造路径

- [x] 5.1 Modify `ChipDistributionProvider` / `MarketSentimentProvider`：`from_config` / Router 注入；默认不强制 akshare
- [x] 5.2 Create/Modify 单测：仅 baostock 启用时零 AKShare 实例化（允许能力缺失降级）

## 6. 验收与文档

- [x] 6.1 运行 `pytest -q -m "not network"` 全绿
- [x] 6.2 运行 `python scripts/compare_migration_baseline.py` 通过
- [x] 6.3 Modify `docs/mrd/features/data-source-migration.md`：勾选阶段 A 验收项；变更记录追加
- [x] 6.4 若 Router 目录/命名落地，Modify `docs/dev/engineering-conventions.md` 数据源分层说明
- [ ] 6.5 运行 `/opsx-archive unify-data-source-router`（或用户确认后归档）
