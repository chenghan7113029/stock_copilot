## Context

情绪面已有三层：市场级 V1（`service/sentiment/`，涨跌停家数比 + 恐慌贪婪代理）、个股资金面（`service/fundflow/`，PO-12）、治理事件面（`service/event/`，PO-11）。三者共享同一套已固化的工程范式：

- `data_provider/<域>/` 提供 `Provider`（`from_config` 工厂 + Router/直接实例化 + 逐接口降级 + 离线缓存）
- `dao/<域>_repo.py` + `dao/models.py` ORM 表按 `(code, trade_date)` 组织，`upsert_batch` / `query_range`
- `service/<域>/` 纯确定性 Facade：`analyze()` 联网、`analyze_offline()` 严格离线
- `apps/formatters.py` 独立区块 + 固定免责文案；**不参与** `signal_score` / `combined_signal`
- `DualTrackReport` 新增可选字段 + dual/dashboard 区块

龙虎榜（PO-13）与上述三者的关键差异：`top_list` / `top_inst` 是**市场级日接口**（`trade_date` 必选、无区间参数），按股票取历史必须逐交易日循环。这一差异决定了本设计的核心取舍。

约束：
- 依赖方向 `apps → controller → service → data_provider/dao → common`，`service` MUST NOT 直接调 Tushare
- 默认数据源 tushare + baostock（AKShare 已退役为紧急回滚），故只走 Tushare
- `top_list`：2000 积分；`top_inst`：官方文档标 5000 积分，本项目 `tushare-permission-scan.md` §4.1 实测 2000 可用 → 必须假定可能不可用并降级
- 迁移基线门禁：本 change 不改 `report tech/value/dual` 的既有数值输出（新增字段/区块属于增量），L3 基线不应漂移

## Goals / Non-Goals

**Goals:**

- 以最小 API 成本把「个股是否上榜、净买额多少、机构还是营业部在买、为什么上榜」变成可离线复读的确定性事实
- 用**覆盖水位**区分「该股近 90 日没上榜」与「我们没拉到那几天」，杜绝把数据空洞说成「无异常」
- 与既有情绪/资金面/事件面完全同构：独立区块、观察维度、零 LLM、不碰融合数值
- 单票工作流（`sync <code>` → `report toplist/dual/dashboard`）开箱可用，无需先手动跑 `sync market`

**Non-Goals:**

- 不做席位/游资身份标注（需外部游资名录，维护成本与腐化风险高，另立 change）
- 不做市场级「当日上榜家数 / 龙虎榜总净买」聚合指标（属市场情绪维度，V1 不给 `sentiment` 加口径）
- 不注入 LLM ContextPack / `report summary --narrate` / `report briefing`（避免改动 grounding 与叙事基线）
- 不做历史自动回填调度（回填靠显式 `sync market`）
- 不改 `signal_score`、`combined_signal`、`value_rating` 任何数值路径
- 不引入 AKShare 作为 fallback（退役约束）

## Decisions

### D-1 按「市场日」拉取，按「个股」查询（而非逐票拉历史）

`top_list` 只接受 `trade_date`（+ 可选 `ts_code`），没有 `start_date/end_date`。逐票取 90 日历史 = 90 次调用/票，不可接受。

**决策**：一次 `top_list(trade_date=D)` 返回全市场当日上榜（通常 < 200 行，远低于 10000 行上限），落库全部股票；分析时按 `code` 读本地。

**备选**：① 逐票逐日循环（API 成本爆炸，放弃）；② AKShare `stock_lhb_stock_detail_em`（数据源已退役，放弃）；③ 只存当日快照不建历史（无法算「近 90 日上榜次数」，放弃）。

### D-2 覆盖水位表 `top_list_sync_marker`，区分「未上榜」与「未拉取」

龙虎榜表里没有记录 = 要么该股没上榜，要么那天没同步。二者语义完全不同，混同会输出「近 90 日上榜 0 次」的假事实。

**决策**：每次成功拉取 `trade_date=D` 后写一行水位标记（`trade_date` 主键）。分析时以「水位覆盖的交易日集合」夹逼统计窗口，覆盖不足则 `warnings` 显式说明「龙虎榜覆盖 X 个交易日（Y~Z），近 90 日上榜次数可能偏低」。

**备选**：① 用 `MAX(trade_date)` 推断覆盖（无法发现中间空洞，放弃）；② 复用 `market_sentiment_snapshot` 日期（语义耦合、`sync <code>` 不写它，放弃）；③ 不看覆盖、直接输出次数（输出假事实，放弃）。

### D-3 两张表分离；`top_list` 用业务主键、`top_inst` 用代理主键 + 整日替换

两者字段差异大（`top_list` 是每票每日的上榜事件行，含 `reason`；`top_inst` 是席位行，含 `exalter`/`side`）。同一股票同一天可能因多条 `reason` 出现多行。

**决策（2026-11-01 实测后修正）**：
- `stock_top_list` 主键 `(code, trade_date, reason)`，写入按交易日**整日替换**（先删该日、再批量插入），重复同步幂等。
- `stock_top_inst` **无天然唯一键**：实测同一「机构专用」可占多个前五席位，同一席位也可能同时出现在买入前 5 与卖出前 5（金额相同）。故用代理主键 `id`，同样按交易日整日替换写入；机构口径在规则层按 `(exalter, buy, sell, reason)` 去重后再求和。
- 规则层对上榜次数按 `trade_date` 去重计数（同日多理由只计一次）。

**备选**：单表 + `kind` 列（字段大量可空、查询分支复杂，放弃）；按 `(code, trade_date)` 单行聚合（丢失 reason 与席位信息，放弃）；`top_inst` 用 `(code, trade_date, side, exalter)` 主键（会把同一「机构专用」的多个席位塌缩成 1 行，丢数据，放弃）。

### D-4 机构 vs 营业部：只用 `exalter` 的确定性判据

龙虎榜本身不标注「游资」，但 `top_inst` 的席位名称里 `机构专用` 是稳定可判的机构通道。

**决策**：`exalter` 含「机构专用」→ 计入机构买卖额；其余计入「营业部（含游资/个人通道）」并在文案中只称「机构 / 非机构」，不臆测游资身份。

**备选**：引入游资名录做身份映射（须长期维护营业部改名，且属推断而非事实，V1 放弃）。

### D-5 信号口径全部为模块常量阈值，输出「事实 + 分档」而非结论

沿用 `service/fundflow/rules.py` 的做法（模块级常量 + 纯函数 + 只陈述事实）。

| 维度 | 口径 | 阈值常量 |
|---|---|---|
| 统计窗口 | 近 `90` 自然日内的交易日 | `WINDOW_DAYS = 90` |
| 上榜频次 | 窗口内去重后的上榜交易日数 → 0 / 1–2 / ≥3 分档 | `ACTIVE_MIN_APPEARANCES = 3` |
| 最近一次净买额 | 最近上榜日「主导事件」（`l_amount` 最大者）的 `net_amount`（元）；**不可跨理由求和**（实测同日多理由金额不同，求和会重复计算） | `LARGE_NET_BUY_10K = 5000`（万元） |
| 机构净买 | `top_inst` 中机构席位 `buy - sell` 之和；无 `top_inst` 数据则 `None` | — |
| 理由分类 | `reason` 文本 → 涨幅偏离 / 跌幅偏离 / 换手率 / 振幅 / 连续三日累计 / 其他（按此优先级匹配） | 关键词常量表 |
| 席位集中度 | 最近上榜日前 5 买席位占龙虎榜买入额比例（可选，数据不足 `None`） | — |

分档只输出「活跃/偶发/未上榜」「机构净买入/净卖出/无机构席位」「大额净买入/净卖出」，**不输出买卖建议**，文本固定附「观察维度，不构成买卖建议」。

### D-6 `sync <code>` 只补「未覆盖的最近交易日」；`sync market` 做批量回填

`sync <code>` 若每次全量回填 20 日 = 40 次调用，过重；只在 `sync market` 拉则单票工作流拿不到数据。

**决策**：
- `sync <code>`：解析出最近交易日 `D`（见 D-7），若 `D` 已在水位表 → 跳过（0 次调用）；否则拉 `top_list(D)` + `top_inst(D)` 并写水位。失败仅 warn，不阻断 sync（与资金面/事件面一致的降级语义）。
- `sync market`：回填最近 `N = 20` 个交易日（`--top-list-days` 可调），逐日拉取；单日失败记 warning 继续。
- API 调用计入 `on_progress` 进度输出，便于观测。

**备选**：`sync <code>` 拉最近 5 日（多 4 次调用换一周窗口，V1 不必要，`sync market` 已覆盖回填场景）。

### D-7 最近交易日解析：`trade_cal` 优先，退化探测

复用 `TushareSentimentFetcher._latest_trade_date()` 的同款思路（`trade_cal` + 近 10 自然日），抽成 `toplist` 侧的独立 helper（不跨域 import 私有方法）。`trade_cal` 不可用时退化为「今天起回溯最多 5 个自然日，取第一个 `top_list` 非空的交易日」；仍为空则不发请求、不写水位、只 warn。

**理由**：龙虎榜在收盘后才更新，盘中/休市日直接查当天易返回空；把「空结果」当成功写水位会污染覆盖语义。

### D-8 不注入 LLM，也不改基线

`TopListResult` 只进 `DualTrackReport`（新增可选字段）与 CLI 文本/JSON。理由：`report summary --narrate` 的 grounding 校验要求数值可溯源，新增证据块会牵动 `context_pack.py` 与 L3 基线 fixture；V1 先落地事实层，叙事化另立 change。

### 依赖与落点

```
apps/cli.py ──► service/toplist/analyzer.py ──► data_provider/toplist/provider.py ──► tushare fetcher
                    │                                  │
                    └──► dao/top_list_repo.py ◄────────┘（provider 与 analyzer 都经 repo 写/读）
service/dual_track/analyzer.py ──► service/toplist/analyzer.py（新增字段编排）
apps/formatters.py ──► service/toplist/models/top_list_result.py（只读模型）
```

表结构（`src/dao/models.py`）：

| 表 | 关键列 | 索引/主键 | 写入语义 |
|---|---|---|---|
| `stock_top_list` | `code, trade_date, reason(上榜理由), close, pct_change, turnover_rate, amount, l_sell, l_buy, l_amount, net_amount, net_rate, amount_rate, float_values, fetched_at` | PK `(code, trade_date, reason)`；`ix_stock_top_list_code_date` | 按交易日整日替换 |
| `stock_top_inst` | `code, trade_date, side, exalter, buy, buy_rate, sell, sell_rate, net_buy, reason, fetched_at` | 代理 PK `id`；`ix_stock_top_inst_code_date` | 按交易日整日替换（席位无唯一键） |
| `top_list_sync_marker` | `trade_date, source, fetched_at` | PK `trade_date` | 仅非空 `top_list` 后写入 |

新表由 `Base.metadata.create_all` 建出；`ensure_sqlite_schema()` 只需在需要给**已有表**加列时改动，本 change 不改它。

## Risks / Trade-offs

- [`top_inst` 权限不足（官方标 5000）] → 降级为仅 `top_list`：机构维度返回 `None`，`reasons` 不出现机构陈述，`warnings` 记「机构席位接口不可用」，其余维度照常；测试覆盖该分支
- [同日多理由的金额求和导致翻倍] → 只取主导事件；实测 2026-10-08 有 8 只股票同日不同理由金额不同（如 `300530` 两条理由净买额分别为 7677 万与 6542 万）
- [`top_list` 空结果被误当「成功」写水位] → 空 DataFrame 视为「该交易日无榜单数据」：不写水位、不发水位标记、warn；仅在拿到非空结果时写标记
- [同日重复行导致上榜次数虚高] → 规则层按 `(trade_date, reason)` 去重后计数；`upsert` 主键含 `reason` 保证幂等
- [历史空洞导致统计偏低] → 水位 warning 显式告知覆盖区间与天数；不回填、不估算
- [盘中运行拿到未更新数据] → D-7 取上一交易日；同时 `top_list` 收盘后才发布，故「今天」查询天然不用于当日决策
- [新增区块污染既有报告/基线] → 只追加区块与字段，`SignalFusion` 不读取 `top_list_result`；L3 基线比对仍应零漂移（gate 中显式验证）
- [数据量增长] → 约 100–300 行/交易日 × 20 日回填 = 数千行，SQLite 无压力；不做清理任务（与现有表一致）
- [按日循环回填 20 日 = 40 次调用] → 计入 `sync market` 的显式行为，`--top-list-days` 可由用户下调；增量日只有 2 次

## Migration Plan

1. 新增 ORM 表与 repo（`Base.metadata.create_all` 在 CLI 启动路径已调用，旧库自动建表，无需手工迁移）
2. 先落地数据层（fetcher/provider/repo）并打通 `sync market` 回填，用真实 token 人工核对一只上榜股的 `net_amount` 与东财/同花顺是否一致
3. 再接 `service/toplist` 规则 + `report toplist`，最后接 dual/dashboard 区块
4. 回滚策略：新表与新命令互相独立，`git revert` 代码即可；已写入的龙虎榜表不影响任何既有路径（无外键、无既有查询引用）

## Open Questions

- `ACTIVE_MIN_APPEARANCES=3`、`LARGE_NET_BUY_10K=5000`（万元）为首版经验阈值，是否需要按流通市值归一（小盘股 5000 万净买与大盘股含义不同）？倾向 V1 先固定阈值 + 在 `details` 里同时给出占龙虎榜成交额比例，等实际样本再定
- 「席位集中度」是否值得进 V1？`top_inst` 只给买卖前 5 席位，占比口径易被误读；倾向 V1 只算机构净买，集中度留到有样本后评估
- `sync market` 回填默认 20 日是否足够覆盖「近 90 日」统计窗口？不足部分只能靠日常增量累积，需在用户文档里讲清「首次建库请用 `--top-list-days 60`」
