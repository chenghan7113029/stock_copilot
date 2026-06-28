## ADDED Requirements

### Requirement: Tushare income 接口提供年度财务数据
`TushareFetcher.fetch_fundamentals` SHALL 在有权限时，从 `income` 接口取最近一个完整年度（end_date 以 12 月底结尾）的营业收入、归母净利润、营业利润。

#### Scenario: income 接口返回数据
- **WHEN** Tushare `income(ts_code, limit=8)` 调用成功
- **THEN** 优先取 `end_date` 以 `1231` 结尾的最新行（年报），写入 `revenue`、`net_income`（归母净利润）、`ebit`（营业利润）

#### Scenario: 仅有季报数据
- **WHEN** 最近 8 期中无年报（均为季报）
- **THEN** 取最近一期季报，`revenue` 等字段写入，并在 `missing_fields` 中标注「annual_income_unavailable」

#### Scenario: income 接口无权限
- **WHEN** 接口返回权限错误
- **THEN** `_try_fetch` 返回 None，income 字段不写入，不抛出异常，回退到 Baostock 数据
