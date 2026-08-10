## 1. Tushare K 线（Issue #1）

- [x] 1.1 Modify `src/data_provider/tushare/fetcher.py`：实现 `fetch_kline`（`pro_bar` qfq）与列归一
- [x] 1.2 Create `test/data_provider/tushare/test_fetch_kline.py`：mock 成功/失败
- [x] 1.3 Create `test/e2e/test_tushare_kline_pipeline.py`（network）：tushare-only 写入缓存；无 Token 则 skip
- [x] 1.4 手工/CI：Baostock 失败 mock 下 `get_kline` 经 Tushare 成功

## 2. Tushare 实时 rt_k

- [x] 2.1 Modify `TushareFetcher`：实现 `fetch_realtime_quote`（仅 `rt_k`）
- [x] 2.2 Create `test/data_provider/tushare/test_fetch_realtime_quote.py`：含无权限路径
- [x] 2.3 Modify CLI/进度文案：realtime 降级警告明确；禁止 daily 冒充
- [x] 2.4 可选：`verify_rt_k_access` 探测脚本或单测钩子

## 3. Baostock 字段收敛与矩阵

- [x] 3.1 Modify `src/data_provider/baostock/fetcher.py`：`FINANCIAL_STATEMENT_FIELDS` 不写入
- [x] 3.2 Modify `test/data_provider/test_baostock_fetcher.py`：断言上述字段缺失
- [x] 3.3 Create `docs/design/data-source-field-matrix.md` 并与实现对齐

## 4. 情绪 Tushare 替代

- [x] 4.1 Create/Modify Tushare 情绪 fetcher：`margin` + `daily` 聚合
- [x] 4.2 Create `test/data_provider/sentiment/test_tushare_sentiment_fetcher.py`
- [x] 4.3 Modify `sync market` 路径：无 akshare、有 tushare 可写快照（允许 warnings）

## 5. Bootstrap 与配置预览

- [x] 5.1 Modify `scripts/cloud_bootstrap.py`：有 token 时 `tushare priority=1`
- [x] 5.2 可选：在 example 注释中预览目标默认序（正式去 akshare 留给阶段 C）

## 6. 验收与文档

- [x] 6.1 `pytest -q -m "not network"` 全绿
- [x] 6.2 `python scripts/compare_migration_baseline.py` 仍通过（S2）
- [x] 6.3 有 Token 时跑网络 E2E；完备性不收缩
- [x] 6.4 Modify `docs/mrd/features/data-source-migration.md`：勾选阶段 B；关闭 Issue #1
- [x] 6.5 运行 `/opsx-archive align-tushare-coverage`（用户确认后）
