## ADDED Requirements

### Requirement: `report portfolio` 严格离线组合报告
CLI SHALL 新增 `python -m apps.cli report portfolio [--code <code>] [--add-quantity <n>] [--json] [--output]` 子命令，严格离线（不发起网络请求，仅读取本地 `TradeRecord`/`stock_snapshots` 缓存）。不带 `--code` 时展示当前组合整体的集中度与行业分布；带 `--code` 时额外展示该标的当前占比与（若提供 `--add-quantity`）加仓后的边际影响模拟，输出 MUST 包含"以下为模拟计算，不代表任何实际交易操作"提示。

#### Scenario: 组合整体概览
- **WHEN** 执行 `python -m apps.cli report portfolio`
- **THEN** SHALL 输出当前组合的单票占比排行、前 3 大持仓占比、行业分布概览

#### Scenario: 指定标的的边际影响模拟
- **WHEN** 执行 `python -m apps.cli report portfolio --code 600519 --add-quantity 500`
- **THEN** SHALL 输出 `600519` 当前占比、模拟加仓 500 股后的新占比、行业暴露度变化，且 SHALL 包含模拟性质的固定提示

#### Scenario: 无持仓时的提示
- **WHEN** 当前无任何未平仓持仓
- **THEN** SHALL 输出"[error] 当前无持仓记录，请先使用 trade record 录入交易"，与既有无缓存报错风格一致
