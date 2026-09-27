# cli-report-fundflow Specification

## Purpose
TBD - created by archiving change add-stock-margin-fundflow. Update Purpose after archive.
## Requirements
### Requirement: `report fundflow` 严格离线且输出个股资金面区块
CLI SHALL 新增 `python -m apps.cli report fundflow <code> [--json] [--output] [--quiet]` 子命令，严格离线（不发起网络请求），调用 `FundFlowAnalyzer.analyze_offline(code)`，输出「个股资金面」独立区块（两融余额变化、融券余额变化、主力资金近 5 日净流入）。文本输出 SHALL 固定包含「资金面数据为观察维度，不构成买卖建议」的提示。

#### Scenario: 成功输出资金面区块
- **WHEN** 本地已有该股两融与资金流缓存，执行 `report fundflow 600519`
- **THEN** 输出 SHALL 包含两融余额变化率、主力资金近 5 日净流入，且 SHALL 包含固定提示文案

#### Scenario: --json 输出结构化字段
- **WHEN** 执行 `report fundflow 600519 --json`
- **THEN** JSON 输出 SHALL 包含 `margin_balance_change_pct`、`main_net_inflow_5d` 等字段，供程序化消费

#### Scenario: 无缓存时明确报错
- **WHEN** 本地无该股资金面缓存
- **THEN** SHALL 输出「[error] 未找到 <code> 的资金面数据，请先运行 sync」，退出码非 0，风格与 `report tech`/`report value` 一致

### Requirement: 资金面区块在 dual/dashboard 中独立展示
`DualTrackReport.fund_flow_result` 非空时，`report dual` 与 `report dashboard` 的人类可读输出 SHALL 包含「个股资金面」区块（复用 `FundFlowResult` 字段）。资金面区块 SHALL 独立于 `combined_signal`，MUST NOT 改变 `SignalFusion.fuse()` 输出的数值。

#### Scenario: dual 输出含资金面区块
- **WHEN** `report dual 600519` 且 `fund_flow_result` 非空
- **THEN** 输出 SHALL 在价值面/技术面/情绪面区块之外包含可识别的「个股资金面」区块

#### Scenario: 资金面缺失时显式降级
- **WHEN** `fund_flow_result is None`
- **THEN** dual/dashboard 输出 SHALL 显式说明「资金面数据缺失」或省略该区块并给出提示，`combined_signal` 计算 SHALL 不受影响

