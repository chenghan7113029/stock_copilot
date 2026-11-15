# case-20261115-allocation-executor — 配置执行器（一期 P0 第二项）

> 现实锚点（ground-truth）。本 case 的事实来源只有两个：① Owner 2026-11-15 的答复 ② 仓库一手材料。
> 私人金额（家庭资产总额 / 缺口 / 月供 / 持仓市值与成本）**不入本文件**，只在 `config/ips.local.yaml`（gitignored）。

## 1. 要解决的真实问题（来源：飞书《投资Agent》v2 §一 P3）

> 「卖完就空仓，没有替代方案」：2025-12 清仓后权益占比从约 25% 降到 4.04%，约 672 万停在 1.6% 存款；
> 目标权益 35%，缺口 217 万；等待 11 个月无规则。

## 2. 文档裁决（来源：飞书《投资Agent》rev 488 §三 / §四）

- 优先级：**回测台 P0（已完成）→ 配置执行器 P0（本波）**，前置依赖 = **无**（纯算术，不依赖任何规则）。
- 为什么排第二（§四）：*「配置执行器排第二，与规则无关：它只做算术（缺口除以期限得出每月金额），却能立刻改变结果——钱停在 1.6% 的存款里，等待本身就有成本。」*
- §三 验收标准原文：**「每月固定日给出『买多少、买什么类别』；金额与比例可复算，与 ips 配置一致」**。
- §三 v2 修订：40/5/25 三条上限「未经回测验证且已在文档评注中被否决，已从验收标准移除，改由回测结果决定参数」→ 本波只能作**提示**，不得当硬门禁。
- §五 明确不做：全市场荐股、宏观/债券研究、交易员自动下单（只出工单）、Web UI。

## 3. Owner 2026-11-15 书面答复（本波口径 ground-truth）

| # | 问题 | Owner 答复 |
| --- | --- | --- |
| 1 | 权益目标与投放期限 | 沿用 ips 现值：权益 **35%**、期限 **24 个月** |
| 2 | 执行日 | **每月最后一个周四**（`execution_day: last_thursday`） |
| 3 | 买什么类别 | 权益端**只买宽基 ETF**（具体标的未指定，不影响金额计算）；固收端先按 **30%** 试水迁移 |
| 4 | 数据来源与时效 | 用 `config/ips.local.yaml` 手工快照；快照 `as_of` 超 `R8_stale_days=7` 天 → **拒绝给指令**（不用过期数拍板） |

## 4. 仓库一手材料（政策值，已入库）

- `config/ips.yaml`：目标配置 35/45/20、容许带 30–40%、`deployment`（`monthly_dca` / 第 2 个月起 / 24 月 / 目标日 2028-11-30 / `last_thursday` / `skip_if_equity_above=0.35` / `new_money_vehicle=broad_etf`）、`fixed_income_detail.migration`（`enabled` / `trial_ratio=0.30` / 目标中短债或理财）、`rules.R4_rebalance_band=0.05`、`rules.R8_stale_days=7`。
- `config/ips.local.yaml`（gitignored）：`pool`、`allocation.current`、`holdings`、`deployment.gap_to_target`、`monthly_amount`。
- 既有能力：`openspec/specs/tech-analyzer/`、`value-analyzer`、`cli-*`；本波**不依赖**回测产出。

## 5. 可证伪的成功判据（本波用）

1. 给定同一快照与同一日期，`ips plan` 输出的当月金额可被人工按公式复算到**元**，且与 `ips.yaml` 政策一致。
2. 权益占比 > 35% 时当月输出「顺延 + 理由」，不得仍然给出买入金额。
3. 快照超过 7 天 → 退出码非 0 且说明「数据过期」，不得用旧数出指令。
4. 任一桶偏离目标 > 5pp → 输出再平衡**提示**（不自动调仓）。
5. 全链路零 LLM、无网络依赖（除读取本地配置）。

## 6. 已知边界

- 账本与市价属 P2（文档 §三）：本波只消费手工快照，不重建记账。
- 持仓体检属 P1：本波不做「持有/减仓/清仓」判定（依赖回测规则）。
- 交易员不自动下单：本波只产出「买多少、买什么类别」的工单文本。

## 7. 结论编号与 ground-truth 标注（append-only，2026-11-15 补）

> 本节只追加，不改写 §1–§6。结论编号把 §5 五条可证伪判据编号为 **C1–C5**；**C0** 保留给「case 级 / 跨判据」挂靠（K3b 的 knowledge trace 已使用，见 `traces.yaml`）。ground-truth 只依据 ① Owner 2026-11-15 答复 ② 仓库一手材料原文标注，PM **不替业务方判对错**；一手材料不足以判定的标「**存疑**」并写明缺什么，不拍「采纳」。

**README 必含段对照（`docs/cases/README.md:34-42`）**：原始业务问题（原始话术，不改写）→ §1；分析链逐环事实 → §8（§2–§4 为文档裁决与一手材料原文）；结论 + 结论编号 → §7；ground-truth（采纳 / 存疑 / 不采纳）→ §7；功能差距 → §9；改进点 → §10；「距端到端复现还差什么」→ §11。

| 编号 | 判据（§5） | ground-truth | 标注依据与理由 |
| --- | --- | --- | --- |
| C1 | 同一快照 + 同一日期，金额可人工复算到元且与 `ips.yaml` 一致 | **采纳** | 飞书 v2 §三 验收原文直接要求「金额与比例可复算，与 ips 配置一致」（annotations:15）；Owner #1 定目标 35% / 期限 24 个月（:23）；政策值见 `config/ips.yaml:26-30`、`:45-53`；`ips.local.yaml` 的 `gap_to_target` / `monthly_amount` 与「缺口 ÷ 24 月、取整到元」逐项对得上（:31，数值不入本文件）。子口径 Q1（`.5` 进位方向）未确认，只影响末位 1 元，不改变「可复算到元」判据 |
| C2 | 权益占比 > 35% 时输出「顺延 + 理由」，不给买入金额 | **采纳** | Owner #1 权益目标 35%（annotations:23）；`config/ips.yaml:51 skip_if_equity_above: 0.35` 与 Owner 答复同值（一手政策原文）；「不给买入金额」即 skip 语义的直接推论（同义表述见草案 `portfolio-plan-v0.1.md:90`） |
| C3 | 快照超 7 天 → 退出码非 0 + 说明「数据过期」，不用旧数出指令 | **采纳** | Owner #4 明确「快照 `as_of` 超 `R8_stale_days=7` 天 → 拒绝给指令（不用过期数拍板）」（annotations:26）；阈值原文见 `config/ips.yaml:67` |
| C4 | 任一桶偏离目标 > 5pp → 输出再平衡提示（不自动调仓） | **存疑** | 「5pp」有政策原文（`config/ips.yaml:61 R4_rebalance_band: 0.05`），但「**只提示、不自动调仓**」目前只在两处一手材料之间互相矛盾：本 case §5 判据（:39，PM 起草）说「不自动调仓」，草案 `portfolio-plan-v0.1.md:110` 的动作却是「季度调整回目标带」（= 会调仓），且草案 :4 自称「待 Owner 确认」。缺：Owner 对「提示 vs 调仓」的行动口径表态 → 标**存疑**，待确认后回填 |
| C5 | 全链路零 LLM、无网络依赖（除读取本地配置） | **采纳** | 飞书 v2 §四「它只做算术」（annotations:14）、§五「明确不做」（:17）给业务边界；`docs/dev/engineering-conventions.md` §9.2 规定数值不得由 LLM 生成/修改；Owner #4 指定用 `config/ips.local.yaml` 手工快照（:26），无联网取数需求 |

**不采纳（防误用；非 §5 判据，不参与 C1–C5 复现核对）**

| 编号 | 事项 | 标注 | 理由 |
| --- | --- | --- | --- |
| N1 | 40% 权益上限 / 单票 5% / 行业 25% 作为**硬门禁** | **不采纳** | 飞书 v2 §三 修订：「未经回测验证……已从验收标准移除，改由回测结果决定参数」→ 本波只能作提示（annotations:16） |
| N2 | 自动调仓（把桶位调回目标带） | **不采纳（本波）** | 与 §5 判据 4「不自动调仓」冲突；草案该动作未经 Owner 确认（`portfolio-plan-v0.1.md:4`、:110），本波只出提示 |
| N3 | 具体 ETF 代码 / 个股标的 | **不采纳（本波）** | Owner #3：权益端只买宽基 ETF，**具体标的未指定，不影响金额计算**（annotations:25） |

**开放问题（含 KQ-1；未答复按 proposal 假设执行，不升格确定口径）**

| 编号 | 问题 | 状态 | 影响 | 本波处理 |
| --- | --- | --- | --- | --- |
| KQ-1 | 执行日（每月最后一个周四）恰逢休市 / 法定节假日：仍按该日给指令、顺延到下一交易日，还是提前到前一交易日？ | **待 Owner 确认**（`config/knowledge/known_unknowns.yaml` 的 `KU-2026-11-alloc-holiday-01`；1 小时时钟按 captain 转交时刻起算） | 执行日标注（R2）；不影响金额公式——指令不是成交 | 本波按「仍按日历周四给指令、不做交易日顺延」执行（design 决策 5），答复后只改执行日解析一处 |
| Q1–Q5 | 取整 `.5` 方向 / 迁移基数与次数 / 现金是否硬门禁 / 顺延是否独立记账 / 宽基 ETF 标的池 | **待 Owner 确认**（T1 proposal 假设 A2–A6；KU 见 `known_unknowns.yaml`） | C1 末位金额 / R5 / R9 / R6 / R5 | 按 proposal 假设执行并在输出标「待确认」 |

> 复现进度与 verdict 见 `docs/cases/case-20261115-allocation-executor/traces.yaml`；本节不手写「复现进度」表、不抄 trace 数字。

## 8. 分析链逐环事实（环定义：提问 / 取数 / 计算 / 结论 / 呈现）

> 环定义随 MRD 演进（`docs/agent-team/templates/case-teardown.md:26`）；「用到的知识」列归 K1，本节不填。产品现状均为**本波实现前**（2026-11-15，HEAD 914a095）的可复核事实。

| 环 | case 实际做了什么 | 产品现状（可证伪） | 差距 |
| --- | --- | --- | --- |
| 提问（Question） | Owner 问「每月该买多少、买什么类别」（飞书 v2 §一 P3 / §三 验收） | `src/apps/cli.py` 无 `ips` / `plan` 子命令（`grep -n "ips" src/apps/cli.py` 无命中）；`openspec/specs/` 无 allocation-executor capability（`ls` 无此目录） | 无「按月产配置指令」入口 |
| 取数（Data） | 读 `config/ips.yaml` 政策 + `config/ips.local.yaml` 手工快照（Owner #4） | 两文件已在库 / 本机，但无 `as_of` 时效与缺字段的拒绝路径（无消费代码） | 无 fail-closed 校验 |
| 计算（Calc） | 缺口 = 35% × pool − 权益市值；÷ 剩余 24 月；超 35% 顺延；桶位偏离 5pp | `src/service/allocation/` 不存在（`ls` 无此目录）；政策值只散落在文档与 `ips.local.yaml` 手算 | 无确定性、可复算的月金额与顺延判定 |
| 结论（Conclusion） | 输出「买多少、买什么类别」工单 + 顺延理由 + 提示 | 无该输出；`portfolio-analyzer` 只算集中度且依赖 `TradeRecord`（账本，本波 out of scope） | 无工单与提示结构 |
| 呈现（Presentation） | 人类可读工单（不下单、不选标的） | `cli-report-portfolio` 只出集中度报告；无 plan 输出契约 | 无工单呈现 |

## 9. 功能差距（指回某一环；对应本波 change `add-allocation-executor`）

| 差距 | 指回环 | 产品现状（可证伪，HEAD 914a095） | 本波需求 |
| --- | --- | --- | --- |
| 无月度固定日指令 | 计算 / 呈现 | `src/apps/cli.py` 无 `ips plan`（`grep -n "ips"` 无命中）；`openspec/specs/` 无 allocation-executor | R1–R5（缺口 / 月数 / 金额 / 类别 / 执行日） |
| 无快照时效拒绝 | 取数 | 无 `as_of` 校验代码；`config/ips.yaml:67` 有阈值但无人消费 | R7 |
| 无顺延 / 再平衡 / 现金提示 | 结论 | 无提示结构；`portfolio-analyzer` 只有集中度 warnings | R6 / R8 / R9 |
| 无「零 LLM、只出工单」边界 | 呈现 | 现有 CLI 无此子命令，边界无从谈起 | R10 |

> 复验时以当期实现为准：实现落地后上述现状变为「能复现」，属正常，不改写本节。

## 10. 改进点（候选；有证据才进 `docs/improvements/IMPROVEMENTS.md`，由 T7 收口）

| 候选 | 来源证据 | 影响面 | 建议变更名 | 优先级（建议） | 分流 |
| --- | --- | --- | --- | --- | --- |
| 取整 `.5` 方向口径未定 | Q1 / `KU-2026-11-alloc-rounding-01`；proposal A2 | 末位 1 元与实现一致性 | 并入 `add-allocation-executor` 收口（不另立） | P2 观察 | 口径问题 |
| 固收迁移基数 / 次数未定 | Q2 / `KU-2026-11-alloc-migration-base-01`；proposal A3 | R5 迁移金额 | 同上 | P2 观察 | 口径问题 |
| 现金 20% 是否硬门禁未定 | Q3 / `KU-2026-11-alloc-cash-gate-01`；proposal A5 | R9 行动口径 | 同上 | P2 观察 | 口径问题 |
| 顺延额度是否独立记账未定 | Q4 / `KU-2026-11-alloc-carryover-01`；proposal A4 | 若要求结转 → 触及账本（P2 边界） | `add-allocation-ledger`（若立项） | P2 观察 | 能力 / 边界 |
| 执行日遇休市 / 节假日未定 | KQ-1 / `KU-2026-11-alloc-holiday-01`；design 决策 5 | R2 执行日标注 | 并入本 change（改一处） | P2 观察 | 口径问题 |
| 再平衡「提示 vs 调仓」行动口径 | C4 存疑；`portfolio-plan-v0.1.md:110` vs annotations:39 | R8 输出边界 | 并入本 change（改一处） | P2 观察 | 口径问题 |

> 本节只列候选，不写入 `IMPROVEMENTS.md`（append-only 归 T7）。

## 11. 距端到端复现还差什么

| 维度 | 差什么 | 证据 |
| --- | --- | --- |
| 缺功能 | 实现月度指令（加载、缺口 / 月数 / 金额、类别、顺延、提示、时效拒绝）与单测 / QA 用例 | `src/service/allocation/` 不存在；`test/service/allocation/` 不存在（HEAD 914a095） |
| 缺口径答复 | Q1–Q5、KQ-1 待 Owner 答复；本波按 proposal 假设执行 | `config/knowledge/known_unknowns.yaml` 的 `KU-2026-11-alloc-*`；proposal 假设 A1–A6 |
| 缺知识 | 无新增缺口：K2 已落 5 条 canon（目标三桶 / 执行日 / 再平衡带 / 时效 / 试水比例）；CAN-ALLOC-005 已由 K2-repair 修正 | `config/knowledge/canon/allocation-executor.yaml`；`openspec/changes/add-allocation-executor/knowledge-verification.md` |
| 缺数据源 | 无：只消费手工快照，不联网、不建账本（Owner #4；§6） | 本文件 §6 已知边界 |

---

> 本节追加日期 2026-11-15；**append-only**：未改写 §1–§6 任一历史行。结论编号与 `traces.yaml` 的 `conclusion` 对齐：C1–C5 = 五条判据，C0 = case 级 / 跨判据挂靠（K3b 已用）。**流程提示（报 captain）**：任务书要求 C1–C5，但 `docs/agent-team/roles/qa.md:80` 的 `conclusion` 枚举写作 `C0..C4`；T5 落 trace 前需统一编号口径（建议按 C1–C5 并修订 qa.md，或由 captain 裁决）。
