## ADDED Requirements

### Requirement: `report events` 严格离线且输出治理/事件面区块
CLI SHALL 新增 `python -m apps.cli report events <code> [--json] [--output] [--quiet]` 子命令，严格离线（不发起网络请求），调用 `EventAnalyzer.analyze_offline(code)`，输出「治理/事件面」独立区块（近 90 日减持、回购、未来 30 日解禁、质押比例、大宗折价、北向近 5 日净流入）。文本输出 SHALL 固定包含「事件面数据为观察维度，不构成买卖建议」的提示。

#### Scenario: 成功输出治理/事件面区块
- **WHEN** 本地已有该股治理事件缓存，执行 `report events 600519`
- **THEN** 输出 SHALL 包含减持/回购/解禁/质押/大宗相关事实陈述，且 SHALL 包含固定提示文案

#### Scenario: --json 输出结构化字段
- **WHEN** 执行 `report events 600519 --json`
- **THEN** JSON 输出 SHALL 包含 `holder_net_sell_90d`、`pledge_ratio` 等字段，供程序化消费

#### Scenario: 无缓存时明确报错
- **WHEN** 本地无该股治理事件缓存
- **THEN** SHALL 输出「[error] 未找到 <code> 的治理事件数据，请先运行 sync」，退出码非 0

### Requirement: 治理/事件面区块在 dual/dashboard 中独立展示
`DualTrackReport.event_result` 非空时，`report dual` 与 `report dashboard` 的人类可读输出 SHALL 包含「治理/事件面」区块（复用 `EventResult` 字段）。事件面区块 SHALL 独立于 `combined_signal`，MUST NOT 改变 `SignalFusion.fuse()` 输出的数值。

#### Scenario: dual 输出含治理/事件面区块
- **WHEN** `report dual 600519` 且 `event_result` 非空
- **THEN** 输出 SHALL 在价值面/技术面/情绪面/资金面区块之外包含可识别的「治理/事件面」区块

#### Scenario: 事件面缺失时显式降级
- **WHEN** `event_result is None`
- **THEN** dual/dashboard 输出 SHALL 显式说明「治理事件数据缺失」或省略该区块并给出提示，`combined_signal` 计算 SHALL 不受影响
