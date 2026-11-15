# Design: add-allocation-executor

> change：`add-allocation-executor`　分支：`feature/add-allocation-executor`　角色：architect（T2）
> 写作基线：依赖 T1 `proposal.md` / `specs/allocation-executor/spec.md` 与 K1 `knowledge-delta.md`。
> 本文件把 10 条 Requirement 落成可执行技术方案：CLI 契约、金额公式与取整、幂等、A–H 清单、被否方案、影响面、风险回滚。**不写代码**（`src/`、`test/` 属 T3）。

## Context

一期 P0 第二项「配置执行器」：在每个固定执行日，把 IPS 目标配置、投放期限与当次手工快照做**纯算术**，产出「当月买多少、买什么类别」的可复核工单；权益超限顺延、快照过期拒绝、桶位偏离与现金不足只提示。零 LLM、无网络、不下单、不选股、不重建账本、不持仓体检（proposal `## What Changes`；annotations.md:11-17）。

本波要解决的问题是**现有仓库没有可执行入口**：`config/ips.yaml` 只存政策、`config/ips.local.yaml` 只存私人快照，两者之间没有「缺口 ÷ 期限 → 当月金额」的确定性计算链（proposal:12）。设计目标是把这条链做成「同输入同输出、金额可手算到元、过期即拒绝」的 CLI 子命令。

环境约束（`docs/agent-team/ENV.md`，本机实测）：
- 本机**无 `python3`**，一律 `python`；`openspec` 只能走 `openspec.cmd` shim。
- PyYAML 6.0.3 已装；`decimal` / `calendar` / `argparse` 均 Python 标准库，**不新增第三方依赖**。
- 分层（`docs/dev/engineering-conventions.md`）：`src/apps/cli.py` 是 CLI 入口；`src/service/<module>/` 放确定性服务；`test/`（工程师）、`test/qa/`（QA 盲测）。
- 确定性纪律（engineering-conventions §9.2）：**数值生成与比较必须由代码完成，禁止 LLM**。

口径事实（T1 已定 + K1 已裁决，逐条可复核）：
- 政策唯一生效载体 = tracked `config/ips.yaml`；私人快照 = ignored `config/ips.local.yaml`（`holdings.as_of` 是时效判定字段，非 `updated_at`，knowledge-delta KD-8-01）。
- 执行日 = **每月最后一个周四**（Owner #2；冲突裁决「最后一个工作日前的周四」作废，knowledge-delta 冲突1）。
- 期限 = **24 个月**、目标日 `2028-11-30`（Owner #1；冲突2 取 24，弃草案 12）。
- 试水迁移 = **30%**（Owner #3；冲突3 取 30，弃草案 20%–30% 区间下限）。
- 知识层已落 5 条 canon（K2 已完成）：`CAN-ALLOC-001…005` + 上位 `CAN-IPS-001`；未确认口径进 `known_unknowns.yaml`（`KU-2026-11-alloc-*` 6 条）。执行器**运行时只读 `config/ips.yaml` + `config/ips.local.yaml`，不读知识库**——知识层是治理索引，不是第二配置源。

## Goals / Non-Goals

**Goals**
1. 明确 `ips plan` 的 CLI 契约：参数、输入文件、输出字段、退出码 0/1/2 语义。
2. 把金额公式与取整规则写死到「可手算到元」，输入回显 + 幂等。
3. 把 R1–R10 逐条指到落地模块/函数，画出确定性状态机的判定顺序。
4. 明确「提示 vs 硬门禁」边界：40/5/25/-15/MA60、现金 20%、再平衡 5pp 全部只提示，唯一硬门禁是「快照过期拒绝」。

**Non-Goals**（本波明确不做，T3 也不得实现）
- 自动下单、选股/选标的（ETF 代码）、账本重建、持仓体检、LLM 叙事。
- 交易日/节假日顺延（KQ-1 未答复，见 Open Questions）。
- 顺延额度独立记账/结转（Q4 未答复，触账本）。
- 在 `config/app.yaml` 复制政策（政策唯一载体是 `ips.yaml`）。
- 落盘 run 目录/实验台账/知识条目（T2/T3 不写 `config/knowledge/`、不建 artifact）。

## Agent 架构决策（A–H，逐项作答）

> 本波是**单进程、零 LLM、纯确定性**的算术 CLI，多智能体与 LLM 相关项绝大多数是「本波不涉及 + 原因」；唯一有实质的是 D（可信）与 F（数据注入面）。每项都有决策或显式 N/A。

**A. LLM / 确定性代码边界** —— 决策：**零 LLM 调用点**。
全部金额、比例、顺延判定、提示、时效拒绝由 `src/service/allocation/`（纯函数 + 状态机）完成；理由文本由**确定性模板**（固定文案 + 回显数值）产出，不调用 LLM。反模式（把字段校验/数字比对交给 LLM）天然规避。锚点：engineering-conventions §9.2、spec R10。**没有**「LLM 可用/不可用降级」问题，因为没有 LLM。

**B. 编排 / 能力边界** —— 决策：**单进程调用链，无编排层、无多 agent 拓扑**。
`argparse` 子命令 `ips plan` → `service/allocation/loader`（读两个 YAML）→ `service/allocation/executor`（纯函数 `compute_plan`）→ `render_plan`（文本/JSON）。无全局状态、无 subAgent fork、无检索路径、无回环。交接契约 = 纯函数入参/出参（dataclass），不落会话记忆。

**C. 知识层实现（消费 `config/knowledge/_design.md`）** —— 决策：**运行时零读库；代码注释可引用 canon id，真源是 `config/ips.yaml`**。
- 分层/准入/升降级语义由 K1 定（`_design.md` §1/§3），本设计**不改层语义**，只消费结论。
- 5 条 canon（`CAN-ALLOC-001…005`）已由 K2 落库，作为「口径治理索引」；执行器代码注释可写 `# 见 CAN-ALLOC-004`，但注释不是真源，运行时取值一律来自 `config/ips.yaml` 对应行（`_design.md` §2.4/§4.2 护栏：canon 不得成为第二配置源）。
- 取整 `.5` 方向、迁移基数/次数、现金门禁、顺延结转、节假日：均为 `known_unknowns.yaml` 的 `KU-2026-11-alloc-*` 待确认项，执行器按 proposal A2–A5 假设执行并在输出标「待确认」，**不预埋未经来源确认的默认数值**（唯一例外：取整 `.5` 向上是 A2 假设 + 固有逻辑，落「代码常量 + 单测」，不进知识层，`_design.md` §0.0 Q2 / §4.1）。

**D. 可信保证** —— 决策：**可复算 = 回显输入 + 纯函数 + 单测手算对照；可拒绝 = 缺键/过期两类退出码**。
- **可复算**：输出回显全部公式输入（目标比例、`pool.total`、权益市值、缺口公式、剩余月数、取整规则、`as_of`、各阈值），人工可按公式手算到元；`compute_plan` 是纯函数，同输入逐字段同输出（幂等）。
- **可拒绝**：缺键/缺字段 → exit 1；快照过期（>7 天）或未来快照 → exit 2；缺 `holdings.total_market_value` → exit 1（R3 拒绝执行，不猜数）。
- **派生字段不作输入**：`deployment.gap_to_target` / `deployment.monthly_amount` 不进入 `compute_plan` 输入，结果必由政策与原始市值重算（R1 反「抄旧结果」）。
- **明账/暗账**：本波唯一产物是 stdout 工单文本（给人看的明账），无实验台账/账本重建（暗账不适用）；工单文本本身即可复核物，**不新增落盘 trace/run 目录**（T5 由 QA 跑命令留证）。
- **防幻觉**：零 LLM，数值不可能被 LLM 自由发挥（A 决策）。

**E. LLM 非功能需求** —— 决策：**全部 N/A（零 LLM）**。
数据不进上下文（无 LLM 上下文）；每环节 LLM 调用次数 0、成本 0；模型分级不适用；全部输出确定性；无 LLM 不可用的降级/重试/超时。

**F. 数据与工具层** —— 决策：**本地双 YAML 单源，`yaml.safe_load`，无网络/无 API/无 DB**。
- 数据源 = `config/ips.yaml`（政策）+ `config/ips.local.yaml`（快照），由 `loader` 用 PyYAML `safe_load` 读入；无优先级路由（单一来源）。
- 派生字段拒绝 = loader 不把 `deployment.gap_to_target`/`monthly_amount` 暴露给 executor（结构上隔离，而非读后再弃）。
- 注入面：无 prompt、无工具调用、无网络。YAML 反序列化用 `safe_load`（禁 `yaml.load`）；`--as-of` 用 `date.fromisoformat` 严格解析，坏日期 → exit 1。
- 密级：`ips.local.yaml` 是私人快照（gitignored）；工单含个人金额只打印到 stdout，不落文件、不外发、不联网。

**G. 评测与自进化** —— 决策：**质量 = 单测手算对照 + QA 盲测 + 幂等；无 LLM 质量指标**。
无完成率/幻觉率/成本指标（零 LLM）。确定性模块必须有单测（engineering-conventions:279）；「自进化」不适用——知识回流走 K1/K2/K3/T7 知识线，不是执行器运行时职责。

**H. Agent 特有反模式（逐项规避）** —— 决策：**全部不适用或已规避**。
- 无限循环：纯函数 + 有限状态机，无 while/递归。
- fork 爆炸：无 subAgent。
- 上下文膨胀：无 LLM 上下文。
- LLM 幻觉进数据流：零 LLM，不可能。
- prompt 与代码职责不清：无 prompt。

## CLI 契约

```
python -m apps.cli ips plan --as-of <YYYY-MM-DD> [--json]
```

- `ips` 为顶层子命令（与 `report`/`backtest`/`trade` 平级），`plan` 为其子子命令；在既有 `src/apps/cli.py` 内扩展，不另建入口。
- `--as-of`：**计算日**（ISO 日期 `YYYY-MM-DD`）。省略时默认取本机当日日期。它是时效判定与执行月推导的唯一「现在」参照，不含行情。格式错 → exit 1（用法/数据错误），不等价于 argparse 的 usage-exit。
- `--json`（可选）：输出结构化 JSON（键见下表），供 T4/T5 机检；缺省输出人类可读工单文本。

**输入**（只读，不写回）
| 文件 | 读取字段 | 缺失/类型错处理 |
| --- | --- | --- |
| `config/ips.yaml`（政策） | `allocation.target.{equity,fixed_income,cash}`、`deployment.{start_month,horizon_months,target_date,execution_day,skip_if_equity_above}`、`fixed_income_detail.migration.trial_ratio`、`rules.{R1_equity_cap,R4_rebalance_band,R7_cash_floor,R8_stale_days}` | `AllocationConfigError` → exit 1 |
| `config/ips.local.yaml`（快照） | `pool.total`、`allocation.current.{equity,fixed_income,cash}`、`holdings.{total_market_value,as_of}` | `AllocationConfigError` → exit 1 |
| 明确**不读** | `ips.local.yaml` 的 `deployment.gap_to_target` / `deployment.monthly_amount`（派生字段，R1） | — |

**输出字段**（文本与 `--json` 同构）
`执行月/执行日`、`缺口`、`剩余投放月数`、`当月权益买入额`、`类别分配`（权益=宽基 ETF / 固收迁移金额 / 现金=0）、`顺延`（标志 + 理由，或「无」）、`再平衡提示`（桶/当前/目标/偏离 pp/方向，或「无」）、`现金不足提示`（补足金额，或「无」）、`时效`（`as_of`、距计算日天数、阈值、判定）、`理由`（确定性文案）、`回显`（目标比例/期限/阈值/取整规则/`as_of`，供人工核对「与 ips 一致」）。

**退出码**
| 码 | 语义 | 触发 |
| --- | --- | --- |
| 0 | 成功 | 产出工单（含顺延、再平衡提示、现金不足提示、投放期已结束——都是正常结果） |
| 1 | 配置或数据错误 | 政策/快照缺键、类型错、YAML 解析失败、`--as-of` 格式错、缺 `holdings.as_of`/`total_market_value`/`pool.total` |
| 2 | 不可执行 | 快照过期（`as_of` 距计算日 > `R8_stale_days`）；快照 `as_of` 晚于计算日（未来快照） |

> 与 `backtest` 先例对齐（`src/apps/cli.py:2023-2045`：0 成功 / 1 参数·配置·数据 / 2 门禁失败）；`ips plan` 的「2」= 时效门禁失败。缺 `as_of` 是**缺字段**（数据错误，exit 1），过期/未来是**时点不可用**（exit 2），二者都在 R7 的「拒绝」范围内、只是退出码不同。

## 金额公式与取整规则（可手算到元）

> 所有金额用 `Decimal`，输入经 `Decimal(str(x))` 读取，避免浮点误差（确定性纪律）。下面 `T_eq` 等为政策值，`pool`/`eq_mv`/`cur` 为快照值。

**常量（来自 `config/ips.yaml`）**
```
T_eq=0.35  T_fi=0.45  T_cash=0.20        # allocation.target
skip=0.35  cap=0.40  band=0.05  cash_floor=0.20  stale_days=7
horizon=24  target_date=2028-11-30  start_month=2  trial_ratio=0.30
execution_day=last_thursday
```

**派生（月份为「年月」粒度，按月算术，不跨日）**
```
target_month    = 2028-11                              # target_date 所在月
first_month     = target_month − (horizon − 1) 个月 = 2026-12   # 首个定投月
migration_month = first_month − (start_month − 1) 个月 = 2026-11  # 迁移月
execution_month/day = resolve(as_of_calc)              # R2：计算日当日或之后最近的「当月最后一个周四」
remaining_months   = 含端点月份数( max(execution_month, first_month) , target_month )
gap                = T_eq × pool − eq_mv               # 可为负
cash_mv            = cur.cash × pool
```

**取整函数（写死，唯一取整规则）**
```
round_yuan(x) = Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
```
即「四舍五入到整数元、`.5` 向上」（proposal A2；Q1 待 Owner 确认，输出中必须回显此规则并标「取整方向待确认」，见 Open Questions）。

**当月权益买入额（判定顺序 = 确定性状态机，首个命中即止）**
```
1. execution_month > target_month           → 权益=0，理由「投放期已结束」（R4）
2. execution_month == migration_month       → 权益=0，固收迁移金额 = round_yuan(T_fi × pool × trial_ratio)，
                                              理由「迁移月，只做固收迁移；定投自 first_month 起」（R5）
3. cur.equity > skip                        → 权益=0，理由「顺延：权益占比 cur.equity > skip」；
                                              若 cur.equity > cap 追加提示「权益超过 R1 上限 40%（未经回测验证，仅提示）」（R6）
4. gap ≤ 0                                  → 权益=0，理由「缺口为负/零，不卖出」（R4）
5. execution_month == target_month          → 权益 = round_yuan(gap)，理由「目标月补齐，投放期结束」（R4）
6. 否则                                     → 权益 = round_yuan(gap / remaining_months)，类别「宽基 ETF」（R4）
```

**类别分配（R5）**：权益金额只投「宽基 ETF」类别（不产出代码）；固收仅在迁移月输出 `round_yuan(T_fi × pool × trial_ratio)`；现金当月新增恒 0。

**提示（不改任何金额，R8/R9）**
```
rebalance_hint: 对每个桶 b ∈ {equity, fixed_income, cash}：
                  dev = cur[b] − T_b；若 |dev| > band → 提示（桶/当前/目标/dev pp/方向）
cash_hint:      若 cash_mv < cash_floor × pool → 提示 + 补足金额 round_yuan(cash_floor × pool − cash_mv)
                （不把当月权益买入额改成 0）
```

**时效判定（R7，唯一硬门禁）**
```
days = (as_of_calc − holdings.as_of).days
days >  stale_days            → AllocationStaleError（exit 2）
days == stale_days 或 更小     → 允许
holdings.as_of 缺失           → AllocationConfigError（exit 1）
holdings.as_of 晚于 as_of_calc → AllocationStaleError（exit 2，未来快照）
```

**手算对照示例（合成数，与 spec R3/R5/R9 场景一致；不用 `ips.local.yaml` 私人数值）**
```
pool=1,000,000  eq_mv=250,000  T_eq=0.35  T_fi=0.45  trial_ratio=0.30
gap = 0.35 × 1,000,000 − 250,000 = 100,000
2026-12 常规月：remaining=24，monthly = round_half_up(100000/24) = round_half_up(4166.666…) = 4167
2026-11 迁移月：固收迁移 = round_half_up(0.45 × 1,000,000 × 0.30) = 135,000，权益=0
现金不足：cash_mv=150,000 < 0.20 × 1,000,000=200,000 → 补足 = 200,000 − 150,000 = 50,000（权益买入额不变）
```

**幂等**：`compute_plan(policy, snapshot, as_of_calc)` 是纯函数——不读时钟（`--as-of` 缺省取 today 时，today 是显式入参）、不读随机数、不写任何状态；同输入两次输出逐字段一致（含理由文本，理由由固定模板 + 回显值产生）。

## Decisions（R1–R10 → 落地位置）

| Requirement | 落地模块 / 函数（T3 实现） | 决策 / 理由 / 取舍 |
| --- | --- | --- |
| R1 政策与快照单一来源 | `service/allocation/loader.py::load_ips_policy()` / `load_snapshot()`；`models.py::PlanInput` | 只读 `config/ips.yaml` + `config/ips.local.yaml`；派生字段不进 `PlanInput`（结构隔离）。输出回显目标比例/期限/阈值/`as_of`。**不**在 `config/app.yaml` 复制政策（见被否方案 否-A） |
| R2 固定执行日与指令时点 | `service/allocation/executor.py::resolve_execution_month_day(as_of_calc)` | 用 `calendar` 求「当月最后一天，向前回退到周四」= 当月最后一个周四；计算日已过该日则取下一月。不接任何行情输入；节假日不特殊处理（KQ-1 待确认） |
| R3 缺口与剩余月数 | `executor.py::compute_gap()` / `compute_remaining_months()` | 缺口 = `Decimal(T_eq)×pool − Decimal(eq_mv)`；剩余月数 = `max(执行月, 首个定投月)` 到目标月含端点。缺 `holdings.total_market_value` → `AllocationConfigError`（exit 1），不猜数 |
| R4 当月金额/取整/期末归零 | `executor.py::compute_monthly_amount()` + `round_yuan()` | 见「金额公式与取整」状态机；`ROUND_HALF_UP` 到元；目标月补齐、期末/负缺口归 0。取整 `.5` 方向 = A2 假设 + 单测锁定（固有逻辑，不进 canon） |
| R5 类别分配 | `executor.py::allocate_categories()` | 迁移月只出固收迁移（权益 0）；定投月起只出「宽基 ETF」类别（无代码）；现金 0。迁移金额不依赖权益缺口（迁移是固收桶再配置） |
| R6 权益超限顺延 | `executor.py::decide_defer()` | `cur.equity > skip` → 顺延（0 + 理由）；`> cap` 追加**提示**，不改顺延判定、不产减仓金额。顺延不记账、由剩余月数递减重摊（A4） |
| R7 快照时效拒绝 | `executor.py::assert_fresh()` | `as_of_calc − holdings.as_of` 天数 > `stale_days` → `AllocationStaleError`（exit 2）；缺失 → `AllocationConfigError`（exit 1）；未来 → exit 2。恰好 7 天允许 |
| R8 再平衡提示 | `executor.py::rebalance_hints()` | 三桶 `|cur[b] − T_b| > band` → 提示；不改金额、不产调仓金额 |
| R9 现金不足提示 | `executor.py::cash_floor_hint()` | `cash_mv < cash_floor × pool` → 提示 + 补足金额；不改当月权益买入额（不把 20% 升格为硬门禁，A5） |
| R10 零 LLM 与工单边界 | `executor.py::compute_plan()` + `render_plan()` / `render_plan_json()` | 全链路确定性；输出只含类别与金额、无代码/下单指令/体检结论；理由由固定模板产生 |

**异常模型（命名由 design 定，T3 落 `models.py`，复用 `common.exceptions.StockCopilotError`）**
```
AllocationError(StockCopilotError)          # 域根
AllocationConfigError(AllocationError)      # 缺键/类型错/YAML错 → exit 1
AllocationStaleError(AllocationError)       # 过期/未来快照 → exit 2
```
语义对齐 `MissingBacktestConfigError`（`src/common/exceptions.py:41-42`：「缺键不得按 0 或默认值继续」），但定义在 `service/allocation/models.py`（`src/common/exceptions.py` 不在 T3 inScope，且 allocation 无需跨 data_provider 共享）。

## Rejected Alternatives（≥1，含理由）

1. **否-A：在 `config/app.yaml` 新增 `allocation:` 段复制政策值。** 否决：政策唯一生效载体是 `config/ips.yaml`（R1），复制会造成「同一口径两处维护、两处漂移」（K1 护栏、`_design.md` §2.4/§4.2）。执行器直接读 `ips.yaml`；`config/app.example.yaml` 本波**不改动**。
2. **否-B：用 `allocation.current.equity × pool` 反推权益市值，替代 `holdings.total_market_value` 参与缺口。** 否决：spec R3 明确缺口用 `holdings.total_market_value`；占比可能四舍五入，反推会引入误差，与「金额可手算到元、与 ips 一致」冲突。市值与占比各自独立读取（同 `as_of`），不做交叉数值校验。
3. **否-C：把 40/5/25/-15/MA60 写成硬门禁改写当月金额。** 否决：annotations.md:16 已把它们移出验收标准、只能提示（飞书 v2 §三 修订）；写成门禁 = 复活已撤销的门禁，违反失败标准。
4. **否-D：顺延额度累积结转（待补额度）。** 否决：触及账本（P2 边界），A4 明确「不独立记账、由剩余月数递减重摊」；若 Owner 要求结转 → 另立 change。
5. **否-E：用 LLM 生成理由文本。** 否决：R10 零 LLM；理由由确定性模板 + 回显值产生。

## 影响面（到文件，禁止「相关模块」）

**本波（T2，architect 写）**
- `openspec/changes/add-allocation-executor/design.md`（本文件）
- `openspec/changes/add-allocation-executor/tasks.md`

**T3（engineer 实现，本波不写）**
- 新增 `src/service/allocation/__init__.py`
- 新增 `src/service/allocation/models.py`（dataclass + `AllocationError`/`AllocationConfigError`/`AllocationStaleError`）
- 新增 `src/service/allocation/loader.py`（`load_ips_policy` / `load_snapshot`）
- 新增 `src/service/allocation/executor.py`（`resolve_execution_month_day` / `compute_gap` / `compute_remaining_months` / `compute_monthly_amount` / `round_yuan` / `decide_defer` / `allocate_categories` / `rebalance_hints` / `cash_floor_hint` / `assert_fresh` / `compute_plan` / `render_plan` / `render_plan_json`）
- 修改 `src/apps/cli.py`（新增 `ips` 子命令 + `plan` 子子命令 + `--as-of`/`--json` + `run_ips_plan()`；`main()` 增加 `ips` 分支）
- 新增 `test/service/allocation/test_executor.py`（手算对照 + 幂等 + 边界）
- 新增 `test/apps/test_cli_ips_plan.py`（退出码 0/1/2 + stderr 文案 + `--json`）
- `config/app.example.yaml`：**确认无需改动**（政策不复制进 app.yaml；见否-A）

**明确不触碰**：`openspec/specs/`、`config/ips.yaml`（本波不改政策）、`config/ips.local.yaml`（私人快照，只读）、`config/knowledge/`（K2 已落 5 条 canon，本波不写）、`src/service/backtest/`、`src/service/portfolio/`、`docs/mrd/`。

## Risks / Trade-offs（含回滚）

| # | 风险 | 触发 | 缓解 | 回滚 |
| --- | --- | --- | --- | --- |
| 1 | 取整 `.5` 方向未确认（Q1 / KU-…-rounding-01） | Owner 答复与 A2 不同 | 按 A2「.5 向上」写死 + 单测锁定 + 输出标「待确认」 | 改 `round_yuan()` 一处（`ROUND_HALF_UP`→`ROUND_HALF_DOWN`/`ROUND_HALF_EVEN`）+ 对应单测 |
| 2 | 固收迁移基数/次数未确认（Q2 / KU-…-migration-base-01） | 实际是「每月 30%」 | 按 A3「一次性、0.45×pool×0.30」写死 + 标待确认 | 改 `allocate_categories()` 迁移分支一处 |
| 3 | 现金门禁是否硬门禁未确认（Q3） | Owner 要求「<20% 暂停买入」 | 按 A5「只提示、不改数」 | 改 `cash_floor_hint`/状态机一处（把提示升级为金额置 0） |
| 4 | 顺延是否独立记账未确认（Q4） | Owner 要求结转 | 按 A4「不记账、自然重摊」 | 若结转 → 触账本，另立 change，不回滚本波 |
| 5 | 执行日遇休市/节假日（KQ-1 / KU-…-holiday-01） | 政策要求交易日顺延 | 按「仍按日历周四给指令」（指令非成交），不实现交易日顺延 | 改 `resolve_execution_month_day` 一处加交易日表 |
| 6 | 手工快照滞后 → 当周无法出指令 | `as_of` 超 7 天 | R7 硬门禁拒绝（exit 2），宁缺毋用旧数 | 人工刷新快照后重跑（无代码回滚） |
| 7 | 顺延导致后续单月金额放大 | 某月顺延 | 预期行为（A4：剩余月数递减重摊），非缺陷 | 无需回滚；如需平滑另立 change |
| 8 | 快照内部「占比 ≠ 市值/pool」不一致 | 上游手工填错 | 市值与占比各自独立读取、不作交叉校验（避免误拒合法快照）；同 `as_of` 由 R7 统一门禁 | 若 Owner 要求交叉校验 → 另立 change |
| 9 | 依赖漂移 | 有人新增第三方库 | 只用 stdlib（`decimal`/`calendar`/`argparse`）+ PyYAML（已装），不新增依赖 | 无 |

## 参考

> 本波 T2 inScope 只有 `design.md` + `tasks.md` 两个文件，故参考内联在本节（与 T1 proposal 同口径，不另建 `reference/tech/REFERENCES.md`）。关键决策处标 `[n]`。

| 序号 | 参考 | 支撑哪个决策 |
| --- | --- | --- |
| [1] | Python `decimal` — `ROUND_HALF_UP` 货币取整 <https://docs.python.org/3/library/decimal.html> | 金额公式与取整（`round_yuan`） |
| [2] | Python `calendar` / `date` — 求「某月最后一个周四」<https://docs.python.org/3/library/calendar.html> | R2 执行日推导 |
| [3] | Python `argparse` — 子命令与程序退出码 <https://docs.python.org/3/library/argparse.html> | CLI 契约（`ips plan` 子命令） |
| [4] | 仓库内回测 CLI 先例 — `src/apps/cli.py:2023-2045`（退出码 0/1/2）+ `src/common/exceptions.py:41-42`（缺键拒绝） | 退出码语义、异常模型 |
| [5] | proposal「外部参考」[1]–[5]（Bogleheads IPS / threshold rebalance / Vanguard DCA vs lump-sum） | 「固定日不择时」「再平衡只提示不调仓」 |

## Migration Plan

无数据迁移：执行器**只读** `config/ips.yaml` 与 `config/ips.local.yaml`，不写任何持久化状态、不新增表/目录。上线 = 合并 `feature/add-allocation-executor` 后跑一次 `python -m apps.cli ips plan --as-of <当日>` 与手算对照。既有能力零改动（`backtest` / `portfolio` / `report` 互不影响）。

## Open Questions

全部未答复口径按 proposal A2–A5 + KQ-1 假设执行，输出中显式标「待确认」；条目已在 `config/knowledge/known_unknowns.yaml` 登记（K2 已落），答复到达后由后续波次回填，本波不定稿：

| ID | 问题 | 假设执行 | KU id |
| --- | --- | --- | --- |
| Q1 | 取整 `.5` 进位方向 | 四舍五入、.5 向上（`ROUND_HALF_UP`） | `KU-2026-11-alloc-rounding-01` |
| Q2 | 固收迁移基数与次数 | 一次性、目标固收额度（0.45）的 30% | `KU-2026-11-alloc-migration-base-01` |
| Q3 | 现金 <20% 是否硬门禁 | 只提示、不改数 | `KU-2026-11-alloc-cash-gate-01` |
| Q4 | 顺延是否独立记账 | 不记账、自然重摊 | `KU-2026-11-alloc-carryover-01` |
| Q5 | 宽基 ETF 标的池 | 只给类别、不选代码 | `KU-2026-11-alloc-etf-pool-01` |
| KQ-1 | 执行日遇休市/节假日 | 仍按日历周四给指令 | `KU-2026-11-alloc-holiday-01` |
