# Agent Team × OpenSpec 协作手册

> 本文件是这套协作方式的**唯一说明书**。每一波交付照它执行；改流程只改这里，并在提交信息里说明原因。
>
> **2026-11-14 升级**：编制从 6 角色 / 8 任务升到 **8 角色 / 11 任务**，新增知识线（K1–K3）。
> **本项目对原手册的两处实质改写**（不是漏抄，是裁决）：
> 1. **知识蒸馏全部人工咨询**：当前客户端找不到可蒸馏的飞书机器人或飞书号，知识条目只能来自「人工答复 + 仓库一手材料」，不做任何自动抓取。见 §13。
> 2. **机检脚本按本仓库实际安装**：装了 4 个（`agent_team_models.py` / `agent_team_preflight.py` / `agent_team_plan.py` / `check_knowledge_source.py`）；原手册的 `verify_traces.py`、`check_knowledge_schema.py`、`scan_prohibitions.py` **未装**，因为它们依赖本仓库不存在的产物（`artifacts/` run 目录、idata `query_id`、知识 loader）。**未装的脚本不许出现在任何闸门或 verify 里**。

## 1. 一句话说清

**MRD 是需求基线，OpenSpec 变更（change）是一次交付单元，Agent Team 是跑这台流水线的编制。**

三者靠「**产物 + 闸门**」耦合，不靠对话记忆、不靠某个 agent 的上下文。任何一环出问题，都能定位到某个文件或某条闸门，而不是「某个 agent 忘了」。

## 2. 一致性模型：五个权威源

| 权威源 | 位置 | 回答什么 | 谁可以写 |
| --- | --- | --- | --- |
| 现实锚点 | `docs/cases/` | 业务**真实发生过**什么、结论对不对（ground-truth） | 人工开采；只追加、不覆盖、不美化 |
| 需求基线 | `docs/mrd/mrd-v{N}.md` | 为什么做、给谁做、边界在哪 | 只由「改进点闭环」产生新版本，且需人工确认 |
| 现行能力 | `openspec/specs/` | 系统**现在必须**做什么 | **只由 `openspec archive` 合并 delta 写入**，任何角色禁止手改 |
| 知识资产 | `config/knowledge/` | 系统**现在知道**什么（口径 / 规则 / 判例 / 映射） | 只由 `knowledge-engineer` 采集，每条带 来源 / 置信度 / owner；跨波存活，不随 change 归档 |
| 交付证据 | `openspec/changes/archive/<date>-<change>/` | 某次交付当时的提案 / 方案 / 验证报告 | 归档后只读 |

**硬规则**：

1. `openspec/specs/` 只能通过 archive 变更。
2. 知识资产**不可发明**——只能从人工答复或仓库一手材料采集，无来源不得入库；**本项目不存在自动蒸馏通道**。
3. 这两条必须写进每个成员的 `executionPrompt`（它们就在 `roles/_shared.md`）。手改主规格会让「现行能力」失真，编造知识会让「知识资产」失真，是这套流程最容易被破坏的两个地方。

## 3. 产物契约（每阶段的完成定义）

| 阶段 | 产物 | 契约要点 | 机器可校验 |
| --- | --- | --- | --- |
| 现实锚点 | `docs/cases/<case-id>/` | `annotations.md`（标注，PM/K1 写）+ `traces.yaml`（溯源，QA 只 append）；ground-truth 只能由业务方标注 | `agent_team_plan.py check` 的 A1 |
| MRD | `docs/mrd/mrd-v{N}.md` | 章节带锚点（`MRD-x.y` 形式），可被 proposal 精确引用 | A2 |
| case 拆解 | `case-teardown.md` | 每条**功能**差距有 case 锚点、产品现状可证伪；「用到的知识」列由 K1 填 | — |
| 提案 | `proposal.md` + `specs/<capability>/spec.md` | Why ≥50 字；What Changes；**Capabilities（New/Modified）**；每条需求标注 MRD 锚点；delta 用 `## ADDED Requirements` / `## MODIFIED Requirements` + `SHALL` + `#### Scenario`（WHEN/THEN） | `openspec.cmd validate <change> --strict` |
| 知识架构 | `knowledge-delta.md` + `config/knowledge/_design.md` | 缺口识别（已有 vs 新）+ 分层 + 准入（强度×频次）+ schema + 升降级 / 退役规则 | 每条知识需求有归属层 |
| 技术方案 | `design.md` + `tasks.md` | 上下文、关键决策**与被否方案及理由**、接口与数据模型、影响面（具体文件路径）、风险与回滚；C 节消费 `_design.md` | `openspec.cmd validate <change> --strict` |
| 代码 | `tasks.md` 全部勾选 + 代码 | 每条 task 能在测试里找到对应断言 | `python -m pytest -q`、`python -m ruff check .` |
| 知识采集 | `config/knowledge/<layer>/*.yaml` | 每条带 来源 / 置信度 / owner / 强度 / 频次 / 生命周期；**不可发明** | `python scripts/check_knowledge_source.py` |
| 验证 | `openspec/changes/<change>/verification.md` | 每条验收标准一行：命令 / 退出码 / 关键输出 / 结论；**必须含负向与边界用例** | 报告里每条命令可重放 |
| 知识验证 | `knowledge-verification.md`（case 回归盲验） | 每条知识放回 case，能否复现结论；**盲验** | 每条有结论（通过 / 降置信度 / 退回） |
| 归档 | 主规格合并 + archive 目录 + 知识入库放行 | `Purpose` 无 `TBD` **且不少于 50 字符**；`verification.md` 随目录归档 | `openspec.cmd validate --specs --strict`、`openspec.cmd doctor`、`openspec.cmd list` 无该 change |

**CLI 注意事项（本机实测）**：

- `openspec` 必须写成 **`openspec.cmd`**：直接敲 `openspec` 会命中 PowerShell 执行策略（禁止运行 `.ps1`）而失败。
- 裸跑 `openspec.cmd validate --strict` 在非交互终端会进入「选择条目」交互，**脚本里必须指明条目**：归档前 `openspec.cmd validate <change> --strict`，归档后 `openspec.cmd validate --specs --strict`。
- `validate --specs --strict` 会把「`Purpose` 仍是 `TBD` / 占位句」判 **failed**（不是 warning）；`Purpose` 还有 **50 字符下限**。
- `openspec archive --yes` 会**越过**未完成任务清单继续归档。所以「tasks 全勾 + verification 存在」这道判断只能由 integrator 在归档前做，不能指望 CLI 拦。

**一个 change = 四个产物，三个角色承接，全部 OpenSpec 原生**：`proposal.md` + `specs/`（product-manager）→ `design.md` + `tasks.md`（architect）→ 代码（engineer）→ `verification.md`（qa）→ `review.md`（reviewer）。MRD 是业务基线，`proposal.md` 是它的 change 级切片，**两者之间不再插一层 PRD**。

## 4. 一波的 DAG

8 名成员、11 个任务，两条线并行：**代码线**（T2–T8 主干）+ **知识线**（K1–K3）。两条线都从 T1 的 case 拆解分叉，在 T8 汇合。知识线用 `work` kind——Agent Teams 的质量闸门 kind 面向代码，知识质量靠「case 回归盲验 + reviewer 去重 + 知识不可发明」三重约束。

| ID | 任务 | kind | 负责成员 | 依赖 | 产出 |
| --- | --- | --- | --- | --- | --- |
| T1 | case 牵引 + 拆解（功能）+ 需求澄清 + 切分与提案 | `requirements` | `product-manager` | — | `case-teardown.md` + `proposal.md` + specs delta |
| K1 | 知识缺口识别 + 分层架构设计 | `work` | `knowledge-architect` | T1 | `knowledge-delta.md` + `config/knowledge/_design.md` |
| T2 | 技术方案 + 任务拆解 | `work` | `architect` | T1, K1 | `design.md`（C 节消费 `_design.md`）+ `tasks.md` |
| K2 | 知识采集 / 结构化落库 | `work` | `knowledge-engineer` | K1 | `config/knowledge/` 条目 + `known_unknowns.yaml` |
| T3 | 代码实现 | `implementation` | `engineer` | T2 | 代码 + `test/`（TDD 单测） |
| T4 | QA 测试设计 | `work` | `qa` | T2 | `test/qa/`（验收 / 负向 / 对抗用例，盲测） |
| K3 | 知识验证（case 回归盲验） | `work` | `qa` | K2, T1 | `knowledge-verification.md` |
| T5 | QA 测试执行 + 报告 | `verification` | `qa` | T3, T4 | `verification.md` |
| T6 | 交付评审 | `review`（`reviewedTaskId`=T3） | `reviewer` | T3, T5, K3 | verdict + `review.md`（含去重） |
| T7 | 改进点 + 知识需求回流 + MRD 演进 | `work` | `product-manager` | T5, T6, K3 | `IMPROVEMENTS.md` 追加 + MRD 新版本建议 |
| T8 | 归档 + 知识入库放行 + 合并回 main | `integration` | `integrator` | T5, T6, T7, K3 | 归档目录 + 主规格 + feature 合回 main |

**为什么 T1 与 T7 是同一人**：回到 MRD 的动作必须由**当初切需求的那个人**做。换人会让「改进点」变成「新需求」，失去与原基线的连线。知识需求的两个来源（K1 从 case 识别的缺口 + T6 从代码查重的发现）最终在知识库汇流，T7 只负责把 T6 的发现记成待办。

**为什么知识线（K1–K3）独立于代码线**：知识与代码生命周期不同——代码随 change 归档（有终点），知识跨波存活（无终点，持续升降级 / 退役）。因此知识线不并入 `implementation/review/repair` 闸门，而用三重约束：**case 回归盲验（K3）+ reviewer 去重（T6 第 B8/B9 项）+ 知识不可发明（K2 失败定义）**。

**为什么 K3 是 QA 做盲验**：K2 自己采自己验 = 利益冲突，与「QA 盲测不读实现」同一道理。QA 拿 case + 知识做盲验，**不读 K2 的采集过程**。

**为什么 QA 拆成 T4+T5、且 T4 与 T3 并行**：测试设计从 spec + 成功标准**盲测**设计、不读实现，避免被实现带偏；执行必须等代码就绪。两段拆开才能让「设计测试」与「写实现」真并行。

**为什么 T8 依赖 T7 与 K3**：合并回 main 是发布动作，必须等 T7 的改进点与知识需求落盘、K3 盲验放行，main 才能一次拿到完整波次产出。

## 5. 编制与权责边界（角色 SOP 索引）

> 完整 instruction 见 [`roles/`](roles/)：起波时成员的 `executionPrompt` = `roles/_shared.md` 全文 + `"\n\n"` + `roles/<角色>.md` 全文。下表是索引，`roles/` 是正文。

| 成员 | 模型 / effort | 任务 | 一句话边界 |
| --- | --- | --- | --- |
| `product-manager` | Flash / high | T1、T7 | 只写 proposal / specs delta / case-teardown / `docs/`；不写代码、不碰知识细节、不产 knowledge-delta |
| `knowledge-architect` | Flash / high | K1 | 只定义知识容器（分层 / schema / 退役）+ 缺口清单；不填知识内容、不写代码 |
| `architect` | **Pro** / high | T2 | 只写 `design.md` + `tasks.md`；C 节消费 K1 的分层，不改层语义 |
| `knowledge-engineer` | Flash / low | K2 | 只写 `config/knowledge/` 条目；**只能采、不能发明**，采集入口仅人工答复 + 仓库一手材料 |
| `engineer` | Flash / high | T3 | 只写 `src/`、`test/`、`tasks.md`（仅勾选）；不自拆任务、不改 design |
| `qa` | Flash / low | T4、K3、T5 | 只写 `test/qa/`、`verification.md`、`knowledge-verification.md`、`traces.yaml`（只 append）；盲测 / 盲验 |
| `reviewer` | **Pro** / high | T6 | 只读被评审产物；verdict + findings 必须落 `review.md` |
| `integrator` | Flash / low | T8 | 只经 `openspec archive` 写主规格；只合并本波 feature 分支 |

**captain（会话本身承担）**：编排波次、守人工检查点、处理阻塞与越权、发布兜底、流程自迭代。不写业务产物、不手改 `openspec/specs/`；流程文档（PLAYBOOK / roles / templates）的修改归 captain。

**模型分级的唯一真值源是 [`models.yaml`](models.yaml)**，成员模型 id 用 `python scripts/agent_team_models.py --json` 解析后传入，**不手抄、不用 `list_subagent_models`**（它只列出 `coding_plan` 子集，本机实测漏掉 `deepseek-v4-pro`）。

## 6. Git 分支工作流（每波一个 feature 分支）

| 步骤 | 谁 | 动作 |
| --- | --- | --- |
| 切分支 | captain | 起波时 `git checkout main && git pull`，再 `git checkout -b feature/<change-name>` |
| 分支上开发 | 全员 | T1–T8 全部在 `feature/<change-name>` 上工作与提交 |
| 归档（分支上） | integrator (T8) | 在分支上完成 `openspec.cmd archive` + 提交，**此时不合并 main** |
| 改进点落盘 | product-manager (T7) | 在分支上追加 `IMPROVEMENTS.md` + `mrd-v{N+1}.md` 并提交 |
| 合并回 main | integrator (T8) | `git checkout main && git merge --no-ff feature/<change-name>`；冲突走人工 |
| 清理 | integrator | 合并后删除 feature 分支（或打 tag 留存） |

规则：

- 分支命名 `feature/<change-name>`，与 change 名一一对应。
- **main 永远是「已发布」状态**；任何越权直接写 main 都视为违反权威源规则（与手改 `openspec/specs/` 同级）。
- 跨波隔离：下一波从最新 main 切新分支，不接力旧分支。
- 本项目串行波次、一次一个 feature 分支；如需并发，先走 CP1 说明并评估冲突面。
- 本机 `git pull` 曾实测失败（GitHub 连接被重置）：不可用时跳过拉取，基于本地 `main` 切分支，并在起波记录里注明「未拉取远端」。**合并回 main 是本地操作，不受影响**；推送远端由 Owner 自行处理。

## 7. 人工检查点

| 检查点 | 时机 | 强度 |
| --- | --- | --- |
| **CP1 波次计划审批** | 团队 staged 后、调度前 | **必须**。每次都要看：范围对不对、MRD 锚点引对了没、DAG 有没有漏闸门 |
| **CP2 技术方案 sign-off** | T2 完成后、T3 启动前 | 建议前 2 波保留，流程稳定后可放宽为抽查 |
| **CP3 归档前验收** | T6 之后、T8 之前 | 建议前 2 波保留。看 `verification.md` + `review.md` |

流程稳定（连续 2 波无 `needs_revision` 返工、无越权）后，CP2 / CP3 可降级为「看报告即可」，但 **CP1 永远保留**——它成本最低、拦截率最高。

**知识线的额外人工口径**：K1 / K2 需要业务口径确认时，问题经 captain 转交 Owner；**1 小时无答复即标「未解决」并记入 `IMPROVEMENTS.md` 下波补**，不许脑补、不许拿 `ref/` 或代码现状顶替业务确认。

## 8. 起一波的机械步骤

```text
1. 确认基线      → docs/mrd/ 最新版本号 + docs/cases/ 有无 ground-truth case；没有就先补，不硬开
2. 定变更名      → kebab-case，动词开头，例如 add-volume-price-divergence
3. 切分支        → git checkout main（pull 可用则 pull）；git checkout -b feature/<change>
4. 计划落文件    → python scripts/agent_team_plan.py init --change <change> --case <case>
                   生成 docs/agent-team/plans/<change>.yaml，按本轮 MRD 填 wave 头与 11 个任务
5. 计划自检      → python scripts/agent_team_plan.py check   必须退出码 0（29 条断言：
                   编制 / DAG / 契约 / inScope / verify / 预算 / case / git）
6. 解析模型      → python scripts/agent_team_models.py --json   拿 8 个角色的真实 model id
7. 环境预检      → python scripts/agent_team_preflight.py       退出码 0 才起波
8. 建队          → agent_teams_create(approval="required", plan={members: 8 人})
                   成员传 name + 第 6 步的 id + models.yaml 的 effort；不传裸名
9. 建任务        → 11 个任务逐个 create_task，参数用
                   python scripts/agent_team_plan.py render <ID> --json 取，**不手抄**
10. 人工审批     → CP1（approval="required" 建完停在 staged，人未点 Approve 前不唤起任何成员）
11. 调度中       → 只处理：阻塞报告、越权告警、契约错误。守两条：
                   ⚠️ attempt 静默丢失：任务 in_progress + 成员 idle/ready + 无产物无报错 = attempt 已断，
                      同一状态持续 15 分钟就 reassign_task 重派，不要「再等等」
                   ⚠️ 依赖只从下游加：需要串行就把依赖挂在下游任务上
                   ⚠️ work kind 无 acceptance 承载、启动后不可编辑，完成/失败定义必须建之前写进 description
12. 收口         → 所有任务终态 + 成员 idle → 先跑收口闸门：
                   python scripts/agent_team_plan.py closeout --plan docs/agent-team/plans/<change>.yaml
                   python scripts/check_knowledge_source.py
                   → 再读 verification.md、knowledge-verification.md 与 findings → 登记流程疏漏
                   闸门红 = 不许归档；warning 允许带过但必须在收口报告里点名
13. 归档+发布    → integrator(T8) 完成归档、知识入库放行、合并 feature 回 main；人工 CP3 抽查
14. 关团队       → agent_teams_delete（归档留档，团队不长期挂着）
15. 修流程       → captain 修 FLOW-ISSUES 的 P0/P1（改 PLAYBOOK / roles / templates）；
                   修完必须 grep 抽查上批「已修」是否仍在位，复查通过才起下一波
16. 下一波       → 从最新 main 切新分支，用 T7 的改进点与知识需求起新 change，回到第 2 步
```

任务描述里必须带**可执行的 verify 命令**，不要写「跑一下测试」这种不可判定的话。

## 9. 闭环：改进点 → 下一版 MRD

改进点台账在 `docs/improvements/IMPROVEMENTS.md`，**只追加不覆盖**。每条必须包含：

| 字段 | 要求 |
| --- | --- |
| ID | `IMP-<wave>-<序号>`，例如 `IMP-add-volume-price-divergence-01` |
| 来源证据 | 指向具体验证条目或 finding id，禁止「感觉不好」 |
| 影响面 | 涉及哪个能力 / 哪个文件 / 哪条需求 |
| 建议变更名 | kebab-case，能直接当下一波的 change 名 |
| 优先级 | `P0 阻塞` / `P1 下一波` / `P2 观察` |
| 分流结论 | `立即` / `观察` / `否决`（否决也要记录理由） |

**晋升到 MRD 的准入条件**（三条全满足才允许改 MRD）：

1. 有现存证据（验证报告或 findings 里能指到）；
2. 影响面描述得清（能说出改哪条需求）；
3. 能被切成一个独立的 change。

MRD 演进**用 diff 表达，不要整篇重写**：在 `mrd-v{N+1}.md` 里只写相对上一版的增删改，保留旧章节锚点编号。

### 知识需求的两个来源（双源闭环）

| 来源 | 方向 | 信号 |
| --- | --- | --- |
| T1 case 缺口 | 前瞻 | 「case 用了 X 知识，我的产品没有」 |
| T6 查重发现 | 后顾 | 「代码里已经长出 X 知识，还写了两份（`knowledge-abstraction` finding）」 |

两者都在 T7 由 PM 汇流成下一波的知识需求。前者看得到「缺」，后者看得到「多而散」，合起来才是知识负债的完整面。`capability-abstraction` finding 则走改进点（「抽象共享能力」的下一波 change）。

### 现实回流（打破内部自循环）

`IMPROVEMENTS.md` 的信号源不能只有内部验证（`verification.md` 未覆盖项 + `review.md` 非阻塞 findings），还要接**现实回流**：真实跑分析任务时的使用反馈（哪个报告没人看、哪个结论被推翻、哪次人工干预最多、重跑率），作为一等改进信号进 T7，优先级至少 P1。archive 不等于投产。

## 10. 异常与返工规则

| 情况 | 处理 |
| --- | --- |
| review 返回 `needs_revision` | 自动进入 repair + 下一轮 review（框架自带），不要手工绕过 |
| review finding 属**知识内容**缺陷（口径取值 / 溯源 / 置信度） | **不得**判 `needs_revision` → 记 `knowledge-abstraction`，交 K2（当波整改任务）或 T7（下一波回流）。否则框架会自动生成 **engineer 的代码 repair**，修复目标打偏 |
| 知识 yaml 里值冲突 | `pass` + captain 立即建 K2 同波整改任务（判 `needs_revision` 会路由成代码 repair，修错对象） |
| 代码里同一知识硬编码多处且**值不一致** | `needs_revision`（两份口径已冲突，系统会产出不一致结果），本波 repair 统一到知识层 |
| 归档后 `openspec.cmd validate --specs --strict` 变红（`Requirement text is very long`） | delta 的 blockquote 锚点 prose **计入** requirement 字符额度。锚点只留「一行结论 + 指针」，推导外置到 `verification.md` / `knowledge-delta.md`；**不得**为凑字数改写 normative `SHALL` 句 |
| 同一时刻多个成员要动 git | captain 指定节拍器，串行化。有 `reset --hard` 的一方**必须先落地并报告**。禁 `-a`/`-am`，只 `git add <具体路径>`，提交后 `git show --name-only` 核对 |
| `verify` 命令根本不可能通过 | 用 `agent_teams_amend_task` 修**契约本身**并在 reason 里写清；**不许**为过闸门放宽 acceptance |
| 实现中发现方案不可行 | 停下，回到 T2 重开方案。禁止在实现里偷偷改设计 |
| 验证发现缺陷但验收标准已满足 | 不算通过验收，记 P1 改进点；若属安全 / 数据正确性问题则升 P0 并阻塞归档 |
| QA 测试失败（`test/qa/` 有红） | QA 写结构化 finding（id / severity / problem / requiredFix / 文件:行）→ reviewer 判 `needs_revision` 并引用 finding → 框架自动 repair → engineer 修到全绿 → 下一轮 review 复审 |
| QA 用例自身有 bug（断言写错） | engineer **不得**私自改 `test/qa/`，报 captain → QA 自己修正测试用例，再重跑 |
| 任务长期无产出 | 用 `agent_teams_reassign_task` 换人或重试，不要反复发消息催 |
| 判据里出现会随生命周期消失的对象（活动 change 名 / 临时目录 / 未归档状态） | 必须写**前 / 后两支**且两支都断言内容（不能只判 exit code）：归档前 `openspec.cmd validate <change> --strict`，归档后 `openspec.cmd validate --specs --strict` 且逐条点名 capability |
| 成员请求「放宽 verify 以绕过已知红」（`-k "not (…)"`、`--deselect`、删用例） | **默认驳回**。命令变绿而断言仍红 = 假绿，比删测试更隐蔽。正路只有两条：修掉那批红，或明文宣布外部阻塞并给最小缺口清单 |
| 判 `failed` 但失败原文是 `MALFORMED_RESPONSE` / JSON 解析错 | 先读 payload：多半是**已完成的工作没记上状态**。只重发状态，**禁止重做 git 操作**。成员侧纪律：`update_task` 的字符串值内不得出现未转义双引号、不得嵌 `.replace(...)` 之类表达式 |
| 收口时读「任务清单」 | `tasks.md` 全勾 ≠ 验收达成：它记「有没有做」，`proposal` 成功标准记「做成了没有」。T7 必须逐条标「达成 / 未达成」并给证据，未达成不得写成「部分达成」 |
| 归档后框架报 `verdict covers a revision that no longer exists` | **归档波的预期现象，不要去「修」**：`openspec archive` 删除 change 目录（含 `tasks.md` / `design.md`），而 T5 / T6 的 verdict 绑定含这些文件的字节。判定以归档后重跑的测试 / `validate --specs --strict` 为准 |

### 判据自检三问（写判据的人也要过）

一条判据的价值 = 别人能否**独立复算**它。做不到就不是判据，是表态。任何验收 / verify 命令写进契约前，先自问三句：

1. **它能红吗？** 拿一个已知的违规样本跑一遍，看它是否真的失败。永远红的判据会逼实现去改对的代码。
2. **它红的是不是它该红的原因？** 反例：`except Exception: pytest.skip` 把「闸门阻断」兜成「未运行」，报告里只统计 failed 就完全看不见。
3. **它绿的时候是不是真绿？** 长度 / 计数类判据一律复用仓内既有函数或命令输出，禁手算。

配套两条纪律：**证据必须由命令输出粘贴**（全精度数值、commit sha、SQL 片段三类尤其）；**自检链没打印过的东西，就等于没验证过**（报告里要 sha，自检链里就必须有 `git rev-parse HEAD`）。

## 11. 反模式（见到就拦）

1. **团队发明需求**：proposal 里出现 MRD 没有的能力 → 打回 T1，要求给锚点。
2. **绕过闸门**：手工勾 `tasks.md`、`archive --yes` 跳验证、手改 `openspec/specs/`。
3. **验证报告写成自我表扬**：没有命令、没有退出码、没有负向用例的报告一律不接受。
4. **一个波次塞太多**：一个 change 覆盖多个不相关能力 → 拆成多个波次。
5. **团队常驻不清**：波次结束不关团队，下一波会串味。
6. **把 MRD 当一次性输入**：MRD 不随改进点演进，闭环就断了。
7. **越权直接写 main**：与手改 `openspec/specs/` 同级，一律拦。
8. **知识硬编码 / 重复造轮子**：同一口径 / 阈值 / 规则多处硬编码（尤其值已不一致）、同一能力被多方重复实现 → reviewer B8 该拦，值不一致升 blocker。
9. **知识发明**：知识条目无来源 / 把假设当确定 / 把业务没确认的口径写进库 / 拿 `ref/` 或代码现状当业务确认 → 打回 K2。
10. **脱离现实锚点**：起波不做 case 拆解就切需求（闭门造车）→ 打回 T1。
11. **判据不可复算**：百分比没分母、把展示值当精确值断言、只给结论不给命令与退出码。
12. **用字面 grep 判语义**：把禁止语境里的引用当违规（或反之），会让 review 判错 verdict 并触发打偏的自动 repair。
13. **假绿测试**：用自建 fixture 断言知识 / 配置内容，真文件被改也不红——测试存在但不保护任何东西。
14. **评审产物只在任务字段**：verdict 没落 `review.md`，下游（T7 / integrator）只能靠口头传话，归档闸门必卡。
15. **凭记忆起队**：不读当波 `PLAYBOOK.md` / `templates/wave-tasks.md` / `models.yaml`，按「印象里的配置」建队——成员少 2 个、任务少 3 个，知识线整条缺失。**起队前必须现读对账，并把基线 commit 记进 `plan.yaml` 的 `baseline_commit`。**
16. **判据没人验**：验收 / verify 写进契约前没自问「能不能红 / 红的理由对不对 / 绿得是否真实」。
17. **拿手抄的证据当证据**：报告里贴手写片段、手抄全精度数值、凭记忆写 commit sha。
18. **在别人做 git 操作时动索引**：共享工作树下 `commit -a/-am`，把别人正在跑的归档 / 合并中间态一起提交。
19. **把红排除出判据范围**：`-k "not (…)"`、`--deselect`、删用例、把 verify 改成只跑绿的那部分。
20. **恒 skip 的假门**：`if 有就测、没有就 skip` 的开门条件写成「我没取到」而不是「确实不存在」。
21. **采信类规格只写正向**：能力含「采信 / 采纳 / 推荐 / 判异」却不写「什么必须被拒 + reason」→ spec 必须有反向 Scenario。
22. **拿任务清单当验收结论**：`tasks.md` 全勾就宣布完成，而 `proposal` 成功标准里还有「未达成」。

## 12. 产物语言

`openspec/config.yaml` 已锁定 `zh-CN`：正文中文，但 `## ADDED Requirements`、`SHALL` / `MUST`、`#### Scenario` 等结构性标记保留英文，保证 CLI 解析与校验正常。

## 13. 知识线专章：本项目为什么全部人工咨询

**背景（2026-11-14 用户裁决）**：原手册的知识蒸馏依赖飞书机器人 / 飞书号（`lark-cli`、`reference/lark-wiki` 快照、业务答疑群会话）自动采集口径。**当前客户端找不到可蒸馏的飞书机器人或飞书号**，因此这条通道整体停用：**知识蒸馏一律先咨询人**。

### 13.1 采集入口（只有两个）

| 序 | 入口 | 怎么用 | 可标到什么置信度 |
| --- | --- | --- | --- |
| 1 | **人工答复** | 成员整理问题清单（表单式、一次性、只给业务口径）→ `agent_teams_send_message` 报 captain → captain 转交 Owner / 业务方 → 答复回填 | `确定`；`source` = 「人工答复:<谁>:<日期>:<主题>」+ 原话短引文 |
| 2 | **仓库内一手材料** | `docs/mrd/`、`docs/design/`、`config/*.yaml`、`openspec/specs/`、现有 `src/` 与 `test/` 断言（只读） | `确定`（仅限「现在是什么」）；`source` = 文件:行 + 引文 |

补充信源（**只能标假设**）：`ref/` 只读快照（方法参考）、`web_search` / `web_fetch`（外部资料）。

**禁止**：飞书机器人、飞书号、`lark-cli`、任何自动抓取或自动蒸馏；凭库内容或名字猜「已有 vs 新」。

### 13.2 提问纪律

- **问题里不许塞实现假设**（表名 / 字段名 / 模块名 / 阈值取值），否则会拿到顺着问题编出来的答案。
- **表单式一次问清**，不多轮追问（追问 = 把成本转嫁给业务方）。
- 答复回来必须带**答复人 + 日期 + 原话**写进 `source`；转述过的答复不算 `确定`。
- **1 小时无答复**：该知识标「未解决」→ `config/knowledge/known_unknowns.yaml` 记「待谁确认」→ 缺口记入 `docs/improvements/IMPROVEMENTS.md` 下波补。**不许脑补、不许拿代码现状或 `ref/` 顶替。**

### 13.3 知识线的验收

| 任务 | 闸门 |
| --- | --- |
| K1 | `knowledge-delta.md` 每条有「已有 vs 新」+ 归属层；`config/knowledge/_design.md` 有分层 / schema / 升降级退役规则 / ≥1 被否方案 |
| K2 | `python scripts/check_knowledge_source.py` 退出码 0（无来源知识 = 0）；`known_unknowns.yaml` 如实记录 |
| K3 | `knowledge-verification.md` 每条有结论（通过 / 降置信度 / 退回），**盲验**（不读 K2 采集过程） |

知识线**不并入** `implementation` / `review` / `repair` 质量闸门——那些闸门面向代码，套在知识上会路由出错误的修复对象。
