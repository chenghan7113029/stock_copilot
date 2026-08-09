## Why

阶段 A 统一选源后，仍缺 Tushare 对 K 线、实时、情绪等旁路的能力矩阵；Issue [#1](https://github.com/chenghan7113029/stock_copilot/issues/1)（KlineProvider 不支持 Tushare）阻塞「仅 tushare+baostock」核心链路。阶段 B 在 Router 上补齐 Tushare，使生产可用性顺序与配置一致，并收敛 Baostock 低可信财报字段。

权威需求：[docs/mrd/features/data-source-migration.md](../../../docs/mrd/features/data-source-migration.md) §5.B / §12.4。**依赖**：`unify-data-source-router` 已落地。

## What Changes

- `TushareFetcher.fetch_kline`：`pro_bar(adj='qfq')`，列对齐现有 K 线契约（关闭 Issue #1）
- `TushareFetcher.fetch_realtime_quote`：`pro.rt_k`；无权限明确失败并 failover/EOD 降级；**禁止**用 `daily` 冒充盘中实时
- Baostock：**不产出** `FINANCIAL_STATEMENT_FIELDS`（或标 missing），配合阶段 A 已删除的 override
- 新建字段能力矩阵文档 `docs/design/data-source-field-matrix.md`
- 情绪 V1 的 Tushare 替代（`margin` + `daily` 聚合近似）；筹码评估 `cyq_perf`（5000 分）或文档化降级
- `cloud_bootstrap`：有 token 时写入 `tushare priority=1`
- 联网 E2E / mock 单测；**离线 migration baseline 仍须通过（报告零漂移）**

## Capabilities

### New Capabilities

- `tushare-kline`：Tushare 历史 K 线拉取与列归一
- `tushare-realtime-quote`：`rt_k` 实时报价与无权限降级语义
- `tushare-sentiment-coverage`：情绪面 Tushare 替代分量（涨跌停近似 + 两融等）
- `data-source-field-matrix`：每字段每源 `native` / `derived` / `unsupported` 文档与实现一致

### Modified Capabilities

- `tech-kline-provider`：Failover 链可命中 Tushare K 线（Baostock 失败时仍可 sync）
- `tech-realtime-overlay`：可命中 Tushare `rt_k`；Baostock 不参与实时
- `value-data-provider`：Baostock 不再写入 §3 财报字段集合；Tushare(1)+Baostock(2) 下财报由 Tushare 主导

## Impact

- **代码**：`src/data_provider/tushare/fetcher.py`、`baostock/fetcher.py`、情绪 fetcher、`scripts/cloud_bootstrap.py`
- **测试**：`test/data_provider/tushare/test_fetch_kline.py`、`test_fetch_realtime_quote.py`、情绪单测、e2e kline pipeline；`compare_migration_baseline.py` 持续门禁
- **文档**：字段矩阵；MRD 阶段 B 勾选；Issue #1 关闭条件
- **权限**：Owner 需确认 `rt_k` 月权限（OQ-1）；2000 分可覆盖多数接口，筹码 5000 分可选
