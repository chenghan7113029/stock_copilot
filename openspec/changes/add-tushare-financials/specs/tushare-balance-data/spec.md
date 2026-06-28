## ADDED Requirements

### Requirement: Tushare balancesheet 提供资产负债数据
`TushareFetcher.fetch_fundamentals` SHALL 从 `balancesheet` 接口取货币资金、短期借款、长期借款、总资产、总负债等字段。

#### Scenario: balancesheet 接口返回完整数据
- **WHEN** Tushare `balancesheet(ts_code, limit=8)` 调用成功
- **THEN** 写入 `total_assets`、`total_liabilities`、`cash`（来自 `money_cap`）、`short_term_debt`（`st_borr`）、`long_term_debt`（`lt_borr`）、`shareholder_equity`

#### Scenario: balancesheet 接口无权限
- **WHEN** 接口返回权限错误
- **THEN** 相关字段不写入，不抛出异常，Piotroski F-Score / Beneish M-Score 因缺少 total_assets 保持 N/A
