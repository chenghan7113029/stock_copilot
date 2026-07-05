## Why

`historical_pb` 始终为空（`pb_relative` 完全不可用），`historical_pe` 仅覆盖约 2 年（8 季）导致相对估值窗口偏窄、均值不稳定。Tushare `daily_basic` 接口提供完整的 `pe_ttm` 与 `pb` 日频历史序列，可直接按季末采样，同时解决两个问题并将窗口扩展至 5 年（20 个数据点）。此外，DCF 与 EPV 方法输出相差约 2 倍（1950 vs 989），在报告中缺乏语义说明，需补充注释告知用户两者含义差异。

## What Changes

- **historical_pb 新增**：在 `TushareFetcher` 中从 `daily_basic` 按季末采样 `pb`，写入 `StockData.historical_pb`；解锁 `PBRelativeValuation`。
- **historical_pe 扩展至 5 年**：同样从 `daily_basic.pe_ttm` 按季末采样（替代 Baostock 仅 2 年），窗口从 8 季扩展至 20 季（5 年）。
- **DCF/EPV 语义注释**：在 `formatters.py` 的价值面报告中，对 `dcf` 与 `epv` 方法分别补充一行语义说明（DCF = 含增长假设的公允价；EPV = 零增长地板价），帮助用户理解两者差异。
- **Baostock historical_pe 保留为 fallback**：Tushare 不可用时降级到 Baostock 2 年数据。

## Capabilities

### New Capabilities

- `tushare-historical-multiples`：通过 Tushare `daily_basic` 提供 historical_pe（5年）和 historical_pb（5年），按季末采样。

### Modified Capabilities

- `valuation-relative`：`PBRelativeValuation` 从 Not Applicable 变为 Applicable（数据补全）；`PERelativeValuation` 数据窗口扩展，均值更稳定。
- `value-data-provider`：`historical_pb` 字段从「始终 None」变为「Tushare 提供」；`historical_pe` 来源从 Baostock（2年）迁移至 Tushare（5年，带 Baostock fallback）。
- `cli-report-value`：DCF 与 EPV 方法行补充语义说明行。

## Impact

- `src/data_provider/tushare/fetcher.py`：新增 `_fetch_historical_multiples()` 方法
- `src/data_provider/tushare/field_mapping.py`：不需改动（使用已有 `daily_basic` 拉取路径）
- `src/apps/formatters.py`：value report 中 DCF/EPV 行补充注释
- `test/data_provider/` 新增 Tushare historical_pe/pb 单测
- `docs/mrd/features/value-analysis.md`：变更记录与已知缺口更新
