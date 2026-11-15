# Proposal: add-allocation-executor

> 本波（一期 P0 第二项）：配置执行器。只做「每月固定日买多少、买什么类别」的纯算术指令；不做下单、选股、账本重建、持仓体检、LLM。
> 依据：飞书《投资Agent》v2 §三/§四/§五 + Owner 2026-11-15 四条书面答复（`docs/cases/case-20261115-allocation-executor/annotations.md`）+ 仓库一手材料（`config/ips.yaml`、`docs/design/portfolio-plan-v0.1.md`）。

## Why

现实问题是「卖完就空仓，没有替代方案」：2025-12 清仓后权益占比从约 25% 降到 **4.04%**，约 672 万停在 1.6% 存款里；目标权益 35%，缺口 217 万，等待 **11 个月**没有任何规则告诉 Owner 该买多少（annotations.md:6-9，飞书 v2 §一 P3）。飞书 v2 §四把配置执行器排在一期 P0 第二位，理由是它**只做算术**（缺口除以期限得出每月金额），却能立刻改变结果——钱停在 1.6% 的存款里，等待本身就有成本（annotations.md:14）。§三 的验收原文是「每月固定日给出『买多少、买什么类别』；金额与比例可复算，与 ips 配置一致」（annotations.md:15）。

不做会怎样：① 明知道该从 4.04% 往 35% 走，仍只能每月临场拍一个数，金额不可复算、无法复核；② 权益上涨超过 35% 时没有「不追高」的固定判据，容易在高位加仓；③ 用手工快照算数却没有时效门禁，可能拿两周前的数字拍板；④ 桶位偏离超过 5pp 没有任何提示，配置漂移无人发现。

仓库现状也替代不了：`docs/design/portfolio-plan-v0.1.md` 是**待 Owner 确认的草案**（:4），只写了缺口口径与规则表（:87、:113），没有可执行指令与可复核输出；`portfolio-analyzer` 只算集中度且依赖 `TradeRecord` 派生持仓（= 账本，属本波 out of scope）；`cli-report-portfolio` 只出集中度报告。产品参考里，IPS + 阈值再平衡已是成熟做法（[1][2][3]），缺的只是把政策值、快照与固定执行日变成一条可复算指令。

## What Changes

- 新增 capability `allocation-executor`：10 条 Requirement（R1–R10），把「缺口 → 剩余投放月数 → 当月金额 → 类别分配 → 顺延 → 再平衡提示 → 现金不足提示 → 快照时效拒绝」做成纯确定性、可手算复核的一条链，并守住「零 LLM / 只出工单」边界。Requirement 与来源锚点的映射见下表。
- 输入只有两处：`config/ips.yaml`（政策）与 `config/ips.local.yaml`（私人快照，含 `pool.total`、`allocation.current`、`holdings.total_market_value`、`holdings.as_of`）。快照里已有的派生字段 `deployment.gap_to_target` / `deployment.monthly_amount` **不得**当输入（必须由政策重算，见 R1），避免「抄旧结果」。
- 不修改任何既有 capability 的 spec；不写 `src/`、`test/`、不产 `knowledge-delta.md`、不改 `docs/mrd/`、不手改 `openspec/specs/`。
- 本波不引入任何 LLM 或联网数据源：金额、比例、顺延与提示全部由确定性代码产出（`docs/dev/engineering-conventions.md` §9.2 同口径）。
- 产品参考（IPS 条文、阈值再平衡、成本平均化）只借鉴「把政策写成可核对条文 + 固定间隔执行 + 只提示不调仓」的做法，不搬任何具体比例或工具（见「外部参考」[1]–[5]）。

### Requirement → 来源锚点 映射

| # | Requirement（`specs/allocation-executor/spec.md`） | 来源锚点 |
| --- | --- | --- |
| R1 | 政策与快照单一来源（派生字段不作输入） | 飞书 v2 §三 验收（annotations.md:15）；Owner #1/#4（annotations.md:23/26）；`config/ips.yaml:25-30`、`45-53`、`57-67` |
| R2 | 固定执行日与指令时点（每月最后一个周四） | Owner #2（annotations.md:24）；`config/ips.yaml:50` |
| R3 | 缺口与剩余投放月数可复算（`0.35 × pool − 权益市值`） | annotations.md §5 判据 1（:36）；`config/ips.yaml:48-49`；`docs/design/portfolio-plan-v0.1.md:87` |
| R4 | 当月金额、取整与期末归零 | annotations.md §5 判据 1（:36）；`config/ips.yaml:48-49` |
| R5 | 类别分配（权益宽基 ETF / 固收 30% 试水迁移 / 现金 0） | Owner #3（annotations.md:25）；`config/ips.yaml:26-29`、`41`、`47`、`52` |
| R6 | 权益超限顺延（>35% 顺延且不给金额；>40% 仅提示） | annotations.md §5 判据 2（:37）；`config/ips.yaml:51`、`57`；飞书 v2 §三 修订（annotations.md:16） |
| R7 | 快照时效拒绝（as_of 超 7 天） | Owner #4（annotations.md:26）；annotations.md §5 判据 3（:38）；`config/ips.yaml:67`、`11` |
| R8 | 再平衡提示（任一桶偏离 > 5pp，不自动调仓） | annotations.md §5 判据 4（:39）；`config/ips.yaml:61` |
| R9 | 现金不足提示（低于 R7 下限时给补足金额，不擅自改数） | `config/ips.yaml:66`、`29`；`docs/design/portfolio-plan-v0.1.md:113`；annotations.md:16（未验证阈值只作提示） |
| R10 | 零 LLM 与工单边界（不下单 / 不选股 / 不重建账本 / 不体检） | 飞书 v2 §五（annotations.md:17）；annotations.md §5 判据 5（:40）、§6（:44-46） |

## Capabilities

### New Capabilities

- `allocation-executor`：一期 P0 的**月度配置执行器**——读取 IPS 政策与当次手工快照，算出权益缺口、剩余投放月数、当月权益买入额（取整到元、末期归零），按类别分配（权益端只给「宽基 ETF」类别、固收端在迁移月给 30% 试水迁移金额、现金端不新增），并在权益超限时只给「顺延 + 理由」、快照过期时拒绝出指令、桶位偏离超 5pp 与现金低于下限时只给提示。全部数值可人工按公式复算，零 LLM、无网络、只出工单。

### Modified Capabilities

无。本波不改变任何既有 capability 的 spec 级行为。

### 与既有能力的关系

| 既有 capability | 关系 | 是否改其 spec |
| --- | --- | --- |
| `portfolio-analyzer` | **不复用**：它从 `TradeRecord` 派生持仓（= 账本重建，属本波 out of scope），且只算集中度；本执行器只消费手工快照。仅借鉴其「确定性计算 + 过期只提示」的写法 | 否 |
| `cli-report-portfolio` | **不修改**：输出契约互不替代；本波只新增 `ips plan` 类子命令（入口与命名由 T2 设计定） | 否 |
| `trade-record` / `trade-review-attribution` | **不触碰**：账本与成交复盘不在本波（annotations.md:44） | 否 |
| `backtest-engine` | **不依赖**：本波纯算术、前置依赖为零（annotations.md:12-13）；规则参数是否有效属回测台子，本波不引用其结论 | 否 |

## 成功标准（验收口径）

每条都可被 T4 逐条核对、被 T5 引用；判据是「命令输出 / 退出码 / 手算对照」，不是自评。

1. **金额可复算到元且与 ips 一致**：给定同一快照与同一日期，输出的缺口、剩余投放月数与当月金额可人工按 `0.35 × pool − 权益市值`、`缺口 ÷ 剩余月数` 复算到元；两次执行逐字段相同（幂等）；把 `allocation.target.equity` 改一格后金额随之重算（证政策未硬编码）[1]。
2. **权益超限只顺延不追高**：权益占比 > 35% 时当月买入额为 0，输出「顺延 + 理由」且**不出现买入金额**；> 40% 仅追加提示，不产出减仓/调仓金额（40% 未经回测验证，不作硬门禁）[2][3]。
3. **快照过期拒绝**：`as_of` 距计算日超过 7 天 → 非零退出码 + 明确「数据过期」说明，且不产出金额/类别；恰好 7 天允许执行；缺 `as_of` 同样拒绝。
4. **提示类输出不越界**：任一桶偏离目标 > 5pp → 再平衡提示（桶、偏差 pp、方向），不含调仓或买卖金额；现金低于 20% → 现金不足提示 + 补足金额，但不擅自把当月权益金额改成 0 [4][5]。
5. **期末归零**：目标月（2028-11）当月金额 = 当期全部缺口，按快照估值的权益缺口归零并标注「投放期结束」；目标月之后为 0 且不再出买入指令。

## 失败标准/反目标

任一条出现即本 change 失败：

- 把未验证阈值当硬门禁：用 40% 权益上限 / 单票 5% / 行业 25% / -15% 止损 / MA60 阻断或改写当月金额（这些只能提示；飞书 v2 §三 修订，annotations.md:16）。
- 用 LLM 生成或修改任何数值（缺口、月数、金额、比例、顺延判定）；或联网取价后再算数。
- 用过期快照出指令；或对缺 `as_of`、缺权益市值的快照猜数。
- 快照里的派生字段（`gap_to_target` / `monthly_amount`）被直接当结果抄出（必须重算）。
- 输出下单指令、具体交易标的（个股或 ETF 代码）、账本重建结果、持仓「持有/减仓/清仓」体检结论。
- 再平衡变成自动调仓（产出调仓金额或改持仓建议）。
- 金额不可复算：公式输入不回显、取整规则不写死、同一输入两次结果不同。
- 越界：改 `openspec/specs/`、写 `src/` `test/`、改 `docs/mrd/`、伪造 MRD 锚点。

## Impact

- **新增代码模块**（T3 落地，本波不写）：`src/service/allocation/`（models / loader / executor）、`src/apps/cli.py` 内新增 `ips plan` 类子命令；不新增第三方依赖，无网络依赖。
- **输入前置**：`config/ips.yaml` 已具备所需政策键（目标配置 `:25-30`、容许带 `:30`、`deployment` `:45-53`、`migration.trial_ratio` `:41`、`R4/R7/R8` `:61/66/67`）；`config/ips.local.yaml` 需含 `pool.total`、`allocation.current`（三桶占比）、`holdings.total_market_value`、`holdings.as_of`（现状已有，见 annotations.md:31），缺字段按配置错误拒绝而不是猜。
- **配置与文档**：`config/ips.yaml` 本波不改；`docs/mrd/mrd-v1.md` 待 Owner 定稿后回填锚点（T7 产出 diff 建议稿，本波不引用其编号）。
- **风险**：① 手工快照可能滞后 → 由 R7 拒绝而不是静默，代价是「可能当周无法出指令」；② 取整 `.5` 方向、固收迁移基数属 PM 口径假设（见下），Owner 未确认前按假设执行并由 spec 写死，避免两份实现；③ 顺延会造成后续单月金额放大（剩余月数递减重摊），若 Owner 要求「顺延额度独立入账」将触及账本，需另立 change；④ 宽基 ETF 具体标的未指定，指令只给类别，执行时人工选择。
- **回滚**：本波只新增 capability 与两个规划文件，未改代码/配置；若要撤，`git revert` 本次提交即可，不影响既有能力。

## out of scope（本波明确不做）

- **自动下单**：只产「买多少、买什么类别」的工单文本，交易由人工执行（飞书 v2 §五，annotations.md:17）。
- **选股 / 选标的**：不选个股、不指定 ETF 代码、不做全市场荐股排序（飞书 v2 §五；Owner #3 明确「具体标的未指定，不影响金额计算」annotations.md:25）。
- **账本重建**：不读成交明细、不重建逐笔持仓、不做 FIFO；只消费手工快照（annotations.md:44）。
- **持仓体检**：不做「持有/减仓/清仓」判定（依赖回测规则，属 P1，annotations.md:45）。
- **LLM 叙事**：不调用任何 LLM，不生成解释性长文；理由文本由确定性模板产出（annotations.md:40；engineering-conventions §9.2）。
- **再平衡自动调仓**：只提示偏离，不产出调仓金额或改持仓建议（annotations.md:39）。
- **回测规则验证**：不验证 40/5/25/-15/MA60 等阈值是否有效（属 `backtest-engine` 及其后续实验）。
- **Web UI / 宏观债券研究 / 报告渲染**：飞书 v2 §五；渲染归既有 `service/report` 能力。

## Case 复现锚点

本波让 case 从「知道该买、但没有任何规则」变成「每月固定日有一条可复算指令」，对应 `docs/cases/case-20261115-allocation-executor/annotations.md` 的 5 条可证伪判据：

| case 判据 | 现状（X） | 本波（Y） | 落点 |
| --- | --- | --- | --- |
| §5-1 金额可复算到元、与 ips 一致 | 零散手算，无固定输出 | 输出公式输入 + 取整规则，T5 逐条手算核对 | R1 / R3 / R4 |
| §5-2 权益 > 35% 顺延且不给买入金额 | 无规则 | 顺延 + 理由 + 0 金额；>40% 仅提示 | R6 |
| §5-3 快照 > 7 天拒绝 | 无时效门禁 | 非零退出码 + 过期说明，不出指令 | R7 |
| §5-4 任一桶偏离 > 5pp 提示、不自动调仓 | 无提示 | 再平衡提示（含偏差 pp），无调仓金额 | R8 |
| §5-5 零 LLM、无网络 | 无执行链 | 纯确定性代码，输出只含类别与金额 | R10 |

## 外部参考

> **本波 T1 的 inScope 只有 `proposal.md` 与 `specs/allocation-executor/spec.md` 两个文件**，故参考直接内联在本节（不另建 `reference/product/REFERENCES.md`，避免越出任务契约）；若后续需要拆成独立索引，由 T7 归档时迁移。

| 序号 | 参考（标题 / URL） | 借鉴什么 | 明确不借鉴 | 落点 |
| --- | --- | --- | --- | --- |
| [1] | Bogleheads Wiki — *Investment policy statement* <https://www.bogleheads.org/wiki/Investment_policy_statement> | 把「目标配置 + 再平衡区间」写成可核对的 IPS 条文，明确目标与再平衡触发范围 | 不搬其具体资产比例与税务安排（A 股/国内税制不同） | R1 / R8 |
| [2] | Bogleheads Wiki — *Rebalancing* <https://www.bogleheads.org/wiki/Rebalancing> | 绝对 5% 偏离带（5/25 规则的 5% 部分）作为再平衡提示的常见阈值 | 不采纳「相对 25% 规则」与具体调仓动作（本波只提示） | R8 |
| [3] | Vanguard — *Rebalancing your portfolio* <https://investor.vanguard.com/investor-resources-education/portfolio-management/rebalancing-your-portfolio> | 阈值触发（threshold-based）而非凭感觉调仓；再平衡应事先写进政策 | 不采纳其年度复核节奏与具体阈值 | R6 / R8 |
| [4] | Vanguard — *How to invest a lump sum of money*（DCA vs lump-sum）<https://investor.vanguard.com/investor-resources-education/online-trading/dollar-cost-averaging-vs-lump-sum> | 固定间隔、固定金额投入的定义与「减少择时」的表述，支撑「固定日 + 不择时」 | 不采纳「一次性投入更优」的结论（Owner 已定 24 个月分批，annotations.md:23） | R2 / R4 |
| [5] | Vanguard Research — *Cost averaging: Invest now or temporarily hold your cash?* <https://corporate.vanguard.com/content/dam/corp/research/pdf/cost_averaging_invest_now_or_temporarily_hold_your_cash.pdf> | 成本平均化与一次性投入的对照方法，用于说明「分批是政策选择而非收益预测」 | 不把其研究结论当本波政策；本波只做执行工具 | R2 / Why |

## 假设/开放问题

> **MRD v1 仍未定稿，本波没有任何 MRD 锚点可引用**：`docs/mrd/mrd-v1.md` 的 §1–§7 全部是占位（`<为什么现在做、不做会怎样>` / `TODO` / 空的 `OPEN-1`），本波需求锚点 = 飞书《投资Agent》v2 §三/§四/§五（`annotations.md:11-17`）+ Owner 2026-11-15 四条答复（`annotations.md:19-26`）+ 仓库一手材料（`config/ips.yaml`、`docs/design/portfolio-plan-v0.1.md`、`openspec/specs/`）。`docs/mrd/mrd-v2.md` 是**上一波回测台子的建议稿、待 Owner 确认**，本波**不引用**其编号（其 §7 明确「本文仍非定稿」）。MRD 定稿后由 T7 回填正式锚点编号，本波**不虚构**任何 MRD 编号；MRD-v1 §7 的 `OPEN-1` 编号只声明「未在本波解决」，不填内容。

**已由 Owner 答复、本波直接落值（非假设）**

| # | 口径 | 落值 | 来源 |
| --- | --- | --- | --- |
| O1 | 权益目标与投放期限 | 权益 35%、期限 24 个月（目标日 2028-11-30） | Owner #1（annotations.md:23）+ `config/ips.yaml:26-30`、`48-49` |
| O2 | 执行日 | 每月最后一个周四（`execution_day: last_thursday`） | Owner #2（annotations.md:24）+ `config/ips.yaml:50` |
| O3 | 买什么类别 | 权益端只买宽基 ETF（标的不指定）；固收端先按 30% 试水迁移 | Owner #3（annotations.md:25）+ `config/ips.yaml:41`、`52` |
| O4 | 数据来源与时效 | 手工快照；`as_of` 超 `R8_stale_days=7` 天拒绝给指令 | Owner #4（annotations.md:26）+ `config/ips.yaml:67` |

**假设（Owner 未答复前按此执行；spec 已把行为写死，避免实现各自发挥）**

| ID | 假设 | 依据 / 若假设不成立的影响 |
| --- | --- | --- |
| A1 | **投放月推导**：首个定投月 = `target_date` 所在月 − `horizon_months` + 1 = **2026-12**；固收迁移月 = 首个定投月 − (`start_month` − 1) = **2026-11**；剩余投放月数 = `max(当前执行月, 首个定投月)` 到目标月的含端点月份数 | 依据 `config/ips.yaml:47-49`（start_month=2 / 24 月 / 目标日 2028-11-30）；与 `ips.local.yaml` 现有 `monthly_amount = round(gap ÷ 24)` 一致（annotations.md:31）。若 Owner 以别的起点计「第 1 个月」，起始月会顺移，届时按配置错误暴露（不静默） |
| A2 | **取整规则**：每月金额四舍五入到元（.5 向上）；目标月用「当期全部缺口」补齐使缺口归零 | `ips.local.yaml` 的 `monthly_amount` 只证明「整除到元」，未证明 .5 方向；故 .5 进位方向为 PM 口径假设，待 Owner 确认（Q1） |
| A3 | **固收迁移基数**：迁移金额 = `allocation.target.fixed_income × pool × migration.trial_ratio` = `0.45 × pool × 0.30`，仅在迁移月输出一次 | Owner 只答「先按 30% 试水迁移」，未说基数与次数；本波按「目标固收额度的一次性 30%」执行（Q2）。若实际含义不同（如每月 30%），R5 金额需改，属口径变更 |
| A4 | **顺延不独立记账**：顺延月买入额 = 0，不累积「待补额度」，由剩余月数递减在后续月份重新均摊 | 落实「不做账本」；若 Owner 要求顺延额度独立入账，触及账本，另立 change（Q4） |
| A5 | **现金不足只提示**：现金占比低于 `R7_cash_floor=0.20` 时给出补足金额与「优先补现金」说明，但不把当月权益金额自动改成 0 | 未验证阈值不得升格为硬门禁（annotations.md:16 同一口径）；`portfolio-plan-v0.1.md:113` 的 R7 动作「暂停权益买入」由人工按提示执行（Q3） |
| A6 | **权益市值口径**：缺口中的「当前权益市值」取快照 `holdings.total_market_value`（个股 + ETF 合计）；三桶占比取 `allocation.current`；两者必须来自同一 `as_of` | `ips.local.yaml` 现状可核对：`gap_to_target = 0.35 × pool − holdings.total_market_value`（annotations.md:31）；若快照只有占比无市值，按缺字段拒绝而不是猜 |

**开放问题（已按表单式经 captain 转交 Owner；未答复前按上表假设执行，不擅自定稿）**

| ID | 问题（一句话） | 影响需求 | 状态 |
| --- | --- | --- | --- |
| Q1 | 金额取整到元时 `.5` 进位方向（向上 / 向下 / 银行家舍入）？ | R4 | **待 Owner 确认**；本波按「四舍五入、.5 向上」 |
| Q2 | 固收 30% 试水迁移的基数（目标固收额度 45% × pool）与次数（一次还是每月）？ | R5 | **待 Owner 确认**；本波按「一次性、45% × pool × 30%」 |
| Q3 | 现金低于 20% 时是否要把权益买入置 0（硬门禁），还是只提示由人工决定？ | R9 | **待 Owner 确认**；本波按「只提示、不改数」 |
| Q4 | 顺延额度是否需要独立记账/结转（会触及账本，属 P2 边界）？ | R6 | **待 Owner 确认**；本波按「不独立记账、自然重摊」 |
| Q5 | 宽基 ETF 是否指定候选标的池（如 A500 / 沪深 300）？ | R5 | **待 Owner 确认**；本波只给类别，不选代码 |

> 触及飞书 v2 §三「40/5/25 三条上限」与止损/MA60 的口径：本波只在权益超 40% 时作提示，**不**把它们写成门禁、不产出减仓建议；这些阈值是否有效由回测结果决定（annotations.md:16）。

## 附：T1 校验证据

> 环境：Windows 11 + `openspec` 只走 `openspec.cmd` shim（`docs/agent-team/ENV.md`）；分支 `feature/add-allocation-executor`，基线 HEAD `ef6d70b`。证据 = 命令 + 退出码 + 原样输出。

### 1. 验收命令（strict 校验）

```text
$ openspec.cmd validate add-allocation-executor --strict
Change 'add-allocation-executor' is valid
[exit code: 0]
```

### 2. 验收项结构自检（Requirement / SHALL / 来源锚点 / Scenario / 覆盖 / 反目标）

```text
$ python - <<'PY'
import re,sys
prop='openspec/changes/add-allocation-executor/proposal.md'
spec='openspec/changes/add-allocation-executor/specs/allocation-executor/spec.md'
pt=open(prop,encoding='utf-8').read(); st=open(spec,encoding='utf-8').read()
ok=True
def chk(name,cond):
    global ok
    print(('PASS' if cond else 'FAIL'),name); ok = ok and cond
heads=['## Why','## What Changes','## Capabilities','### New Capabilities','### Modified Capabilities',
       '## 成功标准（验收口径）','## 失败标准/反目标','## Impact','## out of scope（本波明确不做）',
       '## 外部参考','## 假设/开放问题','## Case 复现锚点']
for i,h in enumerate(heads,1): chk(f'proposal-section-{i}', h in pt)
chk('mrd-v1-not-finalized-stated', 'MRD v1 仍未定稿' in pt)
chk('added-requirements-header', '## ADDED Requirements' in st)
reqs=re.findall(r'### Requirement: (.+?)\n\n(.+?)(?=\n#### Scenario:|\n### Requirement:|\Z)', st, re.S)
chk('requirement-count-10', len(reqs)==10)
for i,(name,body) in enumerate(reqs,1):
    seg=st.split('### Requirement: '+name)[1].split('\n### Requirement: ')[0]
    chk(f'R{i}-shall', 'SHALL' in body.strip())
    chk(f'R{i}-anchor', '来源锚点：' in seg)
    chk(f'R{i}-scenario', len(re.findall(r'#### Scenario: ',seg))>=1)
n=st.count('#### Scenario:')
chk('scenario-count-28', n==28)
chk('all-scenarios-when-then', st.count('- **WHEN**')==n and st.count('- **THEN**')==n)
for i,kw in enumerate(['可复算','顺延','数据过期','再平衡','现金不足','投放期结束'],1):
    chk(f'coverage-{i}', kw in st)
oos=pt.split('## out of scope（本波明确不做）')[1].split('## Case 复现锚点')[0]
for i,kw in enumerate(['自动下单','选股','账本重建','持仓体检','LLM'],1):
    chk(f'out-of-scope-{i}', kw in oos)
print('SUMMARY requirements=%d scenarios=%d anchors=%d' % (len(reqs), n, st.count('来源锚点：')))
sys.exit(0 if ok else 1)
PY
PASS proposal-section-1
PASS proposal-section-2
PASS proposal-section-3
PASS proposal-section-4
PASS proposal-section-5
PASS proposal-section-6
PASS proposal-section-7
PASS proposal-section-8
PASS proposal-section-9
PASS proposal-section-10
PASS proposal-section-11
PASS proposal-section-12
PASS mrd-v1-not-finalized-stated
PASS added-requirements-header
PASS requirement-count-10
PASS R1-shall
PASS R1-anchor
PASS R1-scenario
PASS R2-shall
PASS R2-anchor
PASS R2-scenario
PASS R3-shall
PASS R3-anchor
PASS R3-scenario
PASS R4-shall
PASS R4-anchor
PASS R4-scenario
PASS R5-shall
PASS R5-anchor
PASS R5-scenario
PASS R6-shall
PASS R6-anchor
PASS R6-scenario
PASS R7-shall
PASS R7-anchor
PASS R7-scenario
PASS R8-shall
PASS R8-anchor
PASS R8-scenario
PASS R9-shall
PASS R9-anchor
PASS R9-scenario
PASS R10-shall
PASS R10-anchor
PASS R10-scenario
PASS scenario-count-28
PASS all-scenarios-when-then
PASS coverage-1
PASS coverage-2
PASS coverage-3
PASS coverage-4
PASS coverage-5
PASS coverage-6
PASS out-of-scope-1
PASS out-of-scope-2
PASS out-of-scope-3
PASS out-of-scope-4
PASS out-of-scope-5
SUMMARY requirements=10 scenarios=28 anchors=10
[exit code: 0]

