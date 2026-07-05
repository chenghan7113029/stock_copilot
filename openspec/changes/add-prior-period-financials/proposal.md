## Why

Piotroski F-Score 和 Beneish M-Score 均需要「上一会计年度」的财报数据进行同比对比（`prior_roa`、`prior_debt_ratio`、`prior_current_ratio`、`prior_shares_outstanding`、`prior_gross_margin`、`prior_asset_turnover` 共 6 个字段）。当前这 6 个字段在所有股票上均为 None，导致两个质量评分始终只能基于部分指标（或完全不可用），严重影响价值陷阱检测可靠性。

## What Changes

- **prior_* 字段数据接入**：Tushare fetcher 拉取上一年度（`end_date-1 年`）财报，从中提取 6 个 prior 字段写入 `FetchResult.data`。
- **Piotroski / Beneish 评分提升**：prior 字段填充后，F-Score 满分条件数从当前约 5/9 提升到全量 9/9；M-Score 关键比值（`SGAI`、`GMI`）也可正常计算。
- **快照存储验证**：确认 `StockSnapshot` ORM 中 `prior_*` 字段被正确 persist 和 replay。

## Capabilities

### New Capabilities

- `tushare-prior-period-financials`：Tushare fetcher 支持拉取上一年度财报并写入 prior_* 字段。

### Modified Capabilities

- `value-data-provider`：merge 层将 prior_* 字段从「始终 None」变为「可来自 Tushare」。

## Impact

- `src/data_provider/tushare/fetcher.py`：新增 prior 年度拉取逻辑（利用已有 income/balancesheet/fina_indicator 接口，改 `end_date` 参数）
- `src/common/models/stock_data.py`：确认 prior_* 字段已定义（当前已存在）
- `test/data_provider/` 新增 prior period 单测
- `docs/mrd/features/value-analysis.md`：变更记录更新
