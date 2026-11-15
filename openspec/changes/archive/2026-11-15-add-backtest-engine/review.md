# Review: add-backtest-engine（R1 设计产物评审）

> 评审者：reviewer（T6/R1）　方法：`ponytail-review`（correct / safe / load / tested / fast / lean）+ 项目 Agent 专项（B1–B9）+ 越权（D1–D3）
> 评审对象（7 份，只读）：`proposal.md` / `specs/backtest-engine/spec.md` / `knowledge-delta.md` + `config/knowledge/_design.md` / `design.md`（822 行）/ `tasks.md` / `test-design.md`（894 行）/ `references/research.md` + `docs/design/references/backtest-engine-research.md`
> 基线：设计冻结 commit `4139f34`；其后角色配置提交 `ca54333`、`ab53d48`（KA 四问校准）、`b33e3c9`（HEAD）。本评审在 HEAD `b33e3c9` 上读产物（设计产物自 `4139f34` 未再变）。

## 0. 结论先行

| 项 | 结论 |
| --- | --- |
| **verdict** | **pass** |
| findings | **5 条**（1 medium + 4 low），无 blocker / high → 不触发 needs_revision |
| 契约闭环主链 | R(19) ↔ Scenario(56) ↔ design §4.2(19) ↔ tasks(20) ↔ TC(56) 双向可追，无断链 |
| 未解口径被填值 | 未发现（Q1–Q8 / KQ-1…KQ-7 在全部产物里仍是「待确认 / 缺键即拒绝」） |
| 越权 | 未发现（`openspec/specs/` 未被手改；本波无 `src/`/`test/` 生产代码） |

**给 T5/后续的一句话**：5 个 medium/low finding 都是「契约收口级」细节（导出字段来源、影响面文件清单、台账字段形态、知识四问迁移），不阻断 T3 开工；其中 R1-01（`LedgerExportRow.statement` 无数据源）建议在 T3 开工前由 architect 补一句契约，其余可进 T7。

---

## 1. 维度 1：与当前角色配置的一致性（逐项结论）

### 1.1 product-manager（新增 `requirements-analysis`）

**结论：达标，无 finding。** proposal 具备 `requirements-analysis` 要求的完整度：`## Why` 是问题陈述而非解法定制（「没有回测台子，一期所有规则都只是拍脑袋」，并给出三个可证伪数字）；`## What Changes` 明确「本波交台子、不交策略结论」（真实需求 vs 表面诉求的区分）；`## 假设/开放问题` 给出 A1–A5 约束与 Q1–Q8 澄清清单，且逐条标「影响哪条需求 / 为什么必须现在定」（约束与假设分离）。成功/失败标准可观测（5 条 + 8 条），scope 边界明确（out of scope 8 条）。未发现「The Solution Specification / Stakeholder Fiction / Constraint Blindness」反模式。

### 1.2 architect（新增 `architecting-solutions` / `system-architect`）

**结论：达标，无 finding。** design.md 覆盖 `architecting-solutions` 的「多方案对比」——§5 有 4 个被否方案（否-1 复用前复权 / 否-2 写死默认值 / 否-3 门禁塞进 registry / 否-4 signal 靠自觉），每个含「方案 / 理由 / 结论」；覆盖 `system-architect` 的文档骨架——Context / Goals-NonGoals / 模块落位与依赖方向 / Decisions（R→模块映射）/ 风险表（触发·缓解·回滚）/ Migration。A–H 八项逐项给决策或显式 N/A（A 零 LLM、B 单进程 pipeline、E 零 LLM→N/A），无留白。

### 1.3 reviewer（本次以 `ponytail-review` 为主方法）

**结论：本评审已按 6 条逐条走，见 §6 A1–A6；每个 finding 带具体 case。** 无 finding 遗漏。

### 1.4 knowledge-architect（按 `_design.md` §0.0「四问」校准）

- **facts 与 canon 是否混用：未混用。** `knowledge-delta.md` 把「现状事实」单列 FAC 层（KD-1-04 三源前复权、KD-2-03 无 ann_date、KD-4-07 无成交额），与「口径」CAN 层（KD-1-01 后复权、KD-2-01 公告日）分开，且 `_design.md` §1.2 明写「facts 永远不能被当作口径引用」。
- **`_design.md` 自身是否自洽：自洽。** §0.0 四问轴与 §1 五层轴并存且不混（§0.0 明写「五层只回答进库后按什么形态管，要不要进库由四问决定」），「待迁出清单」4 条显式登记下一波 `recut-knowledge-axis` 处理。
- **`knowledge-delta.md` 是否满足四问：不完全（finding R1-05，low）。** delta 早于四问校准，固有逻辑类条目仍落在 CAN/RUL 层（见 §9 R1-05），但 `_design.md` §0.0 已显式登记为待迁出，属已知有归属的遗留，非本波阻断项。

### 1.5 qa（盲测纪律）

**结论：合规，无 finding。** `test-design.md` 开篇「盲测声明」明确只读 spec / proposal 成功失败标准 / design §4.1 契约 / 飞书 §三·§七·§九·§十，未读任何 `src/` 实现（本波亦无实现）；断言只锚 design §4.1 的签名与数据结构；测试用数值全部声明为「夹具输入、非生产默认」（§10.2 明写「示例值，非生产默认」）。未发现从实现派生的痕迹。

> 附：PM/architect 角色文件写「调研索引落 `reference/{product,tech}/REFERENCES.md`」，本 change 实际落 `docs/design/references/backtest-engine-research.md`（engineering-conventions §5 唯一真源要求的落位）+ change 内副本 `references/research.md`。按「engineering-conventions 为真源」判**非缺陷**，属角色文件与真源约定之间的既有张力，不列 finding。

---

## 2. 维度 2：契约闭环（双向可追）

机检证据（本评审实测，exit 码见 §7）：

| 环节 | 数量 | 双向可追 |
| --- | --- | --- |
| spec Requirement | 19（`^### Requirement:` = 19） | proposal R↔来源锚点表 19 行 ↔ spec 19 条 |
| spec Scenario | 56（`^#### Scenario` = 56） | test-design §1.2 56 个 TC ID，逐条 WHEN→THEN |
| design §4.2 映射 | 19 行（`^| R[0-9]` = 19） | R1–R19 全覆盖，每条有落地模块/接口 + 关键机制 |
| tasks | T2.1–T2.20（20 条） | 每条引用 design §4.1/§6.x 决策，无「完成整个模块」式条目 |
| test-design TC | 56 个 `TC-Rxx-yy`（sort -u = 56） | 每行带落位文件 `test/qa/backtest/test_*.py` |

**结论：主链无断链。** 唯一断链点在下游导出契约的字段来源（finding R1-01，见 §9）。

---

## 3. 维度 3：与仓库真源一致

- **分层与依赖方向**：design §4.0 的 `apps/cli → service/backtest → data_provider/backtest + dao → common` 符合 engineering-conventions §4.2 与 STRUCTURE.md 依赖方向；`data_provider/backtest` 只依赖 common、不反向依赖 service（§4.0 已明写）。
- **确定性边界（零 LLM）**：proposal `## What Changes` 与 design §A 均声明「零 LLM 调用点」，且引用 engineering-conventions §9.2（:310）「禁止 LLM 生成或修改数值」；无 LLM 数值环节。
- **`ref/` 纪律**：research.md 明写「不 COPY 任何代码 / AGPL-3.0 只借口径 / 禁止 import」，符合 engineering-conventions §5 与 STRUCTURE.md §关键约定 6。
- **`openspec/config.yaml` rules**：proposal（Why≥50 字、Capabilities、out of scope、成功标准）、spec（SHALL + `#### Scenario` WHEN/THEN、ADDED Requirements）、design（被否方案、影响面到文件、风险表含回滚）、tasks（具体文件路径 + 可执行 pytest 命令）均符合 rules 段。
- **结论：与真源一致，无 finding。**

---

## 4. 维度 4：未解口径是否被悄悄填值（blocker 检查）

**结论：未发现，无 finding。** 实测：

- design.md + tasks.md 中无 `alpha` / `block_length` / `n_bootstrap` / `shrink` / 佣金率 / 印花税率 / 滑点 bps 的具体默认值（grep 扫描 NONE）。
- design §9.1/§9.2 把 Q1–Q8 / KQ-1…KQ-7 全部落到「待开关 = 缺键即 `MissingBacktestConfigError` / `exit != 0`」，未拍板任何数值。
- test-design §10.2 的 `rate=2.5e-4/min=5/sell_rate=5e-4/滑点 1e-3` 明确标注「示例值，非生产默认」，且期望值由独立算式得出、禁止调用被测函数反推（§3 统一纪律第 2 条）。
- test-design 未硬编码 `alpha=0.05`（多处显式「alpha 来自夹具配置，不硬编码 0.05」）。
- 三段样本年份（2015–2020 / 2021–2023 / 2024–2026）、20/60 日窗口、T+1、100 股、组规模 ≥30/3 年/9–27、共线 0.7、MA60 等均来自飞书 r482 原文（`A 已有`，非「待确认」），不算填值。

---

## 5. 维度 5：可实施性（tasks.md 能否直接开工）

**结论：可开工，无 finding。** 每条 T2.x 具备：产出文件路径（`src/service/backtest/models.py` 等）、设计依据（design §4.1 具体 dataclass/签名）、验证命令（`python -m pytest -q test/...`）、判定真伪（具体输入→具体断言结果，如「一字涨停买不进→FAILED_LIMIT_SEAL→顺延」「缺 commission/stamp_tax→MissingBacktestConfigError」）。无「完成整个模块」式条目；Phase 顺序（契约→数据对齐→撮合→信号指标→台账→校准门禁→CLI）符合「先数据撮合、再指标台账、最后事件研究校准」的依赖序。tasks 尾部明示「本波只产出 design+tasks，不执行 T2.1–T2.20」，属预期状态。

---

## 6. CR 清单逐项结论（无留白）

### 通用 6 条（A1–A6，`ponytail-review` 维度）

| # | 维度 | 结论 |
| --- | --- | --- |
| A1 | correct | 未发现逻辑 bug；契约边界覆盖充分（K=None、空基准、越界、封板顺延、最大顺延上限）。导出契约字段来源有缺口 → finding R1-01（medium） |
| A2 | safe | 未发现。设计含三处硬拒绝（预注册缺失/配置缺键/数据缺口）+ 台账 append-only + 逐行哈希（篡改即 `RegistryCorruptedError`）；无弱随机/密钥/写序错误面 |
| A3 | load | 未发现。本波明确单进程批处理 pipeline（B 项），无 check-then-write 竞态、无每进程重复工作；台账 append-only + 最大顺延上限封死循环 |
| A4 | tested | 未发现。56 Scenario + 5 成功标准 + 8 失败标准 + 8 硬约束负向均有可执行断言；QA 用例非从实现抄（盲测声明 + 独立算式）。契约缺口已有断言兜底 |
| A5 | fast | 未发现。设计未引入热循环重复或大减速面；`ref/` 只借口径不 import |
| A6 | lean | 未发现过度设计。复用 `DataFetcherRouter`/`tech-analyzer` MA60 口径/`value-analyzer` 骨架，不重复造轮子；gates 从 registry 拆出是单一职责而非过度拆分。台账字段形态有轻微冗余（R1-03/R1-04，low） |

### Agent 特有 9 项（B1–B9）

| # | 维度 | 结论 |
| --- | --- | --- |
| B1 | LLM vs 确定性代码 | 未发现。design §A 逐环节「确定性」，零 LLM 调用点，与 proposal/engineering-conventions §9.2 一致 |
| B2 | 可信保证落地 | 未发现。§3D trace/明暗账/重入/拒绝全部落到契约（RunRecord 执行行 + ExperimentRecord 结果行 + 逐行哈希 + calibration.json 原子写），非仅声明 |
| B3 | 上下文管理 | N/A（零 LLM）。design §E 已为未来叙事层预留「只收结构化 JSON、不整表灌上下文」红线 |
| B4 | 成本 | N/A（零 LLM）。无 LLM 调用/token 浪费面 |
| B5 | 确定性 | 未发现。signal 纯函数（同输入同输出）、撮合/指标确定性；无 LLM 生成阈值/排序/口径 |
| B6 | 注入面 | 未发现。零 LLM；CLI 参数（`--config` 相对 cwd、缺键拒绝）与台账注入点（clock/data_version/results_dir）显式定义 |
| B7 | 可重入/可拒绝 | 未发现。可重入 = 预注册 commit + 参数快照 + 数据版本；可拒绝 = 三处硬拒绝 + 样本外二次/门禁跳级/改假设均落执行行留痕 |
| B8 | 知识/能力抽象（去重） | 未发现重复造轮子（复用 Router/tech/value 口径）。知识分类四问迁移未完成 → finding R1-05（low） |
| B9 | 知识 schema 一致性 | 未发现。`python scripts/check_knowledge_source.py` = exit 0（0 error；1 warning 为 `known_unknowns.yaml` 非条目容器，预期，本波 0 条目） |

---

## 7. 越权 / 范围检查（D1–D3，带命令与输出）

| # | 检查 | 命令 | 输出 / 结论 |
| --- | --- | --- | --- |
| D1 | `openspec/specs/` 未被手改 | `git diff --name-only main...feature/add-backtest-engine -- openspec/specs/` | 空 → 通过 |
| D2 | `test/` 与 `test/qa/` 分离 | `git diff --name-only main...feature/add-backtest-engine -- test/` | 仅 `test/qa/README.md`（QA 的 t6 产物）；无 engineer `test/` 文件 → 通过 |
| D3 | 评审只读产物 | 本评审未写任何被评审产物（`src/`/`test/`/`design.md`/`openspec/specs/`/`config/knowledge/`/`proposal.md`/`specs/`/`tasks.md`/`test-design.md`/`knowledge-delta.md`） | 通过（本评审只新增 `review.md`） |

补充证据（本评审实测）：

```bash
$ openspec.cmd validate add-backtest-engine --strict
Change 'add-backtest-engine' is valid        # exit=0
$ python scripts/check_knowledge_source.py
结论: 0 error，1 warning —— 通过（无来源知识=0）。   # exit=0
$ git rev-parse HEAD
b33e3c9a9acac3ae7d05271ed626dbaade26e6f9
$ git branch --show-current
feature/add-backtest-engine
```

---

## 8. verdict 的两项开放条件

1. **tasks.md 是否全完成**：本波（T2）只产 `design.md` + `tasks.md`，T2.1–T2.20 是 T3 实现波的施工图，**未执行**——`tasks.md:182` 明示「本波只产出 design.md + tasks.md，不执行上述 T2.1–T2.20」。属预期状态，非缺陷。
2. **声称行为是否在生产路径可达**：本波无实现，无法做运行时可达性验证；但契约层面（§4.1 签名/数据结构/异常清单）与 tasks 验收判据、test-design 断言三方一致，可达性留待 T3/T5 验证。R1-01（statement 来源）在 T3 开工前应补一句契约，否则 `export_ledger` 的 S2 字段会卡实现。

---

## 9. Findings（5 条，均 medium/low → verdict pass）

### R1-01（medium）`LedgerExportRow.statement` 无数据源，proposal S2「假设」导出链断裂

- **problem**：`design.md` §4.1 的结果行 `ExperimentRecord`（`design.md:358-374`）**没有** `statement` 字段；`export_ledger`（`design.md:531`）签名只有 `experiment_id / hypothesis_id`，**无预注册装载器**；而 `statement` 只存在于 git 跟踪的 `config/backtest/preregistrations/<hypothesis_id>.yaml`（`design.md:586`，`PreregistrationSpec.statement`）。case：T3 实现 `export_ledger` 时，无法从 append-only 台账 NDJSON 单独产出 `LedgerExportRow.statement`（`design.md:452`），而 `test-design.md` TC-SC-02 要求「读真实 YAML 逐字段一致」——签名与用例假设不一致，S2「任一实验一条命令导出假设/参数/…」会在实现处卡住。
- **requiredFix**：`design.md` §4.1 二选一并同步 tasks T2.15 判定——① `ExperimentRecord` 增 `statement: str`（`append` 落结果行时从预注册复制一份）；或 ② `export_ledger` 增 `prereg_dir: Path` 参数，按 `hypothesis_id` 读 YAML 填充 `statement`。验证：TC-SC-02 的 `statement` 与预注册 YAML 逐字段一致。
- **file:line**：`openspec/changes/add-backtest-engine/design.md:358-374`、`design.md:452`、`design.md:531`

### R1-02（low）design §6.7「影响面」QA 用例文件清单不完整（8 vs 19）

- **problem**：`design.md:715-724` §6.7 只列 8 个 QA 文件，而 `test-design.md:35-56` §1.1 实为 **19 个**（R1/R2/R3/R6/R9/R13/R14/R15/R16/R17/R19 的 QA 文件未在 design §6.7 列出）。case：engineer 只看 design §6.7 会漏建 11 个 QA 文件，违反 architect「影响面到文件路径清单」产出契约。
- **requiredFix**：`design.md` §6.7 补一句「完整 19 文件清单以 `test-design.md` §1.1 为准」，或列全 19 个文件。验证：`grep -c 'test/qa/backtest/' test-design.md` 与 design §6.7 清单一致。
- **file:line**：`openspec/changes/add-backtest-engine/design.md:715-724`；对照 `openspec/changes/add-backtest-engine/test-design.md:35-56`

### R1-03（low）`LedgerExportRow.segments`/`run_status` 与结果行的 join 规则未定义

- **problem**：`LedgerExportRow.segments: tuple[str, ...]`（`design.md:454`，复数）与 `ExperimentRecord.segment: Segment`（`design.md:364`，单数）形态不一致；`run_status`（`design.md:460`）来自执行行 `RunRecord`，但 `export_ledger` docstring 写「导出结果行」（`design.md:532`），而 REJECTED/FAILED 执行**无结果行**且 `RunRecord.experiment_id=None`。case：`ledger --hypothesis <id>` 对一个只有 REJECTED 记录（无结果行）的假设返回什么、`segments` 如何从单数 `segment` 派生，均未定义，TC-EXIT-02 只覆盖「未知 id → 1」。
- **requiredFix**：`design.md` §4.1 明确 `export_ledger` 的 join 规则（结果行 ↔ 最近执行行按 `experiment_id` 关联）与「REJECTED/FAILED 无结果行时的导出形态」（是只导结果行、还是也导执行行摘要）。验证：补一条 `ledger` 对无结果行假设的断言用例。
- **file:line**：`openspec/changes/add-backtest-engine/design.md:454`、`design.md:460`、`design.md:364`、`design.md:532`

### R1-04（low）`ExperimentRegistry.__init__` docstring「data_version 写入每行」与 `RunRecord` 无该字段矛盾

- **problem**：`design.md:519` 写「`data_version`：写入每行」，但 `RunRecord`（`design.md:347-355`）无 `data_version` 字段（仅 `ExperimentRecord:369` 有）。case：T3 按 docstring 实现会给 `RunRecord` 写 `data_version` 却无字段可落。
- **requiredFix**：`design.md:519` docstring 改为「data_version：写入结果行」；或给 `RunRecord` 补 `data_version: str | None`。验证：T2.15 判定与 test_registry 对齐。
- **file:line**：`openspec/changes/add-backtest-engine/design.md:519`、`design.md:347-355`

### R1-05（low）knowledge-delta 早于四问校准，固有逻辑仍落在 CAN/RUL 层

- **problem**：`knowledge-delta.md` 把固有逻辑类条目分到 CAN/RUL——KD-3-01（T+1）→CAN（`knowledge-delta.md:81`）、KD-3-02（封板顺延）→CAN（`:82`）、KD-3-03（停牌跳过）→CAN（`:83`）、KD-8-01（block bootstrap）→RUL（`:154`）、KD-8-08（部分池化）→RUL（`:161`）；而 `config/knowledge/_design.md:42-43` §0.0 明确「canon 不可调不变量（T+1、封板顺延、无未来函数）→ 固有逻辑」「rules 纯算法（block bootstrap、部分池化）→ 固有逻辑，知识库只留指针不条目化」。case：若 K2 按 delta 把 T+1 写成 CAN 条目，会与 §0.0「不条目化」冲突。**但** §0.0「待迁出清单」第 3 条（`_design.md:61-66`）已显式登记「下一波 `recut-knowledge-axis` 处理，不要在本波混改」，故为已知、有归属的遗留，非本波阻断项。
- **requiredFix**：下波 `recut-knowledge-axis` 时把 KD-3-01/02/03、KD-8-01/08 等固有逻辑条目从 CAN/RUL 迁出（只留一句业务理由 + 指向 specs 锚点），并回填 `knowledge-delta.md` §14 覆盖自检表。本波不改。
- **file:line**：`openspec/changes/add-backtest-engine/knowledge-delta.md:81-83`、`knowledge-delta.md:154`、`knowledge-delta.md:161`；`config/knowledge/_design.md:42-43`、`_design.md:61-66`

---

## 10. 分流核对

| finding | type | severity | verdict 影响 | 去向 |
| --- | --- | --- | --- | --- |
| R1-01 | bug（契约缺口） | medium | pass | T7 改进点（建议 T3 开工前 architect 补一句） |
| R1-02 | bug（影响面不完整） | low | pass | T7 改进点 |
| R1-03 | bug（join 规则未定义） | low | pass | T7 改进点 |
| R1-04 | bug（docstring 与字段不一致） | low | pass | T7 改进点 |
| R1-05 | knowledge-abstraction（四问迁移遗留） | low | pass | 下波 `recut-knowledge-axis`（已在 `_design.md` 待迁出清单） |

无 `blocker` / `high` → 按分流规则（`medium`/`low` 一律 `pass`），verdict = **pass**，findings 保留、不消失。
