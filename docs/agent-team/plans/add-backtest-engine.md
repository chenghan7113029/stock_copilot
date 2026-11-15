# 波次计划：add-backtest-engine（设计段）

- 波次：`add-backtest-engine`
- 分支：`feature/add-backtest-engine`（基于本地 `main`，本机 `git pull` 不可用，未拉取远端）
- 需求一手来源：飞书《投资Agent》r482 → 快照 `docs/agent-team/inputs/feishu-invest-agent.md`
- 范围：**只做设计段**（T1 → K1 → T2 → T4），不写生产代码、不改 `openspec/specs/`、不归档
- 团队：`product-manager` / `knowledge-architect` / `architect` / `qa`（4 人，按 `models.yaml` 解析模型）

## 与标准起波流程的偏差（已知并记录）

| 标准步骤 | 本波处理 | 理由 |
| --- | --- | --- |
| `agent_team_plan.py init/check`（29 条断言，按 11 任务全量 DAG） | **未执行** | 本波是设计段子集（4 任务），全量断言要求 case 目录与 11 任务编制，套用会红；另 `docs/cases/` 目前没有 ground-truth case |
| CP1 人工审批 | 由 Owner 的「启用 Agent Team + 实现设计」指令直接放行，计划在本文件与 captain 汇报中呈现 | Owner 明确要求立即产出设计 |
| T3/T5/T6/T7/T8 | 本波不建 | 设计段止于 CP2；实现段待飞书 comment 后另起 |
| case 牵引 | 无 ground-truth case，改用飞书文档 + 仓库一手材料 | T1 任务契约要求显式记录「MRD v1 未定稿」，不得假装有 MRD 锚点 |

## 任务与依赖

| ID | 任务 | kind | 负责 | 依赖 | 产物 |
| --- | --- | --- | --- | --- | --- |
| T1 | 回测模块需求：提案 + specs delta | `requirements` | product-manager | — | `proposal.md` + `specs/backtest-engine/spec.md` |
| K1 | 回测知识缺口识别 + 分层架构 | `work` | knowledge-architect | T1 | `knowledge-delta.md` + `config/knowledge/_design.md` |
| T2 | 技术方案 + 任务拆解 | `work` | architect | T1, K1 | `design.md` + `tasks.md` |
| T4 | 测试设计（盲测） | `work` | qa | T2 | `test-design.md` |

## 飞书同步（captain 执行）

- 目标文件夹：`投资Agent批注`（`WCiWfrGDplbcuUdJFYQcXO74n3c`）
- 方式：`docs +create --doc-format markdown --parent-token <folder>`（实测：真表格 / 列表 / 代码块均正确落块）
- 计划文档：01 需求提案 / 02 规格增量 / 03 知识分层 / 04 技术方案 / 05 测试设计

## 待 Owner 决策的口径（会被成员收集上报）

- 成本参数具体数值（佣金 / 印花税 / 分层滑点档位）
- 样本切分区间首尾口径（2015–2020 / 2021–2023 / 2024–2026 的边界交易日）
- 三级门禁阈值（「不劣于基准」定义、影子期长度、方向一致判据）

## 本轮 captain 裁决（记录在案）

1. **QA-F1 落位口径**：以 `design.md` §6.7 的 `test/qa/backtest/test_*.py` 为准（与 `src/service/backtest/` 镜像），T4 负责改自己的落位名（t6）。理由：扁平目录在未来多模块下会膨胀，且子目录与 `test/` 镜像 src 的既有约定一致。
2. **ruff 基线 39 错误**：判定为「起波前既有基线偏差」，**不在本设计波修复**（不混入设计分支）。T5 验证报告须如实记录 `python -m ruff check .` exit=1 + 28 个既有文件清单 + 「本 change 产物（.md）不在 ruff 覆盖范围」的证据，并在 `IMPROVEMENTS.md` 记 P1。修复基线另起一个 housekeeping 波。
3. **QA 发现的 8 条契约缺口**：不降级为「实现时再说」，追加 T2-fix（t5）在设计层闭合，再由 T4-fix（t6）复核 `TODO(QA-Fx)`。保持「设计先行、实现不迁就」。

## 收口状态（设计段冻结）

- 冻结 commit：`4139f34`（分支 `feature/add-backtest-engine`，未 push）
- 产物规模：`proposal.md` + spec delta（19 Requirement / 56 Scenario）· `knowledge-delta.md`（80 条知识）· `config/knowledge/_design.md`（5 层）· `design.md`（822 行）· `tasks.md`（T2.1–T2.20）· `test-design.md`（894 行 / 56 TC / 19 文件）
- QA finding 闭环：`QA-F1–F11` **11/11 闭合，TODO 0**（8 → 2 → 1 → 0 四轮收敛）
- 飞书同步：7 篇（01 提案 / 02 规格增量 / 03 知识缺口 / 04 知识分层 / 05 技术方案 / 06 任务拆解 / 07 测试设计），05/06 已刷新为冻结版
- 待 Owner：Q1–Q8、KQ-1…KQ-7、前后复权裁决；未答复前 `BacktestConfig` 缺键即拒绝，台子不出带成本结论
- 未做：T3 实现、T5 验证、T6 评审、T7 回流、T8 归档（等设计评审意见后另起）

## 实现段收口状态（2026-11-15）

- 冻结 commit：`1fe099c`（代码树；`6f61ab3` 为 T7 台账提交，仅 docs）
- 门禁：全量 `-m "not network and not akshare_legacy"` **1065 passed / 35 deselected / exit 0**；QA `test/qa/backtest` **57 passed**（56 Scenario + 1 条 R2-01 锁定用例）；本 change ruff 路径 **新增 0**；`validate --strict` valid
- T5 终审：`verification.md` §11 **通过**（t25；t27 补记 §11.13；t30 复验补记 §11.14）
- T6 代码评审：`review-implementation.md` **pass**，3 条 finding（R2-01 medium 已由 t29 修复 + t30 锁定；R2-02/R2-03 low 入 T7）
- T7：`IMPROVEMENTS.md` 10 条（P0×2 口径波/数据波、P1×6、P2×2）+ `docs/mrd/mrd-v2.md` 建议稿（待 Owner 确认，未定稿）
- 残留：R2-01 已闭环；`--specs --strict` 76 failed 属 ENV.md 已登记的主规格 Purpose 存量债（非本 change）
- 失败任务账面：`t13`（首轮实现，全量含 QA 未绿）、`t14`/`t20`（验证基线「不通过」，5 条待裁决）均已由后续 t17/t21/t23 对齐 + t19/t24/t30 修夹具 + T5 终审闭环。框架提示「failed without follow-up repair」是因为 repair 类型要求 `sourceFindingId`，而三次 failed 均为「闸门红」而非评审 finding，故未造 finding 补账；对应工作由 t29（R2-01 repair）与 T5 终审逐条核对承担。

## captain 裁定补充（2026-11-15）

- **IMP-06（ruff 38 存量基线）**：维持「本波不修、不记失败」口径；T7 台账标 **P1 下一波 / 独立 housekeeping change**，不得并入功能波。理由是静态债与回测需求无关，混入会让评审 diff 失真。
- **归档（T8）未执行**：`openspec archive` + `merge --no-ff` 属发布动作，等 Owner 明确同意后再派 integrator。
- **口径波与数据波**：IMP-07（Q1–Q8 + KQ-1…KQ-7）与 IMP-08（A1/A4/avg_amount）是 P0，二者合起来才可能让 proposal S1 从「机制层」走到「业务层」；在答复前，所有未确认值保持「缺键即拒绝」。

## 交付记录（2026-11-15 收波）

| 项 | 值 |
| --- | --- |
| 归档 | `openspec/changes/archive/2026-11-15-add-backtest-engine/`（12 项：proposal/design/tasks/verification/review/review-implementation/test-design/knowledge-delta/specs/references/README） |
| 主规格 | `openspec/specs/backtest-engine/spec.md`（19 R，Purpose 已写、无 TBD、≥50 字符） |
| 分支合并 | feature HEAD `796dbc5` → main HEAD `1a419d9`（`merge --no-ff`，无冲突）；**feature 分支保留** |
| 远端 | **已 push**（2026-11-15）：`origin/main` `ba609a0..b1be868`；`feature/add-backtest-engine` `796dbc5` 作为备份分支推送（未删） |
| 门禁（main 复核） | 全量 **1091 passed / 35 deselected / exit 0**；QA `test/qa/backtest` 62 passed；`validate --specs --strict` **24 passed / 76 failed**（基线 23/76 → **无新增失败**）；`doctor` ok；`check_knowledge_source.py` 0 error；ruff 全仓 38 存量（本 change 新增 0） |
| 遗留（已入台账） | R2-02/R2-03（low → IMP-01/02）；e2e 种子库（IMP-05）；ruff 基线（IMP-06）；76 条主规格 Purpose 存量债（housekeeping 波） |
| 未定值 | `max_delay_days` / `min_events` 仍为 `null`（Owner 未答；消费处会抛缺键） |

**流程疏漏（本波发现，待修）**：`agent_team_plan.py closeout` 只接受 `plans/<change>.yaml`，而本波计划盘是 `.md`，导致收口脚本 `exit 2`（不阻断三闸门，已如实记录）。决议：后续波按 PLAYBOOK §8 用 `agent_team_plan.py init` 生成 `.yaml` 计划；或给脚本增加 `.md` 兼容。本波不回溯改造。
