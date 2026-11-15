# 调研记录（change 内副本）

> 本 change 做了外部参考调研（4 条，全部来自既有本地 `ref/` 快照，0 次新 clone）。
>
> **唯一真源（进 git）：[`docs/design/references/backtest-engine-research.md`](../../../../docs/design/references/backtest-engine-research.md)** —— 按 `docs/dev/engineering-conventions.md` §5 的规定，调研索引必须落在 `docs/design/references/`（`ref/` 不进 git，索引才是唯一凭据）。本文件只做 change 内的可追溯摘要，**不复制全文**，避免两处漂移。

## 结论一句话

借鉴 `thesis-backtester` 的时点硬过滤、`ai-hedge-fund` 的事件研究统计骨架、`TradingAgents-CN scripts/` 的 A 股规则参数位、`Vibe-Trading` 的多重比较校正清单；四者都**没有**「涨跌停封板顺延 / T+1 / 停牌 / 后复权」的可复用实现，这部分按飞书《投资Agent》r482 §回测模块·三 自建；**不 COPY 任何代码**。

## REF 条目（摘要）

| REF-ID | 对象 | 许可证 | 借鉴 | 落地 |
| --- | --- | --- | --- | --- |
| `REF-backtest-engine-01` | `ref/thesis-backtester` @ `3ea3a6c` | AGPL-3.0（只借口径） | 财务按 `ann_date`、股价 `trade_date <= cutoff`、分红同口径的时点硬过滤 | R10 / R11 |
| `REF-backtest-engine-02` | `ref/ai-hedge-fund` @ `eff8a73` | MIT | 事件研究骨架（市场模型 → AR → CAR → 窗口统计 + CI）、走味事件前视过滤 | R17 / R6 / R11 |
| `REF-backtest-engine-03` | `ref/TradingAgents-CN` @ `74783e8`（`scripts/` 段） | Apache-2.0（`app/` 为专有，禁取） | A 股规则**字段位**：T+1、涨跌停、100 股、佣金/最低额、印花税（仅卖出）、过户费 | R7 / R8 |
| `REF-backtest-engine-04` | `ref/Vibe-Trading` @ `bca4049` | MIT | 多重比较校正清单（Bonferroni / Holm / FDR-BH）与「校正为强制」的纪律 | R5 |

## 明确不借鉴

- 前 3 者均无 A 股撮合与后复权实现（`thesis-backtester/src` 中 `涨跌停|limit_up|T+1` 命中 0 文件）。
- `ai-hedge-fund` 的 iid bootstrap（未处理组内相关）→ 本波改用 block bootstrap（R6）。
- 任何 LLM 参与数值计算的结构（`docs/dev/engineering-conventions.md` §9.2）。
- `TradingAgents-CN` 费率**数值**（可能过期）→ 只借字段位，数值走需求口径问题 Q4 由 Owner 定。

## MRD

`docs/mrd/mrd-v1.md` 仍是骨架，**本 change 无任何 MRD 锚点**；需求锚点 = 飞书《投资Agent》r482 原文 + 仓库一手材料。
