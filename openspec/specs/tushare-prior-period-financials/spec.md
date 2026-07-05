# tushare-prior-period-financials Specification

## Purpose

Tushare fetcher 拉取 prior 年度（当期年报 1231 减一年）财报，推导 Piotroski / Beneish 所需的 6 个 prior_* 字段。

## Requirements

### Requirement: Tushare 提供上一年度 prior_* 字段
`TushareFetcher` SHALL 在拉取当期年报（`report_period` 以 `1231` 结尾）后，发起 prior 年度（report_period - 1 年）的 `fina_indicator`、`balancesheet`、`income` 查询，计算并写入以下字段到 `FetchResult.data`：

| 字段 | 计算来源 |
|---|---|
| `prior_roa` | prior fina_indicator.roa |
| `prior_debt_ratio` | prior balancesheet: total_liab / total_assets |
| `prior_current_ratio` | prior balancesheet: total_cur_assets / total_cur_liab |
| `prior_shares_outstanding` | prior balancesheet/income: total_share（股，不缩放） |
| `prior_gross_margin` | prior income: (revenue - oper_cost) / revenue；fallback fina_indicator.grossprofit_margin / 100 |
| `prior_asset_turnover` | prior income + balancesheet: revenue / total_assets |

若 prior 年度 API 返回为空或字段缺失，对应字段标注 missing，不报错。

#### Scenario: 当期年报存在时拉取 prior 年度数据
- **WHEN** 最新年报 `report_period = 20251231`，prior 年度 = 20241231
- **THEN** `prior_roa`、`prior_debt_ratio` 等字段均有值，`field_sources[prior_roa] = "tushare"`

#### Scenario: 当期为季报时不拉取 prior 数据
- **WHEN** 最新报告期为 `20260331`（季报），未找到当年年报
- **THEN** prior 年度查询不触发，6 个 prior 字段标注 missing

#### Scenario: prior 年度 API 返回空时不报错
- **WHEN** prior 年度 `fina_indicator` 返回空 DataFrame（数据未上传）
- **THEN** `prior_roa` 等字段标注 missing，整体 fetch 不中断
