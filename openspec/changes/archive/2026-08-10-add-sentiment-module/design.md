## Context

价值面（`service/value/`）与技术面（`service/tech/`）均已交付并通过 `DualTrackAnalyzer`（`src/service/dual_track/analyzer.py`）融合为 `DualTrackReport`（`combined_signal` + `value_rating`）。情绪面是 MRD 三维分析框架中唯一尚未建设的一维（`product-overview.md` §4.2）。

与价值面/技术面不同，情绪面在方法论上有两个特殊性，直接影响本 change 的架构决策：

1. **数据颗粒度不同**：价值面/技术面数据均按 `(code, source, report_period)` 或 `(code, trade_date)` 组织（`StockSnapshot`、`Kline`），是**个股级**数据；而涨跌停家数、恐慌贪婪指数是**市场级**（全市场当日统计），不因 `code` 不同而不同。融资融券余额虽可细至个股，但 V1 收敛范围不含个股融资余额（见 Open Questions）。这意味着情绪面的数据缓存表结构与既有的按 code 分区模式不同，需要新的按交易日分区的市场级表。
2. **MRD 硬约束**：`product-overview.md` §5.1.3 明确「强制标注须与技术+价值联合解读」「禁止单独作为买卖唯一依据」。这不是一条可选建议，而是产品级红线，必须在架构上落地，而不是留给 prompt/文档约定。

`docs/agent-engineering-quality.md` 与 `docs/dev/engineering-conventions.md` §9 要求「情绪面：情绪分位、极端贪婪/恐惧等级」属于确定性计算核输出，禁止 LLM 生成或修改——因此 `SentimentAnalyzer` 与价值面/技术面一样，是纯规则/统计计算模块，联合解读文本也是规则拼接（复用 `dual_track/analyzer.py` 现有 `build_analysis_summary()` 模式），不引入 LLM。

## Goals / Non-Goals

**Goals:**
- 提供确定性、可测试的 `SentimentAnalyzer`，V1 覆盖 2 个核心指标（涨跌停家数比、恐慌贪婪代理指数）
- 情绪面结果**始终**与价值面/技术面一起呈现，架构上不存在"情绪面独立报告"这条路径能绕开联合解读
- 新增市场级数据缓存表与 Fetcher，遵循既有 `data_provider/` Fetcher 模式（`BaseFetcher`、`FetchResult`、`retry_with_backoff`）
- 遵循既有 `sync`/`report` 分离原则（`add-cli-core` D-1）：`sync market` 联网写缓存，`report sentiment` 严格离线

**Non-Goals:**
- 不实现融资融券个股余额明细、龙虎榜、认沽认购比、社媒/新闻文本挖掘（V1 明确排除，见 Open Questions）
- 不修改 `SignalFusion.fuse()` 的既有数值融合算法（`combined_signal`/`value_rating` 计算逻辑不变）；情绪面在 V1 仅通过 `warnings` 与联合解读文本呈现，不参与数值融合
- 不引入 LLM：情绪等级判断、联合解读文本均为规则/模板生成
- 不做重命名：`DualTrackAnalyzer`/`DualTrackReport` 类名保持不变（见决策 1）
- 不实现社交媒体舆情爬取或 NLP 情感分析基础设施

## Decisions

### 决策 1：架构对齐方式——扩展现有 `DualTrackAnalyzer`，不重命名为 `TripleTrackAnalyzer`

这是本 change 的核心决策点。

**选择**：保持 `DualTrackAnalyzer`/`DualTrackReport` 类名与既有 CLI 契约（`report dual`）不变，新增 `sentiment_result: SentimentAnalysisResult | None` 字段；`analyze_offline()`/`analyze()` 内部新增第三次编排调用（`SentimentAnalyzer.analyze_offline(code)`），并扩展 `build_analysis_summary()` 生成的联合解读文本，使其**总是**包含情绪面段落（若情绪面计算失败则显式提示"情绪面数据缺失，本次报告仅基于价值+技术双维"，而不是静默省略）。

**理由**：
- `report dual` 是已交付并被 `red-blue-confrontation` Skill（`EvidenceBucketer`、`.cursor/skills/red-blue-confrontation/`）消费的稳定 CLI 契约。重命名为 `report triple` 或将 `DualTrackReport` 改名，会级联影响：CLI 参数解析、`EvidenceBucketer` 的类型签名与既有单测、已归档 spec（`openspec/specs/dual-track-analyzer/`、`openspec/specs/cli-report-dual/`）中对 `DualTrackReport` 的引用、Skill 的输入契约文档。这些改动与本 change 的核心目标（接入情绪面数据）无关，属于不必要的破坏性变更半径扩大。
- 保留字段追加式扩展（`sentiment_result` 为新增可选字段）符合 `add-red-blue-confrontation` 已验证的模式（`analyze_offline()` 当初也是以"新增方法，不改变既有 `analyze()` 行为"的方式引入）。
- "双轨"这个名字虽然在语义上不再精确覆盖三维，但保持稳定契约的收益（不破坏红蓝对抗、不破坏现有测试与已归档 spec）远大于命名精确性的收益。若未来 Web UI 阶段需要向用户展示"三维分析"品牌概念，可以在展示层（前端文案）使用"三维"措辞，不要求底层类名同步改名。

**备选方案**：
- **方案 A（拒绝）：重命名为 `TripleTrackAnalyzer`/`TripleTrackReport`**，语义更准确，但需要同步处理：`apps/cli.py` 的 `report dual` 子命令是否保留别名、`EvidenceBucketer` 类型签名迁移、已归档 spec 的历史引用如何处理（OpenSpec 归档后的 spec 是既定事实记录，不应因后续改名而回溯修改）。改名的"正确性收益"在 V1 阶段不足以覆盖这些破坏性成本，故拒绝；留作未来专项 rename change（如果确有强烈的产品侧命名统一诉求）。
- **方案 B（拒绝）：情绪面完全独立，不接入 `DualTrackReport`，仅提供独立 `report sentiment` 命令**，直接违反 MRD §5.1.3 硬约束（"禁止单独作为买卖唯一依据"、"须与技术+价值联合解读"），拒绝作为唯一入口。
- **方案 C（部分采纳，作为方案的从属设计）**：保留 `report sentiment <code>` 独立子命令用于调试/单独查看情绪面数值，但输出中强制打印"⚠ 情绪面结论不得单独作为买卖依据，请结合 `report dual <code>` 查看联合解读"的固定提示（非 LLM 生成，硬编码字符串常量），使其在架构上仍然"依附于"三维联合解读的叙事，而不是被包装成一个看起来完整独立的分析产物。

### 决策 2：V1 指标范围——涨跌停家数比 + 恐慌贪婪代理指数，其余延后

**选择**：V1 仅实现 2 个指标：

| 指标 | 计算方式 | 数据来源（待验证） |
|------|---------|---------------------|
| 涨跌停家数比 | `limit_up_count / (limit_up_count + limit_down_count)`（当日全市场统计），极端值（如 > 0.9 或 < 0.1）判定为情绪极端 | AKShare 市场活动统计接口（候选：`stock_market_activity_legu`，**需实现时验证字段名与可用性**） |
| 恐慌贪婪代理指数（0–100） | 复合评分：涨跌停家数比（权重待定，V1 建议 0.5）+ 两融余额环比变化率（权重 0.3，**若数据不可得则该分量置 None 并按剩余分量归一化重新加权，不因单一分量缺失导致整体指标不可用**）+ 全市场换手率分位（权重 0.2） | AKShare 融资融券余额接口（候选：`stock_margin_underlying_info_szse`/`stock_margin_sse`，**需验证**）+ 全市场成交额/换手率接口（**需验证**） |

**理由**：
- 涨跌停家数比是最直接、最少依赖外部字段的市场广度指标，只需要一次市场级 API 调用即可获得，实现成本最低、可验证性最强，作为 V1 的"最小可用情绪信号"。
- A 股无官方"恐慌贪婪指数"（不同于 CNN Fear & Greed Index 针对美股），MRD 提到的"恐慌贪婪指数"在 A 股语境下只能是**自建代理指标**。V1 采用简单加权复合评分而非训练模型/机器学习方法，保持确定性、可解释、可单测。
- 融资融券、龙虎榜、认沽认购比、社媒文本挖掘等方法论范围广、部分依赖非结构化文本（社媒舆情属于自然语言处理，与"确定性计算核"的定位冲突，需要额外的 NLP/情感分析 pipeline，工作量与本 change 目标不匹配），V1 明确排除，留待后续 change（如未来 `add-sentiment-margin-detail`、`add-sentiment-social-nlp`）分别立项。

**备选方案**：
- 一次性实现 MRD §5.1.3 列出的全部方法论（融资融券 + 涨跌停 + 恐慌贪婪 + 文本挖掘 + 龙虎榜）——拒绝，这正是 roadmap 标注"整模块"级别工作量的来源，一个 change 承载过多独立数据源接入与算法设计，验收周期长、评审困难，任何一个子模块延期都会阻塞整体交付。
- 只做涨跌停家数比，不做恐慌贪婪代理指数——拒绝，MRD 用户故事 US-03（"大涨后想追涨，情绪量化显示极端贪婪"）明确期望一个可读的情绪等级/指数而非仅一个比率，两个指标搭配（一个直接市场信号 + 一个复合代理指数）能更好覆盖 US-01/US-03 场景。

### 决策 3：数据持久化——新增市场级快照表，不复用 `stock_snapshots`

**选择**：新增 `MarketSentimentSnapshot` ORM（主键 `trade_date`，非 `(code, source, report_period)`），字段包含 `limit_up_count`、`limit_down_count`、`up_count`、`down_count`、`margin_balance_change_pct`（可空）、`turnover_percentile`（可空）、`fear_greed_index`、`fetched_at`。

**理由**：`stock_snapshots` 的唯一键 `(code, source, report_period)` 假设数据总是归属于某个具体股票；市场级数据没有自然的 `code`，硬塞一个占位符（如 `code="__MARKET__"`）会污染既有表的语义与索引，且未来若要查询"某日市场情绪"，用占位符 code 过滤是反直觉的。新建一张按交易日为主键的轻量表更符合数据本质，也符合 `Kline` 表按 `(code, trade_date)` 为主键的既有先例（本表可视为 `Kline` 模式的市场级变体：主键退化为仅 `trade_date`）。

**备选方案**：复用 `stock_snapshots` 并用固定占位 `code`/`source="sentiment_market"` —— 拒绝，会让 `stock_snapshots` 的既有查询逻辑（按 `code` 索引、`StockDataProvider._pick_quote_snapshot` 等）需要特殊分支处理市场级数据，增加既有价值面数据管道的复杂度和误用风险。

### 决策 4：联合解读文本的生成方式——规则模板，不引入 LLM

**选择**：`build_analysis_summary()` 扩展一段"情绪面"文本，规则示例：
- `market_sentiment_status == 极度贪婪` 且 `tech_result.trend_status ∈ {强势多头}` → 追加"⚠ 情绪面极度贪婪叠加技术面强势，注意钝化与回调风险，不建议仅因情绪指标追高"
- `market_sentiment_status == 极度恐慌` 且 `value_result.assessment == 低估` → 追加"市场极度恐慌但价值面显示低估，符合『恐慌中寻找便宜筹码』的逆向逻辑，但仍需技术面企稳信号确认"
- 其余组合走通用联合解读模板："情绪面：{status}（指数 {score}），须结合价值面『{assessment}』与技术面『{trend_status}』综合判断，不单独作为买卖依据"

**理由**：`docs/agent-engineering-quality.md` 明确"业务叙述"可以用 LLM，但情绪面的联合解读属于**产品护栏级别的强制免责声明与规则化提示**，不是自由创作型叙事；用规则保证 100% 可控、可单测、零 token 成本，且不会因 LLM 幻觉遗漏"须联合解读"这句法律/合规意义上的关键提示。红蓝对抗式的开放叙事已经用 Cursor Skill 承接，本 change 的联合解读是更基础、更刚性的一层，不适合复用同样的模式。

**备选方案**：接入已冻结的 `add-llm-narrative-core` 的 `narrate()` 生成联合解读——拒绝，理由与 `add-red-blue-confrontation` 一致（个人 Cursor 场景下引入 LLM API 的工程成本与当前收益不匹配），且联合解读的"必须包含警示语"这一刚性约束用规则实现比用 LLM+grounded 校验更简单可靠。

## Risks / Trade-offs

- **[风险] AKShare 候选接口（`stock_market_activity_legu`、`stock_margin_underlying_info_szse` 等）命名基于常见接口推测，实现时可能不存在或字段结构不同** → **缓解**：`design.md` 已标注"需实现时验证"；`AkshareSentimentFetcher` 参照既有 `AKShareFetcher` 的异常处理模式（`retry_with_backoff` + 捕获异常返回 `FetchResult(error=...)`），任一分量接口不可用时该分量记为 `None` 并从复合指数权重中剔除、重新归一化，不因单一接口失效导致整个情绪面模块不可用；`tasks.md` 第一节包含"实现前先用 `python -c` 验证候选接口可用性并记录实际字段名"的任务。
- **[风险] 恐慌贪婪代理指数的权重（0.5/0.3/0.2）是主观拍定，缺乏历史回测校准** → **缓解**：V1 明确标注该指数是"自建代理指标"而非行业标准指标，`SentimentAnalysisResult.warnings` 中固定包含"⚠ 恐慌贪婪指数为自建代理指标，非官方标准，权重未经历史回测校准"提示；权重定义为模块内可调常量（不写入用户配置，避免过度设计），后续若有真实历史数据可重新校准。
- **[风险] "禁止单独作为买卖唯一依据"这一硬约束目前主要靠架构设计（情绪面必须嵌入 `DualTrackReport`）落地，而 CLI 用户理论上仍可以只调用 `report sentiment` 而不看 `report dual`** → **缓解**：`report sentiment` 输出强制携带不可关闭的警示文案（决策 1 方案 C）；根本解决（如强制用户先看双轨报告才能看情绪面）涉及产品交互流程设计，超出 CLI 阶段能力范围，留给未来 Web 阶段的决策护航流程统一处理。
- **[风险] 市场级数据（涨跌停家数、恐慌贪婪指数）每日只需拉取一次，但 `sync market` 若被误认为要按 code 调用会造成困惑** → **缓解**：CLI 帮助文本与 `docs/dev/engineering-conventions.md` 明确说明 `sync market` 不接受 `<code>` 参数，是全市场级同步命令；`report sentiment <code>` 内部读取的是最新一条市场级快照（与 `code` 参数无关，`code` 仅用于报告标题与未来"个股融资余额"扩展预留）。

## Migration Plan

- 纯新增能力，`DualTrackReport.sentiment_result` 为新增可选字段（`| None`，默认可为 `None`），不影响任何现有反序列化/格式化代码路径（`format_dual_report` 等既有函数不读取该字段则行为不变，本 change 会同步扩展格式化函数以展示新字段，但既有字段的既有展示逻辑不变）
- 新表 `market_sentiment_snapshot` 由 `Base.metadata.create_all()` 自动建表，无需 `ensure_sqlite_schema` 补丁（表全新，非既有表加列）
- 回滚：删除 `src/service/sentiment/`、`src/data_provider/sentiment/`、`MarketSentimentSnapshot` 模型与 `market_sentiment_repo.py`，撤销 `DualTrackReport.sentiment_result` 字段与 CLI 子命令即可；不影响价值面/技术面/双轨既有功能

## Open Questions

- 个股融资融券余额明细（非市场级聚合）是否需要在 V1.1 补充？—— 暂不做决定，待 V1（涨跌停+恐慌贪婪）验证数据源稳定性与用户实际使用反馈后再评估是否值得增加个股级情绪维度（会引入新的 `(code, trade_date)` 级数据表）。
- 龙虎榜、认沽认购比数据源与算法设计——留待独立后续 change（V1 不做接口调研）。
- 社媒/新闻文本挖掘情绪分析——需要 NLP/情感分析能力，可能涉及 LLM（文本理解属于"代码做不了"的任务类别），若未来立项应作为独立 change 明确评估是否需要解冻 `add-llm-narrative-core`，本 change 不预先设计。
- 恐慌贪婪代理指数的具体权重与分档阈值（极度恐慌/恐慌/中性/贪婪/极度贪婪的分数区间）留给实现阶段基于真实数据抽样调整，`design.md` 不预先锁定具体数值，仅锁定"3 分量加权、可归一化降级"的计算框架。
