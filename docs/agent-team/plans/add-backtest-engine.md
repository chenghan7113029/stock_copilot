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
