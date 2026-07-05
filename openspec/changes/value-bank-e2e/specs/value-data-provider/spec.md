## MODIFIED Requirements

### Requirement: 银行专项字段从始终 None 变为可由 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `net_interest_margin`、`npl_ratio`、`provision_coverage` 合并到 `StockData` 对应属性（优先级：Tushare > Baostock；Baostock 无此字段，不冲突）。

#### Scenario: sync 601398 后银行专项字段非空
- **WHEN** Tushare 启用且 601398 `fina_indicator` 含 `netint_margin`
- **THEN** `StockData.net_interest_margin` 不为 None，可被 bank 原型估值方法使用

#### Scenario: 银行方法缺少 NIM 时优雅降级
- **WHEN** `net_interest_margin = None`（接口无权限或无数据）
- **THEN** 依赖 NIM 的指标评分降级为 Not Applicable，聚合不崩溃
