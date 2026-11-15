# 配置执行器知识缺口识别（K1）

> change：`add-allocation-executor`　分支：`feature/add-allocation-executor`　角色：knowledge-architect（K1）
> 写作基线 HEAD：`a65e0808aa6f5d66e948d47e28fddec786aae12b`（T1 提交，见 §7 自检）
> 分层规则真源：[`config/knowledge/_design.md`](../../../config/knowledge/_design.md)（本文件只做「识别 + 判断 + 归属」，不含知识条目内容，不写 `config/knowledge/`）

## 0. 本文件是什么 / 不是什么

**是**：把配置执行器（R1–R10）依赖的 7 类口径逐条判「是否已在 `config/knowledge/canon/`」「已有 vs 新」、给证据（文件:行 / canon id）与归属层；给「本波是否需要新增 canon」的明确结论；把必须由人定的口径整理成表单式清单报 captain。

**不是**：① 不是 `config/knowledge/<layer>/*.yaml` 的知识条目（K2 的活，本波 0 条由我落库）；② 不是 spec（不改 `openspec/specs/`、不改 T1 的 `proposal.md` / `spec.md`）；③ 不做任何口径裁定：**本文件不填任何未确认数值**，表中出现的数字一律是既有材料原文引文，不是我新定的值。

### 0.1 信源与优先级（本波实际用到的材料，按角色文件 1>2>3>4>5）

| 序 | 信源 | 本波用到的具体材料 | 可标置信度 |
| --- | --- | --- | --- |
| 1 | 人工答复（经 captain 转存进仓库） | Owner 2026-11-15 四条书面答复 + 飞书《投资Agent》v2 §三/§四/§五 裁决（[`annotations.md`](../../../docs/cases/case-20261115-allocation-executor/annotations.md):11-26） | `确定` |
| 2 | 仓库一手材料 | [`config/ips.yaml`](../../../config/ips.yaml)（政策）、[`config/ips.local.yaml`](../../../config/ips.local.yaml)（私人快照，只引行号不引金额）、[`docs/design/portfolio-plan-v0.1.md`](../../../docs/design/portfolio-plan-v0.1.md)（**草案**，:4 自述待确认）、T1 的 [proposal.md](proposal.md) / [spec.md](specs/allocation-executor/spec.md) | `确定`（文件:行 + 引文） |
| 3 | 现有 `src/` 与 `test/` | 本波 **0 次**使用：执行器尚未实现（T3 才落代码），无「现在是什么」可判 | — |
| 4 | `ref/` 只读快照 | 本波 **0 次**使用 | — |
| 5 | `web_search` / `web_fetch` | 本波 **0 次**使用 | — |

**锚点缺口声明**：`docs/mrd/mrd-v1.md` 仍是骨架（[`docs/mrd/mrd-v1.md:11`](../../../docs/mrd/mrd-v1.md) 为占位符），**本文件不引用任何 MRD 编号**，与 T1 [proposal.md:124](proposal.md) 同口径。

### 0.2 「已有 vs 新」四值口径（本文件专用，避免各自解读）

| 代号 | 含义 | 对 K2 / T2 的意义 |
| --- | --- | --- |
| `A 已有·权威已固化` | 口径已由 canon 条目或 spec 写死，可直接引用 | canon 内的补引用即可；spec 内的不动知识层 |
| `B 已有·未入 canon` | 口径本体已有权威来源且明确，但 `config/knowledge/canon/` 无对应条目 | **不是新知识缺口**；缺的是条目，K2 按 schema 落库 |
| `C 待确认` | 口径本体缺失（无 Owner 答复、材料未定义），只能问人 | 不得标 `确定`；进 `hypotheses` 或 `known_unknowns`，答复后回填 |
| `D 无权威来源` | 连问谁都不清楚，或只有外部资料 | 不入库，K2 记 `known_unknowns.yaml` |

### 0.3 归属层代号（层语义与准入见 `_design.md` §1）

`CAN` = `canon/`（可写成 key 的口径/阈值/枚举，硬规则）｜`RUL` = `rules/`（算法/流程）｜`FAC` = `facts/`（现在是什么，可 grep）｜`HYP` = `hypotheses/`（未确认，`confidence=假设`）｜`CAS` = `cases/`（裁决/判例）。
另：**固有逻辑**不是知识层——按 `_design.md` §0.0 Q2 与 §4.1，归「代码 + 单测」，知识库只留指针、不条目化。

---

## 1. 识别总表（7 类口径 → 11 条知识条目）

> 列「支撑 case 哪一环」对应 [`annotations.md`](../../../docs/cases/case-20261115-allocation-executor/annotations.md) §5 的 5 条可证伪判据与 §3 的 Owner 答复。

| ID | 知识条目（口径；新数值不写） | 支撑 case 哪一环 / Requirement | 性质 | 已有 vs 新 | 证据（信源 + 引文） | 归属层 | 本波动作 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| KD-1-01 | 目标配置三桶（权益 / 固收 / 现金的目标占比）与权益容许带 | §5-1「金额与 ips 一致」；R3/R5/R6/R8/R9 | 口径（政策） | `B 已有·未入 canon` | `config/ips.yaml:25-30`「allocation.target: equity 0.35 / fixed_income 0.45 / cash 0.20；equity_band [0.30, 0.40]」；Owner #1（[annotations.md:23](../../../docs/cases/case-20261115-allocation-executor/annotations.md)）「沿用 ips 现值：权益 35%、期限 24 个月」；`docs/design/portfolio-plan-v0.1.md:35`、`:72-76` | `CAN` | **建议新增 canon** |
| KD-1-02 | 权益超限顺延：权益占比高于 `skip_if_equity_above` 时当月买入置 0 并给理由；不独立记账，由剩余月数重摊 | §5-2「>35% 顺延且不给金额」；R6 | 口径（阈值） | `B 已有·未入 canon` | `config/ips.yaml:51`「skip_if_equity_above: 0.35」；`docs/design/portfolio-plan-v0.1.md:90`「若当月权益因上涨已超 35%，跳过当月买入并记一条『顺延』，不追高」；[annotations.md:37](../../../docs/cases/case-20261115-allocation-executor/annotations.md)；proposal:142（A4） | `CAN` | **并入 KD-1-01 条目**（与目标权益同值，不单列 id，避免同值两处） |
| KD-1-03 | 40% 权益上限 / 单票 5% / 行业 25% 未经回测验证 → 只能提示，不得当硬门禁 | §5-2、§5-4 的边界；R6/R10 | 判例（裁决） | `B 已有·未入 canon` | [annotations.md:16](../../../docs/cases/case-20261115-allocation-executor/annotations.md)「40/5/25 三条上限『未经回测验证且已在文档评注中被否决，已从验收标准移除，改由回测结果决定参数』→ 本波只能作提示」；proposal:70；spec R6:118-120 | `CAS` | 不新增（K2 本波 inScope 不含 `cases/`；证据已在 case 文档且 spec 已写死行为） |
| KD-2-01 | 执行日 = 每月最后一个周四；固定日、不择时 | §5-1；R2（执行月派生 R3/R5/R6） | 口径（枚举） | `B 已有·未入 canon` | Owner #2（[annotations.md:24](../../../docs/cases/case-20261115-allocation-executor/annotations.md)）「每月最后一个周四」；`config/ips.yaml:50`「execution_day: last_thursday」 | `CAN` | **建议新增 canon** |
| KD-3-01 | 再平衡带：任一桶偏离目标 > 5pp 时只提示，不自动调仓 | §5-4；R8 | 口径（阈值） | `B 已有·未入 canon` | `config/ips.yaml:61`「R4_rebalance_band: 0.05」；`docs/design/portfolio-plan-v0.1.md:110`「任一桶偏离目标 > 5pp → 季度调整回目标带」 | `CAN` | **建议新增 canon** |
| KD-4-01 | 快照时效：`as_of` 距计算日 > 7 天拒绝；恰好 7 天允许；缺 `as_of` 拒绝 | §5-3；R7 | 口径（阈值） | `B 已有·未入 canon` | Owner #4（[annotations.md:26](../../../docs/cases/case-20261115-allocation-executor/annotations.md)）「快照 as_of 超 R8_stale_days=7 天 → 拒绝给指令」；`config/ips.yaml:67`「R8_stale_days: 7」；`docs/design/portfolio-plan-v0.1.md:114` | `CAN` | **建议新增 canon** |
| KD-5-01 | 固收迁移试水比例 = 目标固收额度的 30%（基数与次数待确认，见 §5-Q2） | Owner #3「买什么类别」；R5 | 口径（比例） | `B 已有·未入 canon`（比例）+ `C 待确认`（基数与次数） | Owner #3（[annotations.md:25](../../../docs/cases/case-20261115-allocation-executor/annotations.md)）「固收端先按 30% 试水迁移」；`config/ips.yaml:41`「trial_ratio: 0.30」；proposal:141（A3）/ :151（Q2） | `CAN`（仅比例）+ `HYP`（基数/次数） | **建议新增 canon（仅比例）**；基数/次数走 §5-Q2 |
| KD-5-02 | 现金低于 20% 时是「只提示」还是「暂停权益买入」 | §5-4「提示不越界」；R9 | 口径 | `C 待确认` | `docs/design/portfolio-plan-v0.1.md:113`「现金/货基 < 20% → 优先补充现金桶，暂停权益买入」 vs spec R9:176 + proposal:143（A5）「只提示、不改数」；`annotations.md:16` 的撤销名单未点名 R7 | `HYP` | 不入 canon；问人（§5-Q3） |
| KD-6-01 | 金额取整：到元；`.5` 进位方向 | §5-1「可复算到元」；R4 | 计算约定 | `C 待确认`（方向）；取整到元本身已在 spec | proposal:140（A2）、:150（Q1）；`config/ips.local.yaml:37`「monthly_amount: 90307 ← 缺口 ÷ 24」只证明整除到元，未证明 `.5` 方向 | 固有逻辑（答复后落代码 + 单测） | 不入 canon；问人（§5-Q1） |
| KD-7-01 | 执行日恰逢休市 / 节假日（非交易日）的处置 | §5-1；R2 | 口径 | `C 待确认`（本波新识别） | Owner #2 只给日期（`annotations.md:24`）；`config/ips.yaml:50` 无节假日规则；`docs/design/portfolio-plan-v0.1.md:89` 措辞为「建议月末最后一个工作日前的周四」 | `HYP` | 不入 canon；问人（§5-KQ-1） |
| KD-8-01 | 边界事实：快照有两个日期字段（`updated_at` 与 `holdings.as_of`），R7 时效以 spec 指定的 `holdings.as_of` 判定 | R7 / R1 | 数据语义 | `A 已有·权威已固化`（spec 已定，非 canon） | spec R1:13 输入列 `holdings.as_of`；R7:139-141；`config/ips.local.yaml:8` `updated_at: "2026-11-14"` vs `:24` `as_of: "2026-11-13"`（相差 1 天） | 固有逻辑（spec 已指定） | 不入 canon；提示 T2/T3 按 spec 取 `holdings.as_of` |

---

## 2. 判断要点（每条判断的可复核依据）

### 2.1 「0 项已在 canon」不是印象，是检索结果

- `config/knowledge/canon/` 现有 8 个文件、**25 条 canon**（+ `hypotheses/grouping.yaml` 1 条 = 知识库 26 条），全部属回测域：`CAN-IPS-001`、`CAN-CAL-*`、`CAN-COST-*`、`CAN-GATE-*`、`CAN-GROUP-*`、`CAN-MATCH-*`、`CAN-SAMPLE-*`、`CAN-STATS-*`。
- 对执行器 7 类口径的关键词（`allocation` / `equity_band` / `skip_if_equity_above` / `last_thursday` / `trial_ratio` / `rebalance_band` / `stale_days` / `取整`）在**整个 `config/knowledge/`** 检索 0 命中（§7.1 的前两条 grep，退出码 1）。
- `CAN-IPS-001` 只覆盖**目标函数**：statement 为「名义目标收益 5%…最大回撤硬线 20%、禁止杠杆、禁止集中」，scope_note 明写「仅约束投资组合层面的风险预算」（`config/knowledge/canon/CAN-IPS-001.yaml:10-12`、`:21-22`）——**不覆盖目标配置三桶 / 执行日 / 顺延 / 再平衡带 / 快照时效 / 迁移比例 / 取整**。

### 2.2 6 项是「已有口径·未入 canon」，不是「新知识缺口」

目标三桶与容许带、执行日、权益超限顺延、再平衡带、快照时效、迁移试水比例：口径本体的权威来源都在（`config/ips.yaml` 的 tracked 政策段 + Owner 2026-11-15 四条答复，逐条证据见 §1），执行器按 spec R1 **只从该文件读取**、不硬编码。按 `_design.md` §0.0 四问，它们不是 Q1 一次性入参、不是 Q2 通用算法、而是 Q3「业务上什么算对且 Owner 不发版就能改」→ **属知识**；按 §1.3 判定流程（能写成配置 key）→ `CAN`。缺的只是 canon 条目，不是口径。

### 2.3 唯一「口径本体缺」的是取整 `.5` 方向（KD-6-01）

「取整到元」已由 spec R4 写死（R4 义务），但 `.5` 往哪边进位无 Owner 答复：proposal 明确列为 A2 假设 + Q1 开放问题（:140、:150），`ips.local.yaml:37` 的注释只证明现有金额是「缺口 ÷ 24 除得尽」，不能证明方向。按 `_design.md` §0.0 属 Q2 固有逻辑（所有金额走同一取整算法），答复后落**代码常量 + 单测**（`_design.md` §4.1），不进 canon；答复前只能标 `待确认`，不得按「四舍五入」当确定口径引用。

### 2.4 40/5/25「只能提示」是判例，不能写成 canon 硬规则

飞书 v2 §三 修订（`annotations.md:16`）已把三条上限移出验收标准、改由回测决定参数。若把它们写成 canon 硬规则（strength=硬规则），等于静默复活已撤销的门禁，与 spec R6 的「提示不改变顺延判定」直接冲突。故归 `CAS`（裁决类），不归 canon。

### 2.5 待确认项与 canon 的边界

现金门禁（KD-5-02）、迁移基数与次数（KD-5-01 的 C 部分）、顺延是否独立记账（proposal Q4）、ETF 标的池（Q5）都**不得**在 canon 里写死方向或数值：它们是业务口径空白，按 `_design.md` §1.2 进 `HYP`，或按 §1.4 进 `known_unknowns.yaml`（K2 唯一写者）。

---

## 3. 冲突登记（信源冲突逐条裁决，不静默取一边）

| # | 冲突 | 各侧证据 | 裁决（按信源优先级 1>2>3） | 对 T2/T3 的约束 |
| --- | --- | --- | --- | --- |
| 冲突1 | **执行日措辞**：Owner 口径「每月最后一个周四」 vs 设计草案「月末最后一个工作日前的周四」 | 侧 A（信源1+已入库政策）：`annotations.md:24`；`config/ips.yaml:50`。侧 B（信源2 草案）：`docs/design/portfolio-plan-v0.1.md:89` | 取「每月最后一个周四」。草案 :4 自述「待 Owner 确认」，措辞作废。**差异是实质的**：2026-12 最后一个工作日是 12-31（周四），草案字面会取 12-24，与 spec R2 Scenario（12-31）差一周 | T3 不得按「最后一个工作日**前**的周四」实现；T2 在设计里显式引用 Owner #2 |
| 冲突2 | **投放期限**：草案「12 个月定投」 vs Owner 答复与 tracked 政策「24 个月」 | 侧 A：`annotations.md:23`（Owner #1「期限 24 个月」）、`config/ips.yaml:48`「horizon_months: 24」、`ips.local.yaml:37`（月供按「缺口 ÷ 24」）。侧 B：`docs/design/portfolio-plan-v0.1.md:40`、`:88`、`:167` | 取 24 个月。草案的 12 个月是 2026-11-14 旧版本，已由 Owner 2026-11-15 答复覆盖 | T2/T3 的剩余月数推导按 24 个月与 `target_date`，不得引用草案 12 个月 |
| 冲突3 | **试水额度表述**：草案「20%–30% 的额度」 vs Owner「30%」 | 侧 A：`annotations.md:25`、`config/ips.yaml:41`「trial_ratio: 0.30」。侧 B：`docs/design/portfolio-plan-v0.1.md:80`、`:171`「20%–30%」 | 取 30%（Owner 明确选定）；区间下限 20% **不得**作为实现依据。此冲突已收敛，登记备查 | R5 只认 `migration.trial_ratio` |

---

## 4. 本波是否需要新增 canon —— 结论

**结论：需要新增 canon，建议 5 条**，由 K2 按 `_design.md` schema 落到 `config/knowledge/canon/allocation-executor.yaml`（文件名与 id 由 K2 定）：

| # | 建议条目（口径） | 来源（K2 落库时照抄） | 来自 |
| --- | --- | --- | --- |
| 1 | 目标配置三桶与权益容许带（含顺延阈值与目标权益同值） | 人工答复:Owner:2026-11-15:权益目标与投放期限（原话见 `annotations.md:23`） + `config/ips.yaml:25-30`、`:51` | KD-1-01（并入 KD-1-02） |
| 2 | 执行日 = 每月最后一个周四 | 人工答复:Owner:2026-11-15:执行日（原话见 `annotations.md:24`） + `config/ips.yaml:50` | KD-2-01 |
| 3 | 再平衡带 = 任一桶偏离 > 5pp 只提示、不调仓 | `config/ips.yaml:61` + `docs/design/portfolio-plan-v0.1.md:110` | KD-3-01 |
| 4 | 快照时效 = `as_of` 超 7 天拒绝、恰好 7 天允许、缺失拒绝 | 人工答复:Owner:2026-11-15:数据来源与时效（原话见 `annotations.md:26`） + `config/ips.yaml:67` | KD-4-01 |
| 5 | 固收迁移试水比例 = 目标固收额度的 30%（仅比例；基数/次数不入条目） | 人工答复:Owner:2026-11-15:买什么类别（原话见 `annotations.md:25`） + `config/ips.yaml:41` | KD-5-01 |

**不新增 canon 的条目及理由**：

- KD-1-03（40/5/25 只能提示）→ 归 `CAS`；本波 K2 inScope 不含 `cases/`，证据已固定在 `annotations.md:16` 与 spec R6，不阻塞实现。
- KD-6-01（取整 `.5` 方向）→ Q2 固有逻辑，答复后落代码 + 单测；若 Owner 要求「可随政策改」再升级为 canon/配置。
- KD-5-02（现金门禁）、KD-7-01（节假日）→ `HYP`；KD-5-01 的基数/次数与 Q4（顺延记账）→ `HYP`/`known_unknowns`。
- KD-8-01 → spec 已指定 `holdings.as_of`，属固有逻辑，不入知识层。

**为什么是「需要」而不是「不需要」**：① 6 项口径在 canon 目录里确实 0 命中（§2.1 检索证据），执行器在本波首次消费它们；② 按 `_design.md` §1.2 canon 准入：可写成 key（①）、有权威来源（②）、被 ≥2 条 Requirement 或实验消费（③，KD-1 被 R3/R5/R6/R8/R9 五条消费；其余各被 1–2 条消费，先例 `CAN-GATE-002` 仅 1 条 Requirement 亦已入 canon）；③ 后续波次（再平衡、持仓体检、阈值回测）会继续消费这些比例/阈值，不条目化就会散落在 config 注释与旧草案里；④ `CAN-IPS-001` 已确立「IPS 政策进 git、canon 做治理索引」的先例，本波同域新增与之对齐。

**护栏（防双写 / 防越界）**：条目 statement 只写「口径措辞 + `source` 指向 `config/ips.yaml` 行号」，**不复制 `config/ips.local.yaml` 的私人数值（金额、持仓、池总额）**；`config/ips.yaml` 仍是政策唯一生效载体，canon 条目不得成为第二配置源（`_design.md` §2.4、§4.2）。id / statement / schema 由 K2 落，本文件不写条目。

**被否方案**：

- **否-A「本波 0 新增 canon」**（理由：`config/ips.yaml` 已是权威载体、执行器只读 config、条目会双写）。否决理由：canon 的作用是跨波治理（来源 / owner / 复核 / 失效），不是运行时查表；0 新增会让 6 项口径在知识层不可见，且 40/5/25 的「只能提示」裁决无处归属。双写风险由上述护栏控制，且 `CAN-IPS-001` 已是同形态先例。
- **否-B「把 40/5/25 现值写成 canon 硬规则」**：否决——它们在 `annotations.md:16` 已被移出验收标准、只能提示；写成硬规则等于复活已撤销的门禁。
- **否-C「把取整方向写成 canon」**：否决——算法细节，按 `_design.md` §4.1「不可调不变量进代码」，写成知识会把实现细节伪装成业务标准。
- **触发再评估的条件**：Owner 在 §5 答复里改变任何比例 / 阈值 → 按 U1 更新条目（K2）；若后续波次出现「同一配置值在多个 change 各写一遍」，则条目增加 `registry_refs`/配置引用并设 `review_at`。

---

## 5. 需问人的口径清单（表单式，经 captain 转交 Owner）

> 纪律：T1 已在 proposal 提出 Q1–Q5（[proposal.md:148-154](proposal.md)），**本节不重复提问**，只列知识层需要的字段形态；KQ-1 是 K1 新增。问题只给业务口径，不含表名 / 字段名 / 模块名等实现假设；**本文件不填任何数值**。

| ID | 问题（业务口径） | 影响 Requirement | 知识层归属 | 未答复时处理 |
| --- | --- | --- | --- | --- |
| Q1（T1 已提） | 金额取整到元时，`.5` 进位方向按哪种约定？ | R4 | 固有逻辑（不进 canon） | 按 proposal A2 假设执行并标「待确认」 |
| Q2（T1 已提） | 固收 30% 试水的**基数**（以哪一档固收额度为基数）与**次数**（一次还是每月）？ | R5 | `HYP`（比例本身已确定，可入 canon；基数/次数不入） | 按 proposal A3 假设执行并标「待确认」 |
| Q3（T1 已提） | 现金低于 20% 时，是只提示由人决定，还是把权益买入置为暂停（硬门禁）？ | R9 | `HYP` | 按 proposal A5「只提示、不改数」并标「待确认」 |
| Q4（T1 已提） | 顺延的当月额度是否需要独立记账 / 结转（会触及账本）？ | R6 | `HYP`（或 KU） | 按 proposal A4「不独立记账、自然重摊」 |
| Q5（T1 已提） | 宽基 ETF 是否指定候选标的池？ | R5 | 不影响金额；本波只给类别 | 按 proposal「只给类别、不选代码」 |
| KQ-1（**K1 新增**） | 每月的执行日若恰逢休市日 / 法定节假日，是仍按该日给指令、顺延到之后第一个交易日、还是提前到前一交易日？ | R2（影响指令日期标注与人工执行时点；不影响金额公式） | `HYP` | 按「仍按该日历周四给出指令」执行（指令不是成交），并标「待确认」 |

**未解决登记方式**：captain 发出后 1 小时无答复 → 该条标「未解决」，由 K2 记入 `config/knowledge/known_unknowns.yaml`（`status: unresolved`），由 T7 记入 `docs/improvements/IMPROVEMENTS.md`。**本文件不写 `known_unknowns.yaml`（越界），只标「待确认」。**

---

## 6. 交接

| 对象 | 拿什么 |
| --- | --- |
| K2（knowledge-engineer） | §4 的 5 条建议 canon（来源行号已给）+ KD-5-02 / KD-6-01 / KD-7-01 的待确认归属；**不得自造数值、不得把 `ips.local.yaml` 私人数值写进条目** |
| T2（architect） | §3 冲突裁决（执行日=最后一个周四、期限=24 个月、试水=30%）；§2.2「条目只是索引，不改输入来源」；KD-8-01「时效取 `holdings.as_of`」 |
| T3（engineer） | 不得按草案「最后一个工作日前的周四」实现；40/5/25 只能提示（不得当门禁）；取整方向等 Q1；迁移基数/次数等 Q2 |
| T4 / T5（QA） | §1 表中「支撑 case 哪一环」列 → 每条判据可反向指到知识条目；负向用例来源：KD-4-01（时效）、KD-1-03（提示边界） |
| reviewer | §4 被否方案（防偷偷全量条目化 / 防把 40% 写成门禁）+ 护栏「canon 只写口径、不复制私人数值」 |

---

## 7. 自检记录（命令 + 退出码 + 输出）

### 7.1 检索与现状证据

```bash
$ git rev-parse HEAD
a65e0808aa6f5d66e948d47e28fddec786aae12b
$ git branch --show-current
feature/add-allocation-executor

$ grep -rniE "allocation|equity_band|skip_if_equity_above|last_thursday|trial_ratio|rebalance_band|stale_days|周四|取整" config/knowledge/canon/
（无输出）
exit=1          # ← canon 内没有执行器任何口径条目（§2.1 的「0 项已在 canon」由此成立）

$ grep -rniE "allocation|last_thursday|trial_ratio|rebalance_band|stale_days" config/knowledge/
（无输出）
exit=1          # ← 整个知识层也没有 allocation 域条目

$ grep -rn "id: CAN-" config/knowledge/canon/
config/knowledge/canon/calibration.yaml:8:  - id: CAN-CAL-001
config/knowledge/canon/calibration.yaml:25:  - id: CAN-CAL-002
config/knowledge/canon/CAN-IPS-001.yaml:8:id: CAN-IPS-001
config/knowledge/canon/cost.yaml:11:  - id: CAN-COST-001
config/knowledge/canon/cost.yaml:34:  - id: CAN-COST-002
config/knowledge/canon/cost.yaml:50:  - id: CAN-COST-003
config/knowledge/canon/cost.yaml:73:  - id: CAN-COST-004
config/knowledge/canon/cost.yaml:92:  - id: CAN-COST-005
config/knowledge/canon/cost.yaml:108:  - id: CAN-COST-006
config/knowledge/canon/gate.yaml:8:  - id: CAN-GATE-001
config/knowledge/canon/gate.yaml:25:  - id: CAN-GATE-002
config/knowledge/canon/gate.yaml:41:  - id: CAN-GATE-003
config/knowledge/canon/grouping.yaml:10:  - id: CAN-GROUP-001
config/knowledge/canon/grouping.yaml:30:  - id: CAN-GROUP-002
config/knowledge/canon/matching.yaml:8:  - id: CAN-MATCH-001
config/knowledge/canon/matching.yaml:22:  - id: CAN-MATCH-002
config/knowledge/canon/matching.yaml:38:  - id: CAN-MATCH-003
config/knowledge/canon/matching.yaml:52:  - id: CAN-MATCH-004
config/knowledge/canon/sample-split.yaml:8:  - id: CAN-SAMPLE-001
config/knowledge/canon/sample-split.yaml:30:  - id: CAN-SAMPLE-002
config/knowledge/canon/statistics.yaml:8:  - id: CAN-STATS-001
config/knowledge/canon/statistics.yaml:23:  - id: CAN-STATS-002
config/knowledge/canon/statistics.yaml:37:  - id: CAN-STATS-003
config/knowledge/canon/statistics.yaml:53:  - id: CAN-STATS-004
config/knowledge/canon/statistics.yaml:69:  - id: CAN-STATS-005
exit=0          # ← 25 条 canon，全部属回测域（CAL / IPS / COST / GATE / GROUP / MATCH / SAMPLE / STATS）

$ python scripts/check_knowledge_source.py
知识来源机检（root: config/knowledge）
================================================================
扫描 10 个文件，识别 26 个知识条目
  ⚠ config/knowledge/known_unknowns.yaml:<file>  不是知识条目容器（顶层 list / entries: / 带 confidence 的 dict），已跳过
----------------------------------------------------------------
结论: 0 error，1 warning —— 通过（无来源知识=0）。
exit=0          # ← 本文件没有写任何知识条目（config/knowledge/ 未被我改动）

$ openspec.cmd validate add-allocation-executor --strict
Change 'add-allocation-executor' is valid
exit=0          # ← 新增 knowledge-delta.md 未破坏 change 结构
```

### 7.2 覆盖自检（7 类口径 × 结论）

| 任务清单项 | 对应 KD | 已有 vs 新 | 是否需新增 canon |
| --- | --- | --- | --- |
| 目标三桶与容许带 | KD-1-01 | `B` | 是 |
| 执行日（每月最后一个周四） | KD-2-01 | `B` | 是 |
| 权益超限顺延 | KD-1-02 / KD-1-03 | `B` / `B` | 并入 KD-1-01 条目；裁决归 `CAS` |
| 再平衡带 | KD-3-01 | `B` | 是 |
| 快照时效 | KD-4-01 | `B` | 是 |
| 固收迁移试水比例 | KD-5-01 | `B`（比例）/ `C`（基数·次数） | 是（仅比例） |
| 金额取整规则 | KD-6-01 | `C` | 否（固有逻辑，待 Owner 答 Q1） |
| （本波新识别）执行日遇休市 | KD-7-01 | `C` | 否（问人 KQ-1） |
| （边界事实）时效日期字段 | KD-8-01 | `A`（spec 已定） | 否 |

- 每条判断均带「文件:行 + 引文」或 canon id，无「凭印象」条目；**0 项被误判为「已在 canon」**（检索退出码 1 为证）。
- 结论明确：**需要新增 5 条 canon**（§4），同时明确 4 类不新增及理由。
- 需问人的口径已列 §5（T1 的 Q1–Q5 + K1 新增 KQ-1），**未填任何数值**；未答复处置已写明。

### 7.3 结构自检（脚本 + 输出）

```bash
$ python - <<'PY'
import sys
p='openspec/changes/add-allocation-executor/knowledge-delta.md'
t=open(p,encoding='utf-8').read(); ok=True
def chk(n,c):
    global ok
    print(('PASS' if c else 'FAIL'),n); ok=ok and c
rows=[l for l in t.splitlines() if l.startswith('| KD-')]
chk('kd-row-count>=10', len(rows)>=10)
for kw,name in [('目标配置三桶','item1'),('最后一个周四','item2'),('顺延','item3'),('再平衡带','item4'),('快照时效','item5'),('试水比例','item6'),('取整','item7')]:
    chk('coverage-'+name, kw in t)
for i,l in enumerate(rows,1):
    chk(f'row{i}-has-evidence', ('config/ips.yaml' in l or 'annotations.md' in l or 'spec' in l))
    chk(f'row{i}-has-layer', ('`CAN`' in l or '`CAS`' in l or '`HYP`' in l or '固有逻辑' in l))
    chk(f'row{i}-has-bvsn', ('`A ' in l or '`B ' in l or '`C ' in l))
chk('verdict-explicit', '结论：需要新增 canon' in t)
chk('no-filled-new-value', '待确认' in t and 'Q1' in t)
chk('conflicts-registered', t.count('冲突1')>=1 and t.count('冲突2')>=1 and t.count('冲突3')>=1)
chk('questions-form', 'KQ-1' in t and 'Q5' in t)
print('SUMMARY kd_rows=%d' % len(rows))
sys.exit(0 if ok else 1)
PY
PASS kd-row-count>=10
PASS coverage-item1
PASS coverage-item2
PASS coverage-item3
PASS coverage-item4
PASS coverage-item5
PASS coverage-item6
PASS coverage-item7
PASS row1-has-evidence
PASS row1-has-layer
PASS row1-has-bvsn
PASS row2-has-evidence
PASS row2-has-layer
PASS row2-has-bvsn
PASS row3-has-evidence
PASS row3-has-layer
PASS row3-has-bvsn
PASS row4-has-evidence
PASS row4-has-layer
PASS row4-has-bvsn
PASS row5-has-evidence
PASS row5-has-layer
PASS row5-has-bvsn
PASS row6-has-evidence
PASS row6-has-layer
PASS row6-has-bvsn
PASS row7-has-evidence
PASS row7-has-layer
PASS row7-has-bvsn
PASS row8-has-evidence
PASS row8-has-layer
PASS row8-has-bvsn
PASS row9-has-evidence
PASS row9-has-layer
PASS row9-has-bvsn
PASS row10-has-evidence
PASS row10-has-layer
PASS row10-has-bvsn
PASS row11-has-evidence
PASS row11-has-layer
PASS row11-has-bvsn
PASS verdict-explicit
PASS no-filled-new-value
PASS conflicts-registered
PASS questions-form
SUMMARY kd_rows=11
exit=0
```

