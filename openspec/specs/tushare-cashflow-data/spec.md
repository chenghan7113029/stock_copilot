## Purpose

Tushare Pro `cashflow` 接口接入：真实 FCF、资本支出、折旧摊销。

## Requirements

### Requirement: Tushare cashflow 接口提供真实 FCF 推导数据
`TushareFetcher.fetch_fundamentals` SHALL 从 `cashflow` 接口取经营活动现金流、资本支出、折旧摊销，并通过 `_derive_fcf` 推导真实 FCF。

#### Scenario: cashflow 接口返回完整数据
- **WHEN** Tushare `cashflow(ts_code, limit=8)` 调用成功且包含 `n_cashflow_act` 和 `c_pay_acq_const_fiolta`
- **THEN** `fcf = n_cashflow_act - abs(c_pay_acq_const_fiolta)`，同时写入 `capex`、`depreciation`（`depr_fa_cog_dp`）

#### Scenario: 仅有 OCF 无 capex
- **WHEN** `n_cashflow_act` 有值但 `c_pay_acq_const_fiolta` 为 None 或 0
- **THEN** `fcf = n_cashflow_act`（等同 OCF），写入 warning：`"FCF derived from OCF only, capex unavailable"`

#### Scenario: cashflow 接口无权限
- **WHEN** 接口返回权限错误
- **THEN** 回退到 Baostock FCF 推导链（层 A 逻辑），不抛出异常
