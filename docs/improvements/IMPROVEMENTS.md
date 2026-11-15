# 改进点台账

> **只追加，不覆盖、不删除**。每波结束由 `T7` 写入，下一波开工前由 `T1` 读取。

> 历史条目永远保留，结论变了就追加一条新记录并注明"取代 IMP-xxx"。

## 字段定义

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| ID | 是 | `IMP-<change-name>-<两位序号>` |
| 来源证据 | 是 | 指向 `verification.md` 的条目编号，或 review finding id。禁止主观描述 |
| 影响面 | 是 | 涉及 capability / 文件 / 需求锚点 |
| 建议变更名 | 是 | kebab-case，可直接作为下一波 change 名 |
| 优先级 | 是 | `P0 阻塞` / `P1 下一波` / `P2 观察` |
| 分流结论 | 是 | `立即` / `观察` / `否决`（否决需写理由） |

## 晋升 MRD 的准入（三条全满足）

1. 有现存证据，能指到具体行；

2. 影响面能说清改哪条需求；

3. 能被切成一个独立 change。

不满足则留在台账里作为 `P2 观察`，不进 MRD。

## 台账

| ID | 来源证据 | 影响面 | 建议变更名 | 优先级 | 分流 | 记录时间 |
| --- | --- | --- | --- | --- | --- | --- |
| （暂无。条目由每波 T7 追加） | | | | | | |

### 波次：`add-backtest-engine`（T7 / 2026-11-15）

> 写入者：product-manager（T7）。上游输入：`openspec/changes/add-backtest-engine/verification.md` §11（终审 + §11.9 F10 + §11.10 未覆盖项 + §11.14 复验）、`review-implementation.md` §6（R2-01/R2-02/R2-03）、`review.md` §9（R1-01…R1-05）、`proposal.md` §假设/开放问题（Q1–Q8）、`knowledge-delta.md` §12（KQ-1…KQ-7）。
> 「分流结论」括号内即**晋升 MRD 准入三条**的自评：1 有现存证据能指到行 / 2 影响面能说清改哪条需求 / 3 能被切成独立 change。三条不全 → `P2 观察`。
> 建议变更名已用 `openspec.cmd list`（在飞 change）与 `openspec/changes/archive/`（54 个归档）核对，**无一重名**。
> 上方占位行「（暂无。条目由每波 T7 追加）」按 append-only 规则保留，本波条目自本小节起。

| ID | 来源证据 | 影响面 | 建议变更名 | 优先级 | 分流结论 | 记录时间 |
| --- | --- | --- | --- | --- | --- | --- |
| `IMP-add-backtest-engine-01` | `review-implementation.md` §6 **R2-02**（low）；HEAD 复核 `grep -n AdjustMode.HFQ src/service/backtest/*.py src/apps/cli.py` → `data.py:139`、`calibration.py:102`、`cli.py:1885`（另 `cli.py:1908/1933` 元数据） | capability `backtest-engine`；**R9**（「后复权**或**分段复权」双值契约只兑现一半）；文件 `service/backtest/data.py`、`service/backtest/calibration.py`、`apps/cli.py`、`service/backtest/models.py:46`（`SEGMENTED_HFQ` 定义存在但信号/校准路径不可达） | `make-adjust-mode-configurable` | P1 下一波 | 立即（准入 1/2/3 全满足：把 `adjust_mode` 提升为 `BacktestConfig` 键 + 三处读配置 + 用例即可独立成 change） | 2026-11-15 |
| `IMP-add-backtest-engine-02` | `review-implementation.md` §6 **R2-03**（low）；HEAD 复核 `grep -c sha256 src/service/backtest/gates.py` = **0** vs `registry.py` = **5**；`gates.py:233-247` `_append` 直写 `gates.ndjson`（无逐行 hash） | capability `backtest-engine`；**R19**（跳级/回退/同态拒绝「MUST 被拒绝并留痕」只覆盖拒绝侧；`accepted=True` 的迁移行可被离线改写而不被检出）；文件 `service/backtest/gates.py:63,233-247` | `harden-gate-state-tamper-evidence` | P1 下一波 | 立即（准入 1/2/3 全满足：迁移行走 registry 的带 hash append，或给 `gates.ndjson` 补同款逐行校验） | 2026-11-15 |
| `IMP-add-backtest-engine-03` | `review.md` §9 **R1-02**（low）：`design.md:715-724` §6.7 列 **8** 个 QA 文件，而 `test-design.md:35-56` §1.1 实为 **19** 个 | 文档一致性（**不改变任何 requirement**）；`design.md` §6.7、`test-design.md` §1.1 | `align-backtest-doc-inventories` | P2 观察 | 观察（准入 1 满足、**2 不满足**：影响面不落到任何需求锚点；可在归档后 docs 合并阶段顺手对齐，不单独立波） | 2026-11-15 |
| `IMP-add-backtest-engine-04` | `review.md` §9 **R1-05**（low）：`knowledge-delta.md:81-83`（KD-3-01 T+1 / KD-3-02 封板顺延 / KD-3-03 停牌跳过 → CAN）、`:154`（KD-8-01 block bootstrap）、`:161`（KD-8-08 部分池化）→ RUL；对照 `config/knowledge/_design.md:42-43` 与 `:61-66`「待迁出清单」 | 知识分层 `config/knowledge/`（CAN/RUL 层语义）；知识侧支撑 **R8 / R6 / R16** 的条目归属 | `recut-knowledge-axis` | P1 下一波 | 立即（准入 1/2/3 全满足；名字沿用 knowledge-architect 在 `config/knowledge/_design.md` §0.0 已登记的待迁出条目，不二次命名，且已在清单里挂了归属） | 2026-11-15 |
| `IMP-add-backtest-engine-05` | `verification.md` §11.9 + §11.11 **F10**（low）：`test/e2e/test_tushare_pipeline.py::test_tushare_pipeline_e2e`、`test/e2e/test_value_data_pipeline.py::test_value_data_pipeline_e2e` 因 `sqlite3.OperationalError: no such column: stock_snapshots.industry` 红；反证 `git diff --stat ba609a0..HEAD -- src/dao` **空** | 测试门禁口径（`python -m pytest -q test --ignore=test/qa` 不加 `-m` 时 exit 1）；本地 `data/stock_copilot.db` 种子库 schema 漂移 | `rebuild-e2e-sqlite-seed` | P1 下一波 | 立即（准入 1/2/3 全满足：环境种子库重建 + 两条 e2e 复跑转绿即可闭环，不涉需求） | 2026-11-15 |
| `IMP-add-backtest-engine-06` | `verification.md` §11.8：`python -m ruff check .` → `Found 38 errors`（exit 1；分布 `scripts/` 5、`src/` 13、`test/` 10，**均非本 change 产物**）；本 change 路径 `All checks passed!`（新增 0） | 全仓静态检查基线（**不影响任何 requirement**）；存量 38 处 style 债 | `housekeeping-ruff-baseline` | P1 下一波 | 立即（准入 1/2/3 全满足：计数可复核、影响面为仓库卫生、可一次清账独立成 change；若 Owner 维持「不修基线」口径，则降至 P2 观察） | 2026-11-15 |
| `IMP-add-backtest-engine-07` | `proposal.md`「## 假设/开放问题」**Q1–Q8**（逐条含「影响哪条需求 / 为什么必须现在定」）+ `knowledge-delta.md` §12.1（Q1–Q8 字段形态）+ §12.2（**KQ-1…KQ-7**）+ `verification.md` §11.10「KQ 系列未答复 → 相关维度不参与判定」 | **口径波（P0）**：R2/R3/R4/R5/R6/R7/R8/R14/R15/R16/R17/R18/R19 的数值与判据全部依赖它（其中 **Q4 费率现值**、**Q5 涨跌停/停牌口径** 是真实全 A 成本与撮合的前置）；落地面 = `config/app.yaml` `backtest:` 段（现待 Q 键全 `null`/`[]`，缺键即 `MissingBacktestConfigError`）+ `design.md` §9 开关表 | `resolve-backtest-semantics` | P0 阻塞 | 立即（准入 1/2/3 全满足；是「真实全 A 业务结论」与所有数值开关的前置，Owner 答复后一次性填值 + 回填 design §9 与 proposal 假设表） | 2026-11-15 |
| `IMP-add-backtest-engine-08` | `verification.md` §11.10「S1 业务结论（最高优先）」+ `proposal.md` 假设 **A1 / A4** + 仓库一手证据：`src/dao/models.py:134`（`kline` 仅 OHLCV，**无 `amount`/`avg_amount`**）、三源仅前复权（`src/data_provider/baostock/fetcher.py:363`、`src/data_provider/tushare/fetcher.py:295`、`src/data_provider/akshare/fetcher.py:109`） | **数据前置（P0）**：R7（分层滑点 / 流动性上限需 `avg_amount`）、R9（后复权全 A 序列）、R12（退市 / ST / 历史成分名单）；现状 `data_provider/backtest/` 四适配器默认 `fetch=None` → fail-closed `BacktestDataGapError`；另 **Q4 费率 / Q5 封板口径** 属口径类，由 `IMP-add-backtest-engine-07` 承接，本波数据波与口径波两者合起来才放行「真实全 A 校准结论」 | `add-backtest-data-prerequisites` | P0 阻塞 | 立即（准入 1/2/3 全满足；与 IMP-07 合起来是 proposal S1 从「机制层」走到「业务层」的唯一通路，缺其一则 S1 只能停在机制层） | 2026-11-15 |
| `IMP-add-backtest-engine-09` | `verification.md` §11.6「未覆盖项」+ §11.10「**R3 跨段请求拒绝入口**：§4.1 未单列入口，仅断配置不变量」；现覆盖仅 `TC-R03-02`（配置不变量） | **R3**（跨段报告必须显式列出各段、不得只给合并数字）；`design.md` §4.1、`tasks.md` T2.4 面 | `add-cross-segment-request-guard` | P1 下一波 | 立即（准入 1/2/3 全满足：新增入口级拒绝 + 对应用例可独立成 change；若判定「配置不变量已足够」，须在 design 显式登记该判断后关闭，避免下一波重复讨论） | 2026-11-15 |
| `IMP-add-backtest-engine-10` | `verification.md` §11.10「图表：`matplotlib` 未安装，本 change out of scope」+ `docs/agent-team/ENV.md`（`matplotlib` ❌ 未安装，需先登记再装） | 无 requirement（proposal 已 out of scope）；报告/图表渲染归 `service/report` 既有能力 | `add-backtest-result-charts` | P2 观察 | 观察（**准入 2 不满足**：不落到任何需求锚点，且须先登记依赖；等 Owner 明确要看图再立项） | 2026-11-15 |

> **状态更新（2026-11-15，Owner 答复口径后）**：见下方「状态更新」小节。上方主表（优先级 / 分流）保留写入时的原样**不覆盖**，状态变化一律追加。

#### 状态更新（2026-11-15：Owner 答复 15 条口径）

> 触发：Owner 2026-11-15 答复 Q1–Q8 + KQ-1…KQ-7 → design 落值（t32，`design.md` §9.3）→ 知识库落库（t33，`config/knowledge/canon/` 22 条 canon + 1 条 hypotheses）。**「已答复 / 已落库」不等于「已实现 / 已验证」**。

| ID | 更新后状态 | 依据 | 剩余动作 | 记录时间 |
| --- | --- | --- | --- | --- |
| `IMP-add-backtest-engine-07`（口径波） | **答复完成，波次转「实现 + 复验」段**（优先级保持 P0；不再是「等 Owner 答复」状态） | t32 `design.md` §9.3（24 键行覆盖 15 条答复，提交 `54ea511`）+ t33 `config/knowledge/canon/`（`CAN-SAMPLE-001/002`、`CAN-STATS-001…005`、`CAN-COST-001…005`、`CAN-MATCH-001…004`、`CAN-GROUP-001` + `HYP-GROUP-001`、`CAN-GATE-001…003`、`CAN-CAL-001/002`；提交 `3cd0128`，`check_knowledge_source.py` exit 0） | ① 实现落值（t34：把 §9.3 的值落进 `config/app.example.yaml` 并由消费处读取、缺值仍拒绝）；② 复验（t35：按新口径复跑并出终稿）；③ 唯一保留待确认项 = Q6 的 `tier_count=3`（`HYP-GROUP-001`，`review_at: 2027-02-15`），Owner 显式确认后转 canon | 2026-11-15 |
| `IMP-add-backtest-engine-08`（数据波） | **P0 未变**（不因口径答复而降级） | Owner 答复只解决「口径怎么算」，不解决「数据从哪来」：后复权全 A（A1）、退市 / ST / 历史成分名单（A4）、`avg_amount` 源仍缺（`src/dao/models.py:134`；三源仅前复权 `baostock/fetcher.py:363` / `tushare/fetcher.py:295` / `akshare/fetcher.py:109`） | 按原计划起 `add-backtest-data-prerequisites`；本条与 IMP-07 的 ① 都完成后，proposal S1 才能从「机制层」走到「业务层」 | 2026-11-15 |

#### 本波已闭环（留痕，不占改进点）

> 上游 findings 里已在本波修完的条目，只留痕供下一波查账，**不再作为改进点排期**。

| 来源 | 结论 | 闭环证据 | 记录时间 |
| --- | --- | --- | --- |
| `review-implementation.md` §6 **R2-01**（medium，零触发被当数据缺口） | 已闭环 | t29 实现（`405e961`）+ t30 用例锁定（`1fe099c`）：`data.load_event_observations([])` 直接返回 `()`，`compute_event_study(())` → `verdict=INCONCLUSIVE`；双向可证见 `verification.md` §11.14 | 2026-11-15 |
| `review.md` §9 **R1-01**（medium，`LedgerExportRow.statement` 无数据源） | 已闭环 | `export_ledger(*, experiment_id, hypothesis_id, prereg_dir)` 按 `hypothesis_id` 读预注册 YAML，缺预注册用显式占位 `[prereg-missing]` 并 WARN（`src/service/backtest/registry.py:357-370`）；engineer `test_export_ledger_13_fields_and_statement_from_prereg` 绿 | 2026-11-15 |
| `review.md` §9 **R1-03**（low，`segments`/`run_status` 与结果行 join 规则未定义） | 已闭环 | join 规则写入 docstring：结果行↔执行行按 `hypothesis_id + experiment_id` 关联；`REJECTED/FAILED` 无结果行时导出执行行摘要、`verdict=None`（`registry.py:364-369`） | 2026-11-15 |
| `review.md` §9 **R1-04**（low，`data_version` docstring 与 `RunRecord` 无该字段） | 已闭环 | `RunRecord.data_version: str \| None`（`src/service/backtest/models.py:282`，注释「captain R1-04」），与结果行同名同源，design 的「写入每行」现自洽 | 2026-11-15 |
| `verification.md` §11.11 **F14**（`design.md` §4.2 R13 行签名漂移） | 已消除 | t26（`be35936`，T2-fix-7）已对齐 §4.2 与 §4.1；design 仍 939 行，§10.3 锚点表不受影响 | 2026-11-15 |

## 已晋升记录

<!-- 某条改进点真正进入 MRD 新版本时，在这里登记，形成"改进点 → 基线"的连线 -->

| 改进点 ID | 进入的 MRD 版本 | 对应 change | 时间 |
| --- | --- | --- | --- |
| （本波无晋升：`mrd-v2.md` 目前是**建议稿**，待 Owner 确认后才登记） | | | |