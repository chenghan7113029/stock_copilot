# 参考调研：backtest-engine（回测模块）

> 填写者：product-manager（T1 前置）｜模板：`docs/agent-team/templates/reference-research.md`
> 资料目录：`ref/research/backtest-engine/`（本波为空，未新增 clone；`ref/` 不进 git）｜本文件：`docs/design/references/backtest-engine-research.md`（进 git，唯一凭据）

- 变更：`openspec/changes/add-backtest-engine/`
- 覆盖锚点：**飞书《投资Agent》r482 §回测模块·二（八条硬约束）/ 三（A 股五个坑）/ 五（标签与分组）/ 六（部分池化）/ 七（统计陷阱）/ 九（三级门禁）/ 十（MVP 与校准）**
- **MRD 锚点：无**。`docs/mrd/mrd-v1.md` 仍是骨架（§1–§7 全是占位与 TODO），本波没有任何 `MRD-*` 锚点可引用；本文件与 proposal / spec 一律锚到飞书 r482 原文与仓库一手材料。MRD 定稿后由 T7 回填。
- 调研人：product-manager
- 调研日期：2026-11-15
- 结论一句话：**借鉴 A（thesis-backtester）的时点硬过滤、B（ai-hedge-fund）的事件研究统计骨架、C（TradingAgents-CN `scripts/`）的 A 股规则参数位、D（Vibe-Trading）的多重比较校正清单；四者都不提供「A 股撮合（涨跌停 / T+1 / 停牌）+ 后复权」的可复用实现，这部分按飞书 §三 自建；不 COPY 任何代码。**

## 1. 调研问题

| # | 问题 | 挂哪个锚点 | 期望答案形态（一句话/表/算法） |
| --- | --- | --- | --- |
| Q1 | A 股撮合与成本的参数（佣金 / 印花税 / 涨跌停幅度 / 最小交易单位）能否从现成实现抄到口径？ | 飞书 r482 §回测模块·二·#4、三 | 参数名 → 值的表，并标明「参数位可抄、数值需按现行口径复核」 |
| Q2 | 事件研究（条件成立 → 之后 N 日超额分布）的统计骨架有无可复用的确定性结构？ | 飞书 r482 §回测模块·十 | 结构体字段表 + 算法步骤（市场模型 → AR → CAR → 窗口统计 → CI） |
| Q3 | 「按公告日对齐、时点冻结」怎么落地才不产生未来函数？ | 飞书 r482 §回测模块·二·#5、三·财报滞后 | 硬过滤规则清单（字段 → 用哪个日期截断） |
| Q4 | 多重比较校正与「有效样本」（组内相关）在实践中怎么落？ | 飞书 r482 §回测模块·二·#3、七 | 校正方法清单（Bonferroni / Holm / FDR）+ 必须报告的字段 |
| Q5 | 生存偏差所需的退市 / ST / 历史成分名单本地能否取到？ | 飞书 r482 §回测模块·二·#6 | 可得性结论（可得 / 需新增权限 / 不可得 → 报缺口） |

## 2. 结论摘要（读这一段就能决定要不要往下看）

- **可借鉴**：
  1. **时点硬过滤**（`REF-backtest-engine-01`）：财务按 `ann_date` 过滤、股价按 `trade_date <= cutoff`、分红与股东数据同口径——直接映射到 spec 的 R10 / R11。
  2. **事件研究统计骨架**（`REF-backtest-engine-02`）：`MarketModelFit(alpha, beta, r_squared, n_obs)` → 逐日 `daily_ar` → `WindowStats(n_events, mean_car, std_car, t_stat, p_value, ci)`，窗口 `[0,+20]` / `[0,+60]`——直接映射 R17，其「按公告日与报告期差 >45 天剔除走味事件」的前视过滤映射 R11 / R10。
  3. **A 股规则参数位**（`REF-backtest-engine-03`）：T+1、涨跌停（主板 10% / ST 5% / 科创 20%）、最小 100 股、佣金率与 5 元下限、卖出印花税、过户费、交易时段——映射 R7 / R8 的**配置字段设计**，但数值不直接采信（见 §6 风险与 Q4）。
  4. **多重比较校正清单**（`REF-backtest-engine-04`）：Bonferroni / Holm-Bonferroni / FDR-BH，并明确「回测多个策略/因子时校正为强制」——映射 R5。
- **明确不借鉴**：
  - 四者都**没有**「涨跌停封板 → 订单失败顺延」「停牌跳过」「后复权价序列」的实现（对 `thesis-backtester/src` 全量 `grep 涨跌停|limit_up|T+1` 为 0 文件）。这部分按飞书 §三 自建，是 `backtest-engine` 的主要新增逻辑。
  - 不借鉴 `ai-hedge-fund` 的 **iid bootstrap**（它对 CAR 做等概率重采样，未处理组内相关）——本波按 R6 改为 block bootstrap。
  - 不借鉴任何 LLM 选股 / 多 Agent 辩论结构：本 change 不引入 LLM 参与数值计算（`docs/dev/engineering-conventions.md` §9.2）。
  - 不 COPY 任何代码：`thesis-backtester` 为 AGPL-3.0；`TradingAgents-CN` 的 `app/` 与 `frontend/` 为专有许可。
- **对 spec 的影响**：`backtest-engine` 的 R5 / R6 / R10 / R11 / R17 标 `参考依据：REF-backtest-engine-0x`；其余 14 条只锚飞书原文。
- **不落地的参考**：`REF-backtest-engine-01` 的 AGPL 代码本身（只借口径）；`REF-backtest-engine-03` 的费率数值（只借字段位）。

## 3. 参考条目

> 全部为**既有本地快照**，本波 0 次 clone（本机 `git ls-remote` / `fetch` 对 GitHub 不可用，见 `docs/agent-team/ENV.md` §外部网络）。因此「复现命令」写为本地定位命令；commit SHA 取自本地 `.git`。

| REF-ID | 名称 | 类型 | 来源 URL | commit SHA / 抓取日期 | 许可证 | 体积 | 存放路径 | 复现命令 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `REF-backtest-engine-01` | thesis-backtester | repo | https://github.com/turtlequant/thesis-backtester | `3ea3a6cbd48f7b44ba3c3d97219296fccb2d282f`（2026-08-19） | AGPL-3.0 | 8.5 MB / 286 文件 | `ref/thesis-backtester/`（既有快照） | `git -C ref/thesis-backtester rev-parse HEAD` |
| `REF-backtest-engine-02` | ai-hedge-fund（event study 模块） | repo | https://github.com/virattt/ai-hedge-fund | `eff8a7320fcf0b473b135690fa1a5b0d9b022a83`（2026-08-07） | MIT | 0.8 MB / 93 文件 | `ref/ai-hedge-fund/`（既有快照） | `sed -n '1,20p' ref/ai-hedge-fund/hedge_fund/event_study/models.py` |
| `REF-backtest-engine-03` | TradingAgents-CN（`scripts/init_paper_trading_market_rules.py`） | repo | https://github.com/hsliuping/TradingAgents-CN | `74783e8817d6cf6de29867880631cc555153f36b`（2026-07-24） | 混合：`scripts/` 等默认 Apache-2.0；`app/`、`frontend/` 专有 | 37.5 MB / 2032 文件 | `ref/TradingAgents-CN/`（既有快照） | `sed -n '20,60p' ref/TradingAgents-CN/scripts/init_paper_trading_market_rules.py` |
| `REF-backtest-engine-04` | Vibe-Trading（quant-statistics skill 文档） | repo | https://github.com/jack139/Vibe-Trading | `bca4049fbdb1d3c837eac8e8428bb3c4ccc53a0b`（2026-04-17） | MIT | 39.7 MB / 562 文件 | `ref/Vibe-Trading/`（既有快照） | `grep -n 'Bonferroni\|Holm\|fdr' ref/Vibe-Trading/agent/src/skills/quant-statistics/SKILL.md` |

## 4. 借鉴点与落地映射

| REF-ID | 借鉴什么（具体到设计/算法/字段） | 明确不借鉴什么 | 落地位置（capability / Requirement） |
| --- | --- | --- | --- |
| `REF-backtest-engine-01` | 时点快照的**硬过滤规则表**：财报按 `ann_date` 而非 `end_date`；`trade_date <= cutoff`；分红、股东数据按 `ann_date`。其「只在 L1 数据层过滤，不在上层兜底」的分层态度 | 全部源代码（AGPL-3.0 传染，不 COPY）；章节 DAG 投研框架与桌面应用形态 | `backtest-engine` / R10、R11 |
| `REF-backtest-engine-02` | 事件研究结构体与算法：`MarketModelFit` → `daily_ar` → `WindowStats(n_events, mean_car, std_car, t_stat, p_value, ci)`；固定窗口 `[0,+20]` / `[0,+60]`；「公告日与报告期差 >45 天即剔除」的前视过滤；`skipped` 清单显式列出被跳过的标的 | iid bootstrap（改 block bootstrap，见 R6）；美股 8-K/10-Q 事件口径；LLM 选股 agent 与 `plot` 出图（`matplotlib` 未装） | `backtest-engine` / R17、R6、R11 |
| `REF-backtest-engine-03` | A 股规则**参数字段位**：`t_plus`、`price_limit{up,down,st_up,st_down,kcb_up,kcb_down}`、`lot_size=100`、`commission{rate,min}`、`stamp_duty_rate`（仅卖出）、`transfer_fee_rate`、交易时段与集合竞价 | 代码本身（只借字段划分）；其费率**数值**不直接采信；`app/`、`frontend/`（专有许可） | `backtest-engine` / R7、R8（配置段由 T2 design 定） |
| `REF-backtest-engine-04` | 校正方法清单与报告纪律：Bonferroni（p×n，最保守）/ Holm-Bonferroni（逐步法）/ FDR-BH；「回测多个策略或因子时，多重比较校正为强制」 | 其 agent skill 体例、工具链与其余量化笔记 | `backtest-engine` / R5 |

## 5. 已排除的候选（避免下一波重复调研）

| 候选 | 链接 | 排除理由（一句话） |
| --- | --- | --- |
| `ref/TradingAgents-astock` | 本地快照（TradingAgents A 股 fork） | 对 `涨停\|跌停` 的命中全部落在 `agents/analysts`、`agents/managers` 等**LLM prompt 文本**里（`grep -rl 涨停 ref/TradingAgents-astock --include=*.py`），不是撮合规则实现，借不到 R8 |
| `ref/AlpacaTradingAgent` | 本地快照 | 面向 Alpaca（美股 / 加密）账户的执行框架，A 股涨跌停与 T+1 规则不适用 |
| `ref/TradingAgents-CN` 的 `app/`、`frontend/` | 同上仓库 | 专有许可（商业使用需单独授权），不得 COPY；仅取 `scripts/` 段（Apache-2.0）的规则参数位 |
| 其余 `ref/` 快照（`TradingAgents`、`investagent`、`FinRobot`、`FinGenius`、`VerumTrade`、`daily_stock_analysis`、`valueinvest`、`FinanceToolkit`） | 本地快照 | 与本波需求（A 股撮合约束 + 事件研究统计 + 台账）不匹配或本波未深查，不作参考依据；需要时下一波单独立项调研 |

## 6. 合规与风险

- **许可证风险**：
  - `REF-backtest-engine-01` AGPL-3.0 → **只借口径，不 COPY、不 import、不 `sys.path`**（与 `docs/dev/engineering-conventions.md` §5 的 `ref/` 只读规则一致）。
  - `REF-backtest-engine-03` 混合许可 → 只读 `scripts/` 段（Apache-2.0），`app/`、`frontend/` 禁止取用。
  - `REF-backtest-engine-02` / `-04` MIT → 思路可借鉴；若将来 COPY，须保留版权与许可声明。
- **计划 COPY 进 `src/` 的部分**：**无**。本波只产出需求与规格；若 T3 决定 COPY，须在文件头写「来源仓库 / 原路径 / commit / 许可证」并补 `test/` 用例（§5 拷贝规范）。
- **参数数值风险（重要）**：`REF-backtest-engine-03` 的 `stamp_duty_rate = 0.001`（卖出千分之一）等数值**可能已与现行口径不符**（印花税近年有下调），因此本波只把它当**字段位**参考，具体数值作为**需求口径问题 Q4** 报 Owner 定，不在 spec 里写死数值。
- **数据与隐私**：不涉及受限个人数据；回测数据来自本地 DB 与既有 fetcher，不新增外网抓取。
- **其它风险**：① `REF-backtest-engine-02` 的 `plot.py` 依赖 `matplotlib`，本机未安装 → 图表不进本 change；② `REF-backtest-engine-01` 的实现面向其自有 SQLite schema，口径可借、代码不可借。

## 7. 未解决 / 待确认

1. **Q5 未查清**：退市 / ST / 历史指数成分名单在本机是否可通过 `tushare` 现有 token 取得，本波未实测（属数据侧，需 T2 技术方案验证）。→ 已作为**假设 A4** 写进 proposal：不可得则 R12 报缺口并停止。
2. **Q4 未定**：费率与滑点分档的现行数值需 Owner 给权威口径（已列入澄清问题清单 Q4）。
3. **索引表未回填**：`docs/design/references/README.md` 的「波次调研索引」表尚未加入本文件行——该文件在起波前已有**波次外未提交改动**，为避免把无关改动混进本任务提交，留给 T8 integrator 归档时一并补行。
4. `ref/research/backtest-engine/` 目录本波**未创建**（0 新增资料），下波若要深挖再建。

## 8. 检索记录

> 可复核：本波**未使用** `web_search` / `read_page` / `web_fetch`（`ref/` 既有快照已覆盖 4 条参考），全部为本地检索，命令可直接重跑。

| 日期 | 引擎 / 来源 | 查询词 / 命令 | 命中数 | 实际采用的 |
| --- | --- | --- | --- | --- |
| 2026-11-15 | 本地 `ref/`（grep） | `grep -rln "point_in_time\|point-in-time\|公告日\|survivorship\|lookahead\|未来函数" ref/thesis-backtester` | 43 文件 | `REF-backtest-engine-01`（`src/data/snapshot.py`） |
| 2026-11-15 | 本地 `ref/`（grep） | `grep -rln "涨跌停\|limit_up\|T+1" ref/thesis-backtester/src` | 0 | —（记为「无 A 股撮合可借实现」的证据） |
| 2026-11-15 | 本地 `ref/`（ls/grep） | `ls ref/ai-hedge-fund/hedge_fund` → `event_study/`、`backtesting/`；`grep -n "class " ref/ai-hedge-fund/hedge_fund/event_study/models.py` | 6 结构体 | `REF-backtest-engine-02` |
| 2026-11-15 | 本地 `ref/`（grep） | `grep -rli "deflated\|bonferroni\|multiple test\|多重比较" ref/` | 5 文件 | `REF-backtest-engine-04`（Vibe-Trading quant-statistics） |
| 2026-11-15 | 本地 `ref/`（sed） | `sed -n '20,60p' ref/TradingAgents-CN/scripts/init_paper_trading_market_rules.py` | 1 规则表 | `REF-backtest-engine-03` |
| 2026-11-15 | 本地 `ref/`（grep） | `grep -rln "涨停\|跌停\|T+1\|停牌" ref/TradingAgents-astock --include=*.py` | 9 文件（全为 agents/ prompt） | 列入 §5 排除 |
