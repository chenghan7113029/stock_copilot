## Context

Piotroski F-Score 需要 9 个指标，其中至少 4 个需要同比比较（`prior_roa`、`prior_debt_ratio`、`prior_current_ratio`、`prior_shares_outstanding`）。Beneish M-Score 同样需要 `prior_gross_margin`、`prior_asset_turnover`。

Tushare `income`、`balancesheet`、`fina_indicator` 接口均支持按 `period` 查询特定报告期数据，只需传入上一年度 1231 日期即可获取。

## Goals / Non-Goals

**Goals:**
- 在 TushareFetcher 中新增 prior 年度拉取（单次额外 API 调用）
- 写入 StockData.prior_roa、prior_debt_ratio、prior_current_ratio、prior_shares_outstanding、prior_gross_margin、prior_asset_turnover
- 单测覆盖 mock prior API 调用

**Non-Goals:**
- 不引入 Baostock prior 数据源（Baostock 无历史 period 查询接口）
- 不存储 prior 字段到独立表（快照合并即可）
- 不更改 Piotroski/Beneish 计算逻辑（已有，只补数据）

## Decisions

### 决策 1：prior 年度定义

prior 年度 = 最新年报 `report_period` 减一年（即若最新为 20251231，prior 为 20241231）。

### 决策 2：prior API 调用时机与复用

在 `TushareFetcher.fetch_all()` 中，获取当期年报后，判断 `report_period` 是否为 1231，若是，则用 `report_period - 1 year` 发起 prior 年度的 `fina_indicator` + `balancesheet` + `income` 查询。每次 sync 触发，缓存到快照中。

### 决策 3：prior 字段计算来源

| prior 字段 | 来源 API | 原始字段 |
|---|---|---|
| prior_roa | fina_indicator | `roa` |
| prior_debt_ratio | balancesheet | `total_liab / total_assets` |
| prior_current_ratio | balancesheet | `total_cur_assets / total_cur_liab` |
| prior_shares_outstanding | income/balancesheet | `total_share` |
| prior_gross_margin | income | `(revenue - operate_cost) / revenue` |
| prior_asset_turnover | income + balancesheet | `revenue / total_assets` |

### 决策 4：API 调用限制处理

Tushare `fina_indicator`/`income`/`balancesheet` 接口每分钟调用限制约 100 次；prior 年度多 3 次调用。加 0.3s 间隔（与现有逻辑一致）。

## Risks / Trade-offs

- **[风险] 2000 积分接口限速**：一次 sync 新增 3 个 API 调用，在合理范围内。
- **[权衡] 不存储 prior 年报到独立快照**：prior 字段作为字段值存入当年快照，下次 sync 更新。V1 可接受；V2 可考虑独立存储多年报历史。
