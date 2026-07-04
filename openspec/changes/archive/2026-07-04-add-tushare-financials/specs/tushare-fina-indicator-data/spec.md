## ADDED Requirements

### Requirement: Tushare fina_indicator 提供高质量财务指标
`TushareFetcher.fetch_fundamentals` SHALL 从 `fina_indicator` 接口取每股净资产、ROIC 等基础财务指标。

#### Scenario: fina_indicator 接口返回数据
- **WHEN** Tushare `fina_indicator(ts_code, limit=8)` 调用成功
- **THEN** 写入 `bvps`（`bps`）、`roic`、`roe`（覆盖 Baostock 的 roeAvg）、`operating_margin`（`netprofit_margin`）

#### Scenario: fina_indicator 接口无权限
- **WHEN** 接口返回权限错误
- **THEN** 保留 Baostock 的对应字段，不抛出异常
