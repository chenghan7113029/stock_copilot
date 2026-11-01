# top-list-analyzer Specification

## Purpose
TBD - created by archiving change add-top-list-sentiment. Update Purpose after archive.
## Requirements
### Requirement: TopListAnalyzer 输出确定性龙虎榜分析结果
系统 SHALL 提供 `TopListAnalyzer`（`src/service/toplist/analyzer.py`），暴露 `analyze(code) -> TopListResult` 与 `analyze_offline(code) -> TopListResult | None`。`TopListResult` SHALL 包含 `code`、`appearance_count`（窗口内去重后的上榜交易日数）、`active_level`（活跃度分档枚举）、`latest_trade_date`、`latest_net_amount`（最近上榜日**主导事件**净买额，元；同名日多理由不可相加）、`latest_net_amount_level`（大额净买入/净卖出/中性）、`inst_net_buy`（机构席位净买，可空）、`inst_participation`（机构买入/机构卖出/无机构席位，可空）、`reason_categories: list[str]`、`coverage_trade_days`（水位覆盖的交易日数）、`reasons: list[str]`、`warnings: list[str]`、`data_timestamp`。所有分档与数值 MUST 由代码规则计算，MUST NOT 由 LLM 生成或修改。

#### Scenario: 离线分析返回确定性结果
- **WHEN** 本地有该股上榜记录与覆盖水位，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `TopListResult`，`appearance_count` 等为确定性值，`reasons` 为事实陈述文本

#### Scenario: 无本地缓存返回 None
- **WHEN** 本地无该股龙虎榜记录
- **THEN** `analyze_offline` SHALL 返回 `None`，调用方记录「龙虎榜无本地缓存，请先运行 sync」警告，不抛异常

### Requirement: 上榜频次去重与活跃度分档
统计窗口 SHALL 为最近 `WINDOW_DAYS`（默认 90）自然日。上榜次数 `appearance_count` SHALL 按去重后的 `(trade_date)` 计数（同一交易日多条 `reason` 只计一次）。活跃度分档 SHALL 为：`0` → 未上榜、`1–2` → 偶发、`>= ACTIVE_MIN_APPEARANCES`（默认 3）→ 活跃。

#### Scenario: 同日多条理由只计一次
- **WHEN** 该股在窗口内有 2 个交易日上榜，其中一天同时命中「涨幅偏离」与「连续三日累计」两条理由
- **THEN** `appearance_count` SHALL 为 `2`

#### Scenario: 达到阈值判为活跃
- **WHEN** `appearance_count = 3` 且 `ACTIVE_MIN_APPEARANCES = 3`
- **THEN** `active_level` SHALL 为「活跃」

### Requirement: 净买额与机构席位口径
最近上榜日净买额 `latest_net_amount` SHALL 取该日「主导上榜事件」的 `net_amount`（主导事件 = `l_amount` 最大者，并列按 `reason` 稳定选择）；MUST NOT 对该日全部 `reason` 行求和（实测同日不同理由金额不同，求和会重复计算）；`>= LARGE_NET_BUY_10K`（默认 5000 万元）记「大额净买入」，`<= -LARGE_NET_BUY_10K` 记「大额净卖出」，其余记「中性」。机构口径 SHALL 只统计 `exalter` 含「机构专用」的席位：`inst_net_buy = Σ(buy - sell)`，并据符号判定「机构买入 / 机构卖出 / 无机构席位」；`top_inst` 无数据时相关字段 SHALL 为 `None` 且不得输出机构结论。MUST NOT 依据席位名称推断「游资」身份。

#### Scenario: 大额净买入判定
- **WHEN** 最近上榜日 `net_amount` 合计为 `68,000,000` 元（6800 万元）
- **THEN** `latest_net_amount_level` SHALL 为「大额净买入」

#### Scenario: 机构席位净买
- **WHEN** 最近上榜日机构席位 `buy=1.2e8`、`sell=4.0e7`
- **THEN** `inst_net_buy` SHALL 为 `8.0e7`，`inst_participation` SHALL 为「机构买入」

#### Scenario: 无机构席位数据时不下结论
- **WHEN** `top_inst` 数据缺失（权限不足）
- **THEN** `inst_net_buy` 与 `inst_participation` SHALL 为 `None`，`warnings` 说明机构维度缺失，`reasons` MUST NOT 出现任何机构买卖陈述

### Requirement: 上榜理由分类与覆盖不足显式告警
系统 SHALL 将 `reason` 文本按关键词常量表归类为：涨幅偏离、跌幅偏离、换手率、振幅、连续三日累计、其他（按此优先级匹配）；`reason_categories` SHALL 去重并按固定顺序输出。当水位覆盖的交易日数不足以覆盖统计窗口时，`warnings` SHALL 显式说明覆盖区间与天数，MUST NOT 把「未拉取」表述为「未上榜」。

#### Scenario: 理由归类
- **WHEN** `reason` 为「日涨幅偏离值达到7%的前五只证券」与「连续三个交易日内，涨幅偏离值累计达到20%的证券」
- **THEN** `reason_categories` SHALL 含「涨幅偏离」与「连续三日累计」

#### Scenario: 振幅类理由单独归类
- **WHEN** `reason` 为「日振幅值达到15%的前5只证券」
- **THEN** `reason_categories` SHALL 含「振幅」

#### Scenario: 覆盖不足告警
- **WHEN** 统计窗口内本地仅覆盖 2 个交易日且该股未上榜
- **THEN** `appearance_count` SHALL 为 `0`，`warnings` SHALL 说明「龙虎榜仅覆盖 N 个交易日（起~止），上榜次数可能偏低」

### Requirement: 龙虎榜结果不参与数值融合与 LLM 输入
`TopListResult` SHALL 只作为观察维度展示；MUST NOT 参与 `signal_score`、`combined_signal`、`value_rating` 的计算，MUST NOT 进入 LLM ContextPack / grounding 输入字段。

#### Scenario: 融合结果不受影响
- **WHEN** 同一 `code` 与同一价值/技术输入，分别在有无龙虎榜数据时调用 `DualTrackAnalyzer.analyze_offline`
- **THEN** `combined_signal` 与 `value_rating` SHALL 完全一致

