# K3 知识盲验（case 回归）— add-allocation-executor

> 角色：qa（K3）｜任务：t7｜分支 `feature/add-allocation-executor`｜盲验日 2026-11-15
> 被验对象：K2 本波落库的 `config/knowledge/canon/allocation-executor.yaml`（5 条 canon）
> 与 `config/knowledge/known_unknowns.yaml` 新增的 6 条 KU（`KU-2026-11-alloc-*`）。
> 本文件只写 K3 结论；不改任何知识条目（`config/knowledge/` 只读）。

## 1. 结论

**有条件通过：5 条 canon 中 4 条「通过」、1 条「退回」；6 条 KU 全部「通过」（其中 1 条带 due 起算瑕疵）。**

| 对象 | 档位 | 一句话 |
| --- | --- | --- |
| CAN-ALLOC-001 三桶 / 容许带 / 顺延阈值 | **通过** | 三桶与带逐字回解 `config/ips.yaml:25-30`，顺延阈值回解 `:51`，Owner #1 原话回解 `annotations.md:23` |
| CAN-ALLOC-002 执行日 last_thursday | **通过** | Owner #2 原话 + `ips.yaml:50`；日历复算 2026-11=11-26、2026-12=12-31，草案字面=12-24，冲突①可复现 |
| CAN-ALLOC-003 再平衡带 5pp 只提示 | **通过** | `ips.yaml:61` + `portfolio-plan-v0.1.md:110` + `annotations.md:39` 三处同向 |
| CAN-ALLOC-004 快照 7 天时效 | **通过** | 核心回解 `annotations.md:26` + `ips.yaml:67`；边界三情形由 Owner 原话「超 7 天」严格推得且 spec R7 写死，条目已披露来源层级 |
| CAN-ALLOC-005 固收迁移试水 30% | **退回** | 「30%」可复现，但 statement 把**未确认的「基数=目标固收额度」**写成了确定口径，与本条自己的 `scope_note` 和 KU 自相矛盾（见 F1） |
| KU-2026-11-alloc-rounding-01 | **通过** | 全库无 `.5` 进位规则；Owner 答复表 4 行无取整项（缺口真实） |
| KU-2026-11-alloc-migration-base-01 | **通过** | `annotations.md:25` 只给比例；proposal A3 明标「假设」（基数/次数确未答复） |
| KU-2026-11-alloc-cash-gate-01 | **通过** | 无 Owner 答复；`portfolio-plan-v0.1.md:113`「暂停权益买入」与 `annotations.md:16`「未验证阈值只提示」冲突真实存在 |
| KU-2026-11-alloc-carryover-01 | **通过** | 无 Owner 答复；spec R6 已写死「顺延 MUST NOT 单独记账或累积待补额度」（本波假设） |
| KU-2026-11-alloc-etf-pool-01 | **通过** | `annotations.md:25` 明写「具体标的未指定」 |
| KU-2026-11-alloc-holiday-01 | **通过**（附 F4） | 一手材料确无节假日规则（`grep` 退出码 1）；但 `due=2026-11-15` 与「尚未转交 Owner」矛盾，1 小时时钟未起算 |

跨条发现 3 条（不改变单条内容正确性）：**F2** canon 准入③（≥2 条 Requirement 消费）4/5 条未达标且与文件头自述不一致；**F3** Owner 冲突裁决②（24 vs 草案 12 个月）在知识产物中无留痕；**F6** 001 `scope_note` 把「目标权益与顺延阈值必须同值」的推断写成「与 Owner #1 答复冲突」。

**退回清单（交 T7 收口）**：F1（high）、F2（medium）、F3（low）、F4（low）、F5（low）、F6（low）。F1 修正前，`CAN-ALLOC-005` 不得被下游当作「基数已确认」消费。

## 2. 盲验声明（读写边界）

**读**（全部只读）：
- case ground-truth：`docs/cases/case-20261115-allocation-executor/annotations.md`
- 仓库一手材料：`config/ips.yaml`（tracked 政策）、`docs/design/portfolio-plan-v0.1.md`（草案，`:4` 自述待确认）、`openspec/changes/add-allocation-executor/specs/allocation-executor/spec.md`、`openspec/changes/add-allocation-executor/proposal.md`（含 A1–A6 / Q1–Q5）
- 被验产物与容器规范：`config/knowledge/canon/allocation-executor.yaml`、`config/knowledge/canon/CAN-IPS-001.yaml`、`config/knowledge/known_unknowns.yaml`、`config/knowledge/_design.md`、`config/knowledge/README.md`（分派口径）、`scripts/check_knowledge_source.py`、`docs/agent-team/roles/_shared.md`、`docs/agent-team/roles/qa.md`、`docs/agent-team/roles/knowledge-engineer.md`
- 计算工具：本机 `python`（日历复算，只读标准库）

**不读 / 不作为证据**：
- **未打开** `openspec/changes/add-allocation-executor/knowledge-delta.md`（K1 的采集与推理过程）——本文件的每条判定只由第 2 节「读」清单中的一手材料复算得到。
- 未读 K2 的采集过程/提交说明与 `src/`、`test/`（K3 不需要，也不给 T4 盲测口径带来污染）；未读其他成员的实现。
- 为核对「Q1–Q5/KQ-1 是否真的经 captain 转交」，只读 `.agent-teams/add-allocation-executor/inbox/captain.jsonl` 与 `team.json` 的**消息摘要**（其中含 K1/K2 自述结论）。这些自述**只当作「待验主张」**（claim），不当作证据；每条主张均回到第 2 节一手材料独立复核。任务书随附的 K1/K2 结论摘要同样按 claim 处理。
- 未写：`config/knowledge/**`、`openspec/specs/**`、`src/**`、`test/**`、`docs/cases/**`。本文件是本任务唯一写入。

**盲验方法**（每条知识四步）：
1. **回解引文**：把 `source` 里的 `<路径>:<行号>｜引文` 回到真实文件，逐条确认行号存在、引文命中（见 §6.3）。
2. **回解 case**：把 statement 的每个数值/日期/边界放回 `annotations.md` 的 Owner 答复与仓库一手材料，看能否**不依赖条目本身**重现。
3. **反证边界**：对「高于 / 超过 / 恰好 / 缺失」类措辞，用独立算术或日历复算（§6.2），检查是否被扩大。
4. **治理复核**：按 `_design.md` §1.2 准入、§2 字段/来源格式、§3.4 双时钟检查条目自身；对 KU 按 `known_unknowns.yaml:12-23` 字段定义 + `knowledge-engineer.md` 超时口径检查。

**未覆盖（如实列）**：Owner 是否真的收到并答复了 Q1–Q5/KQ-1，仓库材料无法独立证明（只有 proposal 与 inbox 自述）；本波无 `docs/cases/<case>/traces.yaml` 文件，知识层 trace 行按 T5 阶段 9 统一 append（本任务契约仅授权写本文件，见 §7）。

---

## 3. 逐条盲验记录

### 3.1 CAN-ALLOC-001 目标三桶 / 权益容许带 / 顺延阈值 — **通过**

| statement 片段 | case/一手材料回解 | 结论 |
| --- | --- | --- |
| 权益 0.35、固收 0.45、现金 0.20（合计 1） | `config/ips.yaml:27-29`；Owner #1「沿用 ips 现值：权益 35%…」`annotations.md:23` | 复现 |
| 权益容许带 [0.30, 0.40] | `config/ips.yaml:30` `equity_band: [0.30, 0.40]` | 复现 |
| 权益占比 **高于** 0.35 → 当月买入顺延置 0 + 理由 | `config/ips.yaml:51` `skip_if_equity_above: 0.35  # 超配则顺延当月买入，不追高`；case 判据 2 `annotations.md:37`「不得仍然给出买入金额」 | 复现（「高于」与 `above` 严格同向，0.35 本身不顺延） |
| 不追高 | `ips.yaml:51` 注释原文 | 复现 |
| notes：40/5/25 只能作提示 | `annotations.md:16`「已从验收标准移除…本波只能作提示，不得当硬门禁」 | 复现 |

算术自检：0.35 + 0.45 + 0.20 = 1.00。`requirement_refs` 的 6 条消费（R1 回显目标 / R3 缺口 / R5 类别 / R6 顺延 / R8 偏离 / R9 现金）逐条在 spec 对应 Requirement 有落点。
唯一保留：F6（`scope_note` 的「与 Owner #1 答复冲突」是推断，非 Owner 原话）。

### 3.2 CAN-ALLOC-002 执行日 last_thursday — **通过**

- Owner #2 原话「**每月最后一个周四**（`execution_day: last_thursday`）」= `annotations.md:24`；政策载体 `config/ips.yaml:50`「`execution_day: last_thursday  # 固定日，不择时`」。两条独立来源同向。
- 「不择时 / 金额不因当日价格改变」：`ips.yaml:50` 注释 + 草案 `portfolio-plan-v0.1.md:89`「不择时、不看当日涨跌」。
- 冲突裁决①的实质差异可复算（§6.2）：2026-11 最后一个周四 = **11-26**（与 spec R2 Scenario `spec.md:36` 一致）；2026-12 = **12-31**；草案字面「月末最后一个工作日前的周四」= 12-24（因 2026-12-31 本身即周四、又是当月最后工作日）。条目 notes 的两个日期均正确。
- 草案地位核实：`portfolio-plan-v0.1.md:4` 自述「草案，待 Owner 确认」，故以 Owner 答复优先的裁决成立。
- 保留：F2（准入③只 1 条 Requirement 消费）。

### 3.3 CAN-ALLOC-003 再平衡带 5pp（只提示） — **通过**

- 带值：`config/ips.yaml:61` `R4_rebalance_band: 0.05  # 任一桶偏离目标 5pp`；触发语义「> 5pp」见 `portfolio-plan-v0.1.md:110`；「含恰好 5pp 不提示」是「大于」的严格读法，与 spec R8 `spec.md:160` 一致。
- 「只提示、不自动调仓、不改当月金额」：case 判据 4 `annotations.md:39`「任一桶偏离目标 > 5pp → 输出再平衡**提示**（不自动调仓）」——该句是 statement 后半句最直接的证据。
- 保留：F5（source 未引 `annotations.md:39`，只引了草案 `:110` 的「季度调整回目标带」，需读者自行推断「人工季度动作」语义）。

### 3.4 CAN-ALLOC-004 快照 7 天时效 — **通过**

- 核心：Owner #4 原话「快照 `as_of` 超 `R8_stale_days=7` 天 → 拒绝给指令」= `annotations.md:26`；阈值载体 `ips.yaml:67`。
- 三个边界（恰好 7 天允许 / `as_of` 缺失拒绝 / 晚于计算日拒绝）**不是新知识**：
  - 「超 7 天」按字面严格大于 → 恰好 7 天不在拒绝集内；
  - 缺 `as_of` 无法算天数差 → 无法判定「未过期」，只能拒绝（与 spec R3/R4「缺字段必须拒绝执行」同一纪律）；
  - 未来日期天数差为负 → 同样无法证明未过期。
  以上与 spec R7 `spec.md:139` 逐字一致；条目 notes 已如实披露「Owner 原话只给核心，边界由 spec R7 写死，本条照录」，**未冒充 Owner 答复**。
- 保留：F2（准入③只 R7 一条消费）。

### 3.5 CAN-ALLOC-005 固收迁移试水 30% — **退回**（F1）

可复现的部分：「30%」回解 Owner #3 原话「固收端先按 **30%** 试水迁移」（`annotations.md:25`）+ `ips.yaml:41` `trial_ratio: 0.30`；冲突③「草案 20%–30% 区间下限不成立」在 `portfolio-plan-v0.1.md:80`、`:171` 可复核，Owner 取 30% 覆盖区间。

**不可放行的部分**：statement 写「固收端迁移的试水比例**为目标固收额度的** 30%」（`config/knowledge/canon/allocation-executor.yaml:120`），把「基数 = 目标固收额度（0.45 × pool）」写成了确定口径；而：
- 同一条 `scope_note` 明确「**基数**（以哪一档固收额度为基数）与次数未确认…任何消费方都不得据本条自行推导迁移金额」（`:134-136`）——条目自相矛盾；
- 本波 KU 也把基数/次数登记为待答复（`known_unknowns.yaml:71-85`）；
- proposal A3 明标该基数为**假设**：「Owner 只答『先按 30% 试水迁移』，未说基数与次数；本波按『目标固收额度的一次性 30%』执行（Q2）」（`proposal.md:141`）。
结论：这是把本波假设升格为确定知识（K3 失败定义里的「把假设当确定」），必须退回 K2 改措辞后才能被下游引用。

### 3.6 KU 六条 — 逐条 **通过**

| KU | 缺口是否真实可复核 | 证据 |
| --- | --- | --- |
| `-rounding-01` | 是 | `annotations.md:23-26` 四条答复无取整项；`ips.yaml` 全文件无 `.5` 规则；proposal A2（`:140`）自述「只证明整除到元，未证明 .5 方向」 |
| `-migration-base-01` | 是 | `annotations.md:25` 只给比例；proposal A3（`:141`）标假设 |
| `-cash-gate-01` | 是 | 无 Owner 答复；`portfolio-plan-v0.1.md:113`「优先补充现金桶，暂停权益买入」 vs `annotations.md:16`「未验证阈值只提示」——KU 的 impact 描述与该冲突一致 |
| `-carryover-01` | 是 | 无 Owner 答复；spec R6 `spec.md:118`「顺延 MUST NOT 单独记账或累积待补额度，SHALL 通过剩余投放月数递减在后续月份重新均摊」是本波写死的假设（proposal A4 `:142`） |
| `-etf-pool-01` | 是 | `annotations.md:25`「具体标的未指定，不影响金额计算」 |
| `-holiday-01` | 是 | §6.5 的检索对「休市 / 节假日 / holiday / 交易日顺延」在 case、`ips.yaml`、草案、proposal 四处**全部 0 命中（grep 退出码 1）**；口径只有「每月最后一个周四」这个日历日 |

字段与状态自检（§6.4）：6 条均 `kind=unanswered`、`status=waiting`，9 个必填字段齐全，`asked_at=due=2026-11-15`，id 格式 `KU-2026-11-alloc-*-01` 且全局唯一；`remedy` 均写明「本波按假设执行、到期记 IMPROVEMENTS、不得升格确定口径」，与 `_shared.md:21`、`knowledge-engineer.md:53` 的超时口径一致。
唯一保留：F4（`-holiday-01` 的 due 起算与该问题「尚未转交 Owner」矛盾）。

---

## 4. 跨条发现（不由单条知识复现失败引起）

### F2 canon 准入③（≥2 条 Requirement / ≥2 个实验消费）未达标，且与文件头自述不一致 — medium

`_design.md:101` 规定 canon 准入三条全满足，第③条为「被 **≥2 条 Requirement** 或 **≥2 个实验**消费（静态引用门槛，防囤无人用的参数）」。实测：

| 条目 | `requirement_refs` | spec 关键词独立检索命中 | 是否满足③ |
| --- | --- | --- | --- |
| CAN-ALLOC-001 | R1,R3,R5,R6,R8,R9（6） | — | 满足 |
| CAN-ALLOC-002 | R2 | `last_thursday`/「最后一个周四」→ 仅 R2 | **不满足** |
| CAN-ALLOC-003 | R8 | `5pp`/`R4_rebalance_band` → 仅 R8 | **不满足** |
| CAN-ALLOC-004 | R7 | `R8_stale_days`/「7 天」→ 仅 R7 | **不满足** |
| CAN-ALLOC-005 | R5 | `trial_ratio` → 仅 R5 | **不满足** |

且该文件头自述准入含「被执行器的**多条** Requirement 消费」（`canon/allocation-executor.yaml:8`），与实际 4/5 条只有 1 条 refs 不符。**不影响数值正确性**，但按容器规范这 4 条要么补足真实消费方，要么按例外登记并报 K1 复核——否则「准入门槛」形同虚设，下一波会继续囤积单消费参数。

### F3 Owner 冲突裁决②（期限 24 vs 草案 12 个月）在知识产物中无留痕 — low

- Owner #1 答复含两块：「权益 **35%**、期限 **24 个月**」（`annotations.md:23`）；政策载体 `ips.yaml:48` `horizon_months: 24`。
- 草案多处写「12 个月」并称「**本次确认**」：`portfolio-plan-v0.1.md:40`「投放方式｜12 个月定投（本次确认）| Owner」、`:167`「已定（2026-11-14）…投放方式为 12 个月定投」、`:11/:20/:81/:88` 同。
- 知识产物的留痕情况：001 的 statement 不含期限（24 个月只出现在它的 `source` 引文里，`canon/allocation-executor.yaml:23`）；002 notes 只写了冲突①（执行日，`:65-67`），005 notes 写了冲突③（试水区间，`:138-139`），**冲突②没有任何条目或 KU 承载**。
- 影响与判档：`config/ips.yaml:48` 是唯一生效载体，因此不影响 T3 取值，判 low；但知识层「信源冲突怎么裁」的追溯链缺一环，后续读者若只看草案会以为 12 个月已定。

### F4 KU-holiday-01 的 `due` 与「尚未转交」自相矛盾 — low

`known_unknowns.yaml:155-157` 自述「尚未经 captain 转交 Owner；转交后按 knowledge-engineer.md:53 的 1 小时超时口径判未解决」，但该条 `due` 已写死 `2026-11-15`（`:145`），而 proposal 的开放问题表只有 Q1–Q5（`proposal.md:150-154`），不含休市问题（§6.5 检索亦证明 case/proposal 无此项）。按字面，这条**从未发出的问题今天即到期**，remedy（`:149-151`）会把「从未问过」记成「Owner 未答复 → 下波回采」，属治理噪声。同批另外 5 条 KU 的 Q1–Q5 有 proposal 表单支撑（`proposal.md:150-154`），不属此问题。

### F5 CAN-ALLOC-003 的 source 缺最强证据 `annotations.md:39` — low

statement 后半句「只据此输出再平衡提示、不自动调仓、不产出调仓金额、也不改变当月权益买入额」的最直接 case 证据是判据 4（`annotations.md:39`「输出再平衡**提示**（不自动调仓）」），但 source 只引 `ips.yaml:61` 与草案 `:110`（后者的动作词是「季度调整回目标带」，需读者自行推断为人工动作）。建议补引，避免下游把「提示」误读成「调仓」。

### F6 CAN-ALLOC-001 的 `scope_note` 把推断写成「与 Owner 答复冲突」 — low

`canon/allocation-executor.yaml:37-38` 称「改目标权益时须同时确认 `skip_if_equity_above`，两处不一致即与 Owner #1 答复冲突」。Owner #1 只答复「沿用 ips 现值：权益 35%、期限 24 个月」（`annotations.md:23`），**没有**就「目标权益与顺延阈值必须同值」表态；该联动要求是采集方的运维推断。当前 0.35/0.35 同值成立不影响使用，但措辞应降为「两处不一致须由 Owner 复核」，不称「与答复冲突」。

---

## 5. 退回清单（交 T7 收口 / K2 修正）

| # | severity | 对象 | 问题 | requiredFix |
| --- | --- | --- | --- | --- |
| F1 | **high** | `CAN-ALLOC-005` statement（`config/knowledge/canon/allocation-executor.yaml:120`） | 「为目标固收额度的 30%」把未确认的基数写成确定口径，与本条 `scope_note`（`:134-136`）和 `KU-2026-11-alloc-migration-base-01` 自相矛盾，等于把 proposal A3 的假设升格为知识 | 改为「固收端迁移的**试水比例**为 30%（`trial_ratio = 0.30`）；基数（以哪一档固收额度为基数）与次数未确认，见 `KU-2026-11-alloc-migration-base-01`，任何消费方不得据本条推导迁移金额」；`confidence` 仍可 `确定`（比例本身有 Owner 原话），但不得再把基数写进 statement |
| F2 | medium | `CAN-ALLOC-002/003/004/005` 的 `requirement_refs` + 文件头 `:8` | 4/5 条只有 1 条 Requirement 消费，未过 `_design.md:101` 准入③；文件头却自述「多条 Requirement 消费」 | 二选一并在 `notes` 留一句：① 若有真实第 2 消费方（如将来被 R1 回显 / R9 使用）就补 refs；② 若无，则记「准入③例外：仅 N 条消费，理由=…，已报 K1」并请 K1 复核 `_design §1.2③` 门槛（单消费的硬口径是否仍需入 canon） |
| F3 | low | 知识层整体 | Owner 冲突裁决②（24 个月 vs 草案 12 个月，草案 `:40` 自称「本次确认」）无任何条目 / KU 留痕 | 在 `CAN-ALLOC-001` 的 `notes` 加一句「期限以 `config/ips.yaml:48`（24 个月）为唯一载体；草案 `portfolio-plan-v0.1.md:40/:167` 的『12 个月已确认』已被 Owner 2026-11-15 答复覆盖」；或按 `_design.md` §1.1 交下波 `cases` 层登记 |
| F4 | low | `KU-2026-11-alloc-holiday-01.due`（`known_unknowns.yaml:145`） | 问题尚未转交 Owner，`due` 却已起算（1 小时时钟未开始），按字面今日到期会把「从未问过」记成「未答复」 | captain 转交 KQ-1 后，把 `due` 改为转交时刻 + 1 小时（或先置空并注明「待转交」，转交时补）；`note` 已写明未转交，保持 |
| F5 | low | `CAN-ALLOC-003.source`（`:75-76`） | 缺最直接的 case 证据判据 4 | 追加 `docs/cases/case-20261115-allocation-executor/annotations.md:39｜引文「…输出再平衡提示（不自动调仓）」` |
| F6 | low | `CAN-ALLOC-001.scope_note`（`:37-38`） | 把「目标权益与顺延阈值须同值」的推断写成「与 Owner #1 答复冲突」 | 改为「两处不一致须由 Owner 复核」；不新增数值 |

**放行边界**：F1 修正前，`CAN-ALLOC-005` 只可用于「30% 是试水比例」，不得据其推导迁移金额；F2–F6 不阻塞 T3 取值（数值本身均已独立复现）。

---

## 6. 复现证据（命令 + 退出码 + 输出）

环境：Windows 11，`python`（本机无 `python3`），`PYTHONIOENCODING=utf-8`；HEAD `a90a9fc8b916447b350efc838a450f9602d4a394`，分支 `feature/add-allocation-executor`，工作树干净（K3 写入前）。

### 6.1 机检：知识来源与字段

```text
$ python scripts/check_knowledge_source.py
知识来源机检（root: config/knowledge）
================================================================
扫描 11 个文件，识别 31 个知识条目
  ⚠ config/knowledge/known_unknowns.yaml:<file>  不是知识条目容器（顶层 list / entries: / 带 confidence 的 dict），已跳过
----------------------------------------------------------------
结论: 0 error，1 warning —— 通过（无来源知识=0）。
exit=0
```

### 6.2 日历复算（执行日与冲突裁决①）

```text
$ python - <<'PY'   # calendar.monthcalendar 取每月最后一个周四 + 关键日期 weekday
2026 11 last_thu 2026-11-26 Thursday
2026 12 last_thu 2026-12-31 Thursday
2027 1 last_thu 2027-01-28 Thursday
2028 11 last_thu 2028-11-30 Thursday
2026-12-31 weekday Thursday
2026-12-24 Thursday
exit=0
```

（12-31 既是当月最后一个周四、又是当月最后工作日；草案字面「最后一个工作日前的周四」因此落到 12-24，与条目 notes 的 12-31 vs 12-24 一致。）

### 6.3 引文回解（source 的 `<路径>:<行号>` 全部存在）

```text
$ python - <<'PY'  # 正则抽取 canon/allocation-executor.yaml 中所有 <path>:<line>，检查文件存在与行号在界内
OK  docs/cases/case-20261115-allocation-executor/annotations.md:19-26 (file lines=46)
OK  config/ips.yaml:25-30 (file lines=82)
OK  config/ips.yaml:51-51 (file lines=82)
OK  docs/cases/case-20261115-allocation-executor/annotations.md:16-16 (file lines=46)
OK  config/ips.yaml:50-50 (file lines=82)
OK  docs/design/portfolio-plan-v0.1.md:89-89 (file lines=175)
OK  config/ips.yaml:61-61 (file lines=82)
OK  docs/design/portfolio-plan-v0.1.md:110-110 (file lines=175)
OK  config/ips.yaml:67-67 (file lines=82)
OK  openspec/changes/add-allocation-executor/specs/allocation-executor/spec.md:139-139 (file lines=209)
OK  config/ips.yaml:41-41 (file lines=82)
OK  docs/design/portfolio-plan-v0.1.md:80-80 (file lines=175)
citations: 12 bad: []
exit=0
```

逐条引文命中（人工比对，脚本辅助）：`ips.yaml:51`「skip_if_equity_above: 0.35」、`:50`「execution_day: last_thursday」、`:61`「R4_rebalance_band: 0.05｜任一桶偏离目标 5pp」、`:67`「R8_stale_days: 7」、`:41`「trial_ratio: 0.30」、`portfolio-plan-v0.1.md:89`「月末最后一个工作日前的周四」、`:110`「任一桶偏离目标 > 5pp」、`:80/:171`「20%–30%」、`spec.md:139`「恰好为 7 天 SHALL 允许」、`annotations.md:23/24/25/26` 四条 Owner 原话、`:16`「40/5/25」、`:39`「不自动调仓」→ **全部 OK（16/16 检查项命中，0 MISS）**。

### 6.4 独立结构自检（条目字段 / 生命周期 / 双时钟 / KU 台账）

```text
$ python - <<'PY'  # 独立于 K2 自检：字段齐全、layer=canon、confidence=确定、无 registry_refs、
                   # id 格式、review_at−as_of=stale_after_days、id 唯一、KU 9 字段与状态
canon layer/domain: canon allocation entries: 5
  CAN-ALLOC-001: refs=['R1','R3','R5','R6','R8','R9'] as_of=2026-11-15 review_at=2027-11-15 stale=365
  CAN-ALLOC-002: refs=['R2'] as_of=2026-11-15 review_at=2027-11-15 stale=365
  CAN-ALLOC-003: refs=['R8'] as_of=2026-11-14 review_at=2027-11-14 stale=365
  CAN-ALLOC-004: refs=['R7'] as_of=2026-11-15 review_at=2027-11-15 stale=365
  CAN-ALLOC-005: refs=['R5'] as_of=2026-11-15 review_at=2027-11-15 stale=365
ids unique: True
KU total: 7
  KU-2026-11-alloc-rounding-01: kind=unanswered status=waiting due=2026-11-15 asked_at=2026-11-15 missing=[]
  …（其余 5 条同形，missing=[]）
KU ids unique: True
FAILS: none | exit 0
```

### 6.5 消费方计数（F2 证据）与节假日规则检索（KU-holiday 证据）

```text
$ python - <<'PY'  # 按 ### Requirement 切分 spec，检索关键词命中的 Requirement 集合
Requirements: ['R1','R2','R3','R4','R5','R6','R7','R8','R9','R10']
'last_thursday'   -> ['R2']
'5pp'             -> ['R8']
'R4_rebalance_band' -> ['R8']
'R8_stale_days'   -> ['R7']
'trial_ratio'     -> ['R5']
'skip_if_equity_above' -> ['R6']
'horizon_months'  -> ['R3']
exit=0

$ grep -rn "休市\|节假日\|holiday\|交易日顺延" \
    docs/cases/case-20261115-allocation-executor/annotations.md config/ips.yaml \
    docs/design/portfolio-plan-v0.1.md openspec/changes/add-allocation-executor/proposal.md
（无输出）
grep_exit=1
```

### 6.6 护栏复核（未复制私人数值）

```text
$ python - <<'PY'  # 去注释后扫描 canon 文件：4 位以上整数 / 私人派生字段
4+digit integers: ['2026', '20261115', '2027']      # 仅有年份与日期串
monthly_amount -> []   gap_to_target -> []   pool.total -> []
ips.local -> [11]      # 仅注释里的文件名（护栏说明），无任何数值
exit=0
```

### 6.7 基线

```text
$ git rev-parse HEAD
a90a9fc8b916447b350efc838a450f9602d4a394
$ git branch --show-current
feature/add-allocation-executor
$ git status --short        # K3 写入前
（空）
```

---

## 7. 未覆盖项与接力

1. **转交事实不可由仓库复核**：Q1–Q5「已按表单式经 captain 转交」只见于 `proposal.md:146` 与 K1/K2 的消息自述；Owner 答复表（`annotations.md:19-26`）只有 4 条、不含这 6 项。本文件按「问题确未获答复」判定（这一点有一手材料支持），但「是否真的发出」无法独立证明，交由 captain/T7 确认。
2. **KU-holiday-01 未在 proposal 表单中**（F4）：本波若要把「执行日遇休市」问出去，需 captain 另发；未发前不得按「Owner 未答复」记 IMPROVEMENTS。
3. **知识层 trace 未写**：`docs/cases/case-20261115-allocation-executor/traces.yaml` 当前不存在；按 `qa.md` 阶段 2 步骤 4 应 append `layer: knowledge` 行，但本任务契约限定只写本文件，故留 T5（阶段 9 统一 append）或 T7 收口处理，避免两处各写一份。
4. **未验实现**：本波 K3 不读 `src/`、`test/`；CAN-ALLOC-* 是否被代码按口径消费，由 T5 功能验证覆盖。
5. F1–F6 的修正状态需在 T7 收口时复核；F1 未修则 `CAN-ALLOC-005` 保持「不得推导迁移金额」的放行边界。
