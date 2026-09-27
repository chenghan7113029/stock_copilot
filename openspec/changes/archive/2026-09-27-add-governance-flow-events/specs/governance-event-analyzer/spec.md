## ADDED Requirements

### Requirement: EventAnalyzer 输出确定性治理事件面分析结果
系统 SHALL 提供 `EventAnalyzer`，暴露 `analyze(code) -> EventResult` 与 `analyze_offline(code) -> EventResult | None` 两个方法。`EventResult` SHALL 包含 `code`、`holder_net_sell_90d`（近 90 日净减持，可空）、`repurchase_active`（回购进行中，bool）、`upcoming_unlock_30d`（未来 30 日解禁占比，可空）、`pledge_ratio`（最新质押比例，可空）、`block_trade_discount`（近期大宗折价，可空）、`northbound_net_inflow_5d`（北向近 5 日净流入，市场级，可空）、`reasons: list[str]`、`warnings: list[str]`、`data_timestamp`。所有数值与 flag 判定 MUST 由代码规则计算，MUST NOT 由 LLM 生成或修改。

#### Scenario: 离线分析返回事件面结果
- **WHEN** 本地已有该股治理事件缓存，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `EventResult`，各 flag 为确定性值，`reasons` 含事实陈述

#### Scenario: 无本地事件缓存时返回 None
- **WHEN** 本地无该股治理事件缓存
- **THEN** `analyze_offline` SHALL 返回 `None`，调用方负责记录「治理事件数据缺失，请先运行 sync」警告，不抛异常

### Requirement: 治理风险 flag 的事实性判定
系统 SHALL 按以下确定性规则产出 flag（阈值均为模块内可调常量）：
- 近 90 日减持：`stk_holdertrade` 中 `in_de` 为减持方向且 `ann_date` 在 90 日内的净减持股数
- 回购进行中：`repurchase` 中近 90 日存在 `proc` 为实施/完成状态
- 未来 30 日解禁：`share_float` 中 `float_date` 落在未来 30 日内的解禁股数占流通盘比例
- 质押比例：`pledge_stat` 最新一条的 `pledge_ratio`
- 大宗折价：`block_trade` 近 30 日成交价低于当日收盘价的折价幅度

`reasons` SHALL 只陈述事实（如「质押比例 52%」「未来 30 日解禁占流通盘 3.2%」），MUST NOT 输出「利空」「看空」等结论性判断。

#### Scenario: 高质押只陈述事实
- **WHEN** 最新 `pledge_ratio = 52.0`
- **THEN** `pledge_ratio` SHALL 为 `52.0`，`reasons` 包含「质押比例 52%」的事实陈述，MUST NOT 出现「利空」类结论词

#### Scenario: 减持方向聚合
- **WHEN** 近 90 日有两条减持（合计 -10 万股）与一条增持（+3 万股）
- **THEN** `holder_net_sell_90d` SHALL 为净减持 7 万股（或等价净额表述）

### Requirement: 北向资金近 5 日净流入（市场级）
系统 SHALL 累加最近 5 个交易日的北向净流入（`north_money`）得到 `northbound_net_inflow_5d`，并在 `EventResult` 中标注「市场级」，MUST NOT 混入个股级 flag。数据不足 5 日时按可用交易日累加，`warnings` 说明。

#### Scenario: 北向 5 日累计
- **WHEN** 最近 5 个交易日北向净流入分别为 `+20, -5, +10, +8, -3`（亿元）
- **THEN** `northbound_net_inflow_5d` SHALL 为 `+30`（亿元），且标注市场级

#### Scenario: 数据不足时降级
- **WHEN** 北向仅 2 个交易日数据
- **THEN** SHALL 按 2 日累计返回，`warnings` 说明数据不足 5 日
