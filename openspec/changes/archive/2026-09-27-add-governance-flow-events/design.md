## Context

`product-overview.md` §4.3 把 PO-11 列为「待补充信息面」开放项，覆盖三类：宏观政策事件（利率/监管/地缘）、流动性资金面（北向/ETF/轮动）、公司治理重大事件（减持/回购/诉讼）。经与 Owner 确认，本 change 收敛范围为**治理事件 + 流动性资金面**，**明确排除宏观政策事件**（后者是新闻文本 + LLM 范畴，与 PO-14 社媒/新闻文本情绪重叠，且 `tushare-permission-scan.md` 2000 积分档无结构化利率/政策接口）。

`tushare-permission-scan.md` §4.1 已实测 2000 积分档可用：`stk_holdertrade`（股东增减持）、`repurchase`（回购）、`share_float`（限售股解禁）、`pledge_stat`（股权质押）、`block_trade`（大宗交易）、`moneyflow_hsgt`（沪深港通北向资金）。全部为 T+1 或公告驱动的确定性结构化数据，无需 LLM。

`docs/agent-engineering-quality.md` 与 `docs/dev/engineering-conventions.md` §9 要求「价值面/技术面/情绪面」数值由确定性计算核产出。治理事件同理：减持/回购/解禁/质押/大宗是**可结构化的事实**，`EventAnalyzer` 只做事实聚合与风险 flag 判定，不做因果推断或叙事（那属于 LLM/红蓝对抗的职责）。

## Goals / Non-Goals

**Goals:**
- 提供确定性、可测试的 `EventAnalyzer`，覆盖治理事件（减持/回购/解禁/质押/大宗）+ 北向资金（市场级流动性）
- 严格遵循 `sync`/`report` 分离原则：`sync <code>` 联网写缓存，`report events` 严格离线
- 治理/事件面作为独立展示维度，不参与 `signal_score`/`combined_signal` 融合

**Non-Goals:**
- 不做宏观政策事件（利率/监管/地缘）——文本 + LLM 范畴，与 PO-14 重叠，另立 change
- 不做诉讼、商誉减值、违规处罚等非结构化治理事件（数据源不可得或不稳定）
- 不修改 `SignalFusion.fuse()` 既有融合算法；不引入 LLM
- 不做龙虎榜（PO-13）、个股两融/资金流（PO-12，已另立 change）

## Decisions

### 决策 1：数据持久化——按接口分表，不做归一化事件表

**选择**：新增 6 张表：
- `holder_trade`（`code`, `ann_date`, `holder_name`, `holder_type`, `in_de`（增减持方向）, `change_vol`, `change_ratio`）
- `repurchase`（`code`, `ann_date`, `proc`（进度）, `vol`, `amount`）
- `share_float`（`code`, `ann_date`, `float_date`, `float_share`, `float_ratio`）
- `pledge_stat`（`code`, `end_date`, `pledge_ratio`, `unrest_pledge`, `total_share`）
- `block_trade`（`code`, `trade_date`, `price`, `vol`, `amount`, `discount`（相对收盘价折溢价））
- `northbound_flow`（`trade_date`, `north_money`, `south_money`；市场级，仿 `market_sentiment_snapshot`）

**理由**：各接口字段异构，归一化单表会导致大量可空列或 JSON payload（违背「确定性 typed 字段」偏好）；分表与 `Kline`/`ChipDistribution` 先例一致，各 Repo 独立可测。`northbound_flow` 是市场级（无 code），单独成表。

**备选**：归一化 `governance_event` 表 + `event_type` 判别列 + JSON payload——拒绝（JSON 列难单测、难做字段级确定性校验）。

### 决策 2：Provider 复用 Router 能力链 + 批量拉取

**选择**：`EventProvider.from_config(config, repos)` 经 `DataFetcherRouter.fetchers_with_method("fetch_holder_trade")` 等收集 Tushare Fetcher；`sync(code)` 对 5 个治理接口并发/顺序拉取，各接口独立失败降级（保留缓存）；`get_latest(code, offline)` 严格离线读。北向资金走市场级 `fetch_northbound_flow()`（`sync market` 或 `sync` 顺带，实现时定）。

**理由**：5 个接口任一失败不应阻断其余事件同步；`ChipDistributionProvider` 已验证「能力链 + 逐接口降级」模式。

### 决策 3：产出形态——`EventResult` 事实 flag，不做因果叙事

**选择**：`EventResult`（`code`, `holder_net_sell_90d`, `repurchase_active`, `upcoming_unlock_30d`, `pledge_ratio`, `block_trade_discount`, `northbound_net_inflow_5d`, `reasons: list[str]`, `warnings: list[str]`, `data_timestamp`）由 `EventAnalyzer` 输出；`DualTrackReport` 新增 `event_result` 字段，`report dual`/`report dashboard` 追加「治理/事件面」区块；另提供 `report events <code>` 深看命令。

**理由**：与 PO-12 资金面、F-17 筹码分布同范式——**观察维度**不进打分。`reasons` 只陈述事实（「近 90 日董监高净减持 X 万股」「质押比例 52%」「未来 30 日解禁占流通盘 Y%」），把「利好/利空」留给红蓝对抗 Skill / LLM 叙述层，避免确定性模块越界做主观判断。

## Risks / Trade-offs

- **[风险] 5 个接口字段名/返回结构实现时与预期不符** → **缓解**：`tasks.md` 第一节为「实现前逐接口验证字段」，fetcher 对缺失字段返回 `FetchResult(error=...)` 降级。
- **[风险] 一次性接 5 个治理接口使 tasks.md 偏大（~45 项）** → **缓解**：按「数据源验证 → dao → fetcher → analyzer → CLI → E2E」分节推进，每个接口独立成 task，任一接口延期不阻塞其余接口的验收（但 change 归档需全部完成）。
- **[风险] 风险 flag 阈值（如质押 ≥50%、解禁窗口 30 日、减持窗口 90 日）主观拍定** → **缓解**：阈值为模块内可调常量；`reasons` 只做事实陈述，把阈值作为「展示口径」而非「买卖规则」。
- **[风险] 北向资金（`moneyflow_hsgt`）为市场级，与个股治理事件颗粒度不同** → **缓解**：`EventResult` 中北向字段单列并标注「市场级」，不混入个股级 flag。

## Migration Plan

- 纯新增能力：`DualTrackReport.event_result` 为新增可选字段（默认 `None`），既有路径不读取则行为不变；`combined_signal`/`value_rating` 不受影响。
- 新表由 `Base.metadata.create_all()` 自动建表，无需 `ensure_sqlite_schema` 补丁。
- 回滚：删除 `service/event/`、`data_provider/event/`、6 张 ORM 表与 Repo，撤销 `DualTrackReport.event_result` 与 CLI 子命令即可。

## Open Questions

- 北向资金是并入 `sync market`（情绪面市场级路径）还是 `sync <code>` 顺带拉取——实现时按「市场级数据每日拉一次」原则确定，建议并入 `sync market`。
- 治理事件区块在 dual/dashboard 的排版与文案措辞——实现阶段与既有区块对齐后定。
- 「诉讼/违规处罚」等非结构化治理事件是否后续另立 change——本 change 明确不做，留待评估。
