## Context

情绪面 V1（`add-sentiment-module`）已交付市场级快照，但它是**市场级**数据（按 `trade_date` 分区，`market_sentiment_snapshot` 表），不区分个股。PO-12 要求的是**个股级**资金面：两融余额（`margin_detail`）与主力资金流（`moneyflow`），按 `(code, trade_date)` 组织——这与筹码分布（`ChipDistribution`）的数据颗粒度一致，而不同于情绪面的市场级快照。因此本 change 复用 `ChipDistributionProvider` 已验证的「Router 能力链 + 独立 DAO 表 + `from_config` + 离线缓存降级」三件套，而不是扩展 `MarketSentimentProvider`。

`docs/agent-engineering-quality.md` 与 `docs/dev/engineering-conventions.md` §9 要求「情绪面：情绪分位、极端贪婪/恐惧等级」属于确定性计算核输出，禁止 LLM 生成或修改。资金面同理：两融变化、融券突增、主力净流入均为统计/规则计算，`FundFlowAnalyzer` 是纯规则模块，不引入 LLM。

数据源已在 `tushare-permission-scan.md` §4.1 实测（2000 积分档）：`margin_detail`（个股两融明细，含 `rzye` 融资余额 / `rqye` 融券余额 / `rzrqye` 两融余额 / `rzmre` 融资买入 / `rzche` 融资偿还 / `rqyl` 融券余量）、`moneyflow`（个股资金流，含 `net_mf_amount` 净流入额、`buy_elg_amount`/`buy_lg_amount` 特大/大单买入等）。均为 T+1 日度数据。

## Goals / Non-Goals

**Goals:**
- 提供确定性、可测试的 `FundFlowAnalyzer`，覆盖个股两融与主力资金流两个维度
- 严格遵循既有 `sync`/`report` 分离原则（`add-cli-core` D-1）：`sync <code>` 联网写缓存，`report fundflow` 严格离线
- 资金面作为**独立展示维度**呈现，不参与 `signal_score`/`combined_signal` 数值融合（与筹码分布 F-17 同构）

**Non-Goals:**
- 不把个股资金面并入市场级恐慌贪婪指数（指数是市场级代理指标，个股资金面是独立维度）
- 不修改 `SignalFusion.fuse()` 的既有数值融合算法
- 不引入 LLM / 不接 LLM 叙述（资金面结论为确定性规则 + 模板文案）
- 不做龙虎榜（PO-13）、不做北向资金（PO-11 流动性）、不做社媒/新闻文本（PO-14）

## Decisions

### 决策 1：数据持久化——两张独立表，不复用 `stock_snapshots` 或 `market_sentiment_snapshot`

**选择**：新增 `StockMarginDetail`（`code`, `trade_date`, `rzye`, `rqye`, `rzrqye`, `rzmre`, `rzche`, `rqyl`, `rqmcl`, `fetched_at`）与 `StockMoneyFlow`（`code`, `trade_date`, `net_mf_amount`, `buy_elg_amount`, `sell_elg_amount`, `buy_lg_amount`, `sell_lg_amount`, `fetched_at`）两张表，主键 `(code, trade_date)`，各配 Repo。

**理由**：`margin_detail` 与 `moneyflow` 字段集合不同、更新频率相同但语义独立，合入一张表会导致大量可空列与查询歧义；分表与 `Kline`/`ChipDistribution` 的 `(code, trade_date)` 先例一致。`stock_snapshots` 的唯一键 `(code, source, report_period)` 面向财报快照，语义不匹配；`market_sentiment_snapshot` 是市场级无 code，也不匹配。

**备选**：合并为一张 `stock_fund_flow` 宽表——拒绝（字段可空率高、Repo 读写复杂、与分表先例不一致）。

### 决策 2：Provider 复用 `ChipDistributionProvider` 的 Router 能力链模式

**选择**：`FundFlowProvider.from_config(config, repos)` 通过 `DataFetcherRouter.fetchers_with_method("fetch_margin_detail")` / `("fetch_moneyflow")` 收集 Tushare Fetcher；`get_latest(code, offline)` 优先缓存，联网失败降级到本地缓存（返回 `(data, warnings)`）。

**理由**：`ChipDistributionProvider` 已把「Router 能力链 + 超时保护 + 缓存降级」走通，复用同一范式零新增架构；`from_config` 按 Router 启用情况实例化，天然遵守「阶段 C 退役 AKShare」约束（不无参构造 AKShareFetcher）。

### 决策 3：产出形态——独立 `FundFlowResult` + 独立展示区块，不进融合

**选择**：`FundFlowResult`（`code`, `margin_balance_change_pct`, `short_balance_change_pct`, `main_net_inflow_5d`, `leverage_direction`, `reasons: list[str]`, `warnings: list[str]`, `data_timestamp`）由 `FundFlowAnalyzer` 输出；`DualTrackReport` 新增 `fund_flow_result` 字段，`report dual`/`report dashboard` 追加「个股资金面」区块；另提供 `report fundflow <code>` 深看命令。

**理由**：用户已确认「独立展示区块（像筹码分布）」。资金面是**观察维度**而非**买卖信号**，纳入 `combined_signal` 融合会让一个尚未校准的代理信号污染已稳定的技术面评分，违背「确定性 + 可解释」原则。与筹码分布 F-17 的处理一致（独立字段 + 风险文案，不参与打分）。

**备选**：喂入个股级情绪子分并参与评分——拒绝（PO-12 输出决策已定「独立展示」，且信号权重未经回测，不应进入融合）。

## Risks / Trade-offs

- **[风险] `margin_detail`/`moneyflow` 字段名或返回结构在实现时与预期不符** → **缓解**：`tasks.md` 第一节为「实现前用 `scripts/` 临时脚本验证接口字段」，fetcher 对缺失字段用 `FetchResult(error=...)` 降级，不因单一字段缺失失败。
- **[风险] `sync <code>` 追加两个接口后单票同步变慢（每票 +2 次 API 调用）** → **缓解**：资金面拉取与筹码分布一样放在价值面 + K 线提交之后、独立 `session.commit()`，失败/超时不回滚前面的成果；`--quiet` 下静默降级。
- **[风险] 阈值（如融券突增、主力净流入 5 日累计）主观拍定，缺乏回测** → **缓解**：阈值定义为模块内可调常量，不写用户配置；`FundFlowResult.reasons` 只做「事实陈述」（余额变化 X%、净流入 Y 元），把「利好/利空」留给展示层的风险文案，避免过度解读。

## Migration Plan

- 纯新增能力：`DualTrackReport.fund_flow_result` 为新增可选字段（默认 `None`），既有反序列化/格式化路径不读取则行为不变；`combined_signal`/`value_rating` 计算不受影响。
- 新表 `stock_margin_detail`/`stock_moneyflow` 由 `Base.metadata.create_all()` 自动建表，无需 `ensure_sqlite_schema` 补丁。
- 回滚：删除 `service/fundflow/`、`data_provider/fundflow/`、两张 ORM 表与 Repo，撤销 `DualTrackReport.fund_flow_result` 与 CLI 子命令即可。

## Open Questions

- 资金面区块在 `report dual`/`report dashboard` 中的排版位置与文案措辞——留待实现阶段与既有区块对齐后定，不预先锁定。
- 是否需要历史序列（如近 20 交易日两融余额曲线）——V1 只取最近 5 个交易日做变化量，历史序列可视化留待 Web 阶段。
