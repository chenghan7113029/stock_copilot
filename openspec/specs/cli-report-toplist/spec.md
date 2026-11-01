# cli-report-toplist Specification

## Purpose
TBD - created by archiving change add-top-list-sentiment. Update Purpose after archive.
## Requirements
### Requirement: `report toplist` 严格离线输出龙虎榜区块
CLI SHALL 新增 `python -m apps.cli report toplist <code> [--json] [--output] [--quiet]` 子命令，严格离线（不发起网络请求），调用 `TopListAnalyzer.analyze_offline(code)`，输出「龙虎榜/席位」独立区块（近 90 日上榜次数与活跃度、最近上榜日、净买额与分档、机构席位净买与参与方向、上榜理由分类、覆盖水位）。文本输出 SHALL 固定包含「龙虎榜为观察维度，不构成买卖建议」的提示。

#### Scenario: 成功输出龙虎榜区块
- **WHEN** 本地已有该股上榜缓存，执行 `report toplist 600519`
- **THEN** 输出 SHALL 含上榜次数、最近上榜日净买额、理由分类，且含固定提示文案

#### Scenario: --json 输出结构化字段
- **WHEN** 执行 `report toplist 600519 --json`
- **THEN** JSON SHALL 至少含 `code`、`appearance_count`、`active_level`、`latest_trade_date`、`latest_net_amount`、`inst_net_buy`、`reason_categories`、`warnings`

#### Scenario: 无缓存时明确报错
- **WHEN** 本地无该股龙虎榜缓存
- **THEN** SHALL 输出「[error] 未找到 <code> 的龙虎榜数据，请先运行 sync」，退出码非 0，风格与 `report fundflow`/`report events` 一致

### Requirement: 龙虎榜区块在 dual/dashboard 中独立展示
当 `DualTrackReport.top_list_result` 非空时，`report dual` 与 `report dashboard` 的人类可读输出 SHALL 包含「龙虎榜/席位」区块（复用 `TopListResult` 字段），并固定附「观察维度」提示。该区块 SHALL 独立于 `combined_signal`，MUST NOT 改变 `SignalFusion.fuse()` 的输出。

#### Scenario: dual 输出含龙虎榜区块
- **WHEN** `report dual 600519` 且 `top_list_result` 非空
- **THEN** 输出 SHALL 在价值面/技术面/情绪面/资金面/事件面区块之外包含可识别的「龙虎榜/席位」区块

#### Scenario: 缺失时显式降级
- **WHEN** `top_list_result is None`
- **THEN** dual/dashboard SHALL 显式说明「龙虎榜数据缺失（请先运行 sync）」或省略该区块，`combined_signal` SHALL 不受影响

