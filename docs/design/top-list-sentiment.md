# 龙虎榜/席位（PO-13）设计与口径

> 来源：OpenSpec change `add-top-list-sentiment`（2026-11-01）
> 相关：[engineering-conventions.md](../dev/engineering-conventions.md) §3.2、[tushare-permission-scan.md](../mrd/tushare-permission-scan.md) §4.1、[roadmap-todo.md](../mrd/roadmap-todo.md) PO-13

## 1. 定位

龙虎榜是**个股级观察维度**，与个股资金面（PO-12）、治理/事件面（PO-11）同构：

- 只输出确定性事实与分档，零 LLM；
- 不参与 `signal_score`、`combined_signal`、`value_rating`，不进入 LLM ContextPack / grounding / briefing；
- 不构成买卖建议，报告固定附提示文案。

## 2. 数据事实（2026-11-01 实测，决定实现口径）

| 事实 | 影响 |
|------|------|
| `top_list` / `top_inst` 都是**市场级日接口**（`trade_date` 必选、无区间参数） | 按交易日整日拉取全市场并落库，分析时按 `code` 读本地，避免逐票 × 逐日的 API 爆炸 |
| 同一股票同一交易日可因多条 `reason` 出现多行，且**行内金额并不总是相同** | 上榜次数按交易日去重计数；净买额只能取「主导事件」，**不可跨理由求和**（会重复计算） |
| `top_inst` 席位无天然唯一键：同一「机构专用」可占多个前五席位，同一席位也可能同时出现在买入前 5 与卖出前 5（金额相同） | 席位表用代理主键、按交易日整日替换写入；机构口径按 `(exalter, buy, sell, reason)` 去重后再求和 |
| 官方文档标 `top_inst` 需 5000 积分，本项目 2000 积分档实测可用 | 不得假定恒可用：失败时保留 `top_list`，机构维度降级为「不可用」并警告 |
| 「未上榜」与「未拉取」在数据层不可区分 | 引入交易日覆盖水位表，分析层显式告警覆盖不足 |

## 3. 落点与依赖

```
apps/cli.py ──► service/toplist/analyzer.py ──► data_provider/toplist/provider.py ──► TushareTopListFetcher
                    │                                  │
                    └──► dao/top_list_repo.py ◄────────┘
service/dual_track/analyzer.py ──► service/toplist/analyzer.py（新增字段编排）
apps/formatters.py / service/report/dashboard_builder.py ──► TopListResult（只读）
```

依赖方向符合 `apps → service → data_provider/dao → common`；`service` 不直接调 Tushare。

## 4. 表结构

| 表 | 主键 | 关键列 | 写入语义 |
|----|------|--------|----------|
| `stock_top_list` | `(code, trade_date, reason)` | `name, close, pct_change, turnover_rate, amount, l_sell, l_buy, l_amount, net_amount, net_rate, amount_rate, float_values, fetched_at` | 按交易日整日替换（先删该日、再批量插入） |
| `stock_top_inst` | 代理 `id` | `code, trade_date, side, exalter, buy, buy_rate, sell, sell_rate, net_buy, reason, fetched_at` | 按交易日整日替换 |
| `top_list_sync_marker` | `trade_date` | `source, fetched_at` | 仅在 `top_list` 返回非空后写入；幂等 |

新表由 `Base.metadata.create_all` 建出（CLI 启动路径已调用），`ensure_sqlite_schema()` 无需改动。

## 5. 规则口径（`src/service/toplist/rules.py`）

| 维度 | 口径 | 常量 |
|------|------|------|
| 统计窗口 | 近 `90` 自然日 | `WINDOW_DAYS = 90` |
| 上榜次数 | 去重后的上榜交易日数 | — |
| 活跃度 | 0 未上榜 / 1–2 偶发 / `>=3` 活跃 | `ACTIVE_MIN_APPEARANCES = 3` |
| 净买额分档 | 主导事件净买额 `>= 5000 万元` 大额净买入、`<= -5000 万元` 大额净卖出、其余中性 | `LARGE_NET_BUY_10K = 5000` |
| 主导事件 | 该日 `l_amount` 最大者；并列按 `reason` 稳定选择 | — |
| 机构参与 | 机构专属席位 `net_buy` 去重后求和；`>=0` 机构买入、`<0` 机构卖出、无席位为 `None` | — |
| 理由分类 | 连续三日累计 > 跌幅偏离 > 涨幅偏离 > 换手率 > 振幅 > 其他 | `REASON_CATEGORY_ORDER` |
| 覆盖告警 | 水位最早交易日比窗口起点晚超过 `5` 天即告警 | `COVERAGE_START_TOLERANCE_DAYS = 5` |

## 6. 同步策略

| 入口 | 行为 |
|------|------|
| `sync <code>` | 解析最近开市交易日；已在水位表则**跳过**（0 次调用），否则拉该日 `top_list`（+ 尽力 `top_inst`）、整日替换写入、写水位；失败仅 warning，不阻断价值/K线/筹码/资金面/事件 |
| `sync market --top-list-days N` | 回填最近 N 个交易日（默认 20），已覆盖跳过，逐日失败继续；`N <= 0` 跳过 |

交易日解析：`trade_cal`（`is_open=1`，近 10 天）优先；不可用时按今天起回溯最多 5 个自然日探测 `top_list` 非空者；仍失败则不发请求、不写水位、仅告警。空结果**永不**写水位，避免把「休市/未发布」当成「已确认无上榜」。

## 7. 验证

- 单测：`pytest test/dao/test_top_list_repo.py test/data_provider/toplist test/service/toplist test/service/dual_track test/apps -q`
- 全量门禁：`pytest -q -m "not network"`
- 迁移基线：`python scripts/compare_migration_baseline.py`（新增字段不进入 dual JSON payload，基线须零漂移）
- 实测（2026-11-01）：`sync market --top-list-days 5` 回填 5 日（89/88/78/75/96 条）；`000568` 的 `net_amount` 与 API 一致（4.61 亿元），机构席位净买 2.4872 亿元与 API 去重后一致；清空 `stock_top_inst` 后机构维度正确降级。
