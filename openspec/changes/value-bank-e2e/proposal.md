## Why

银行原型（`bank`）估值需要 `net_interest_margin`（净息差）、`npl_ratio`（不良贷款率）、`provision_coverage`（拨备覆盖率）三个银行专项指标，当前这三个字段全部为 None。银行股应使用 PE 相对法 + DDM + EV/EBITDA 评分，但由于银行专项字段缺失，`BankPrototypeAdapter` 无法正常提供有效输入，导致银行原型 E2E 实际路径未经验证。

以工商银行（601398）为基准进行 E2E 验证，确保银行原型从 sync → offline report 完整可跑，且银行关键指标有合理值。

## What Changes

- **银行专项字段接入**：Tushare 的 `fina_indicator` 接口含 `netprofit_margin` 等；银行专项指标 `net_interest_margin`、`npl_ratio`、`provision_coverage` 需从 Tushare `银行业务数据` 接口（`stk_fin_audit` 或 `bankloans_stats`）或手动 `fina_indicator` 映射获取。
- **bank 原型字段映射**：在 `TushareFetcher` 中确认或新增银行三大指标的字段映射。
- **E2E 集成测试**：以 601398（工商银行）为例，从 sync → offline report，验证银行原型完整路径无错误，主要估值方法可运行。

## Capabilities

### New Capabilities

- `tushare-bank-metrics`：Tushare fetcher 支持拉取银行专项指标（NIM、NPL、拨备）并写入 StockData。

### Modified Capabilities

- `value-prototype-router`：确认银行原型分类规则对 601398 生效（当前可能分类为 `high_dividend` 或 `value_growth`）。
- `value-data-provider`：银行三大字段从「始终 None」变为「可由 Tushare 提供」。

## Impact

- `src/data_provider/tushare/fetcher.py`：新增/修正银行专项指标映射
- `src/service/value/router.py`：确认银行原型分类逻辑正确识别银行股
- `test/service/value/` 新增银行 E2E 测试（offline mock）
- `docs/mrd/features/value-analysis.md`：变更记录更新
