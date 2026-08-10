## ADDED Requirements

### Requirement: `report trade-review` 严格离线复盘报告
CLI SHALL 新增 `python -m apps.cli report trade-review [--code <code>] [--json] [--output]` 子命令，严格离线（仅读取本地数据库，不发起网络请求）。不带 `--code` 时 SHALL 统计全部持仓标的；带 `--code` 时 SHALL 仅统计该标的。

#### Scenario: 全量复盘报告
- **WHEN** 执行 `python -m apps.cli report trade-review`
- **THEN** SHALL 输出全部标的的汇总胜率、平均收益率、Badcase 列表（或降级提示）

#### Scenario: 指定标的复盘报告
- **WHEN** 执行 `python -m apps.cli report trade-review --code 600519`
- **THEN** SHALL 仅输出 `600519` 的复盘统计

#### Scenario: 无交易记录时的提示
- **WHEN** 本地无任何 `TradeRecord`
- **THEN** SHALL 输出"[error] 未找到交易记录，请先使用 trade record 录入交易"，与既有无缓存报错风格一致
