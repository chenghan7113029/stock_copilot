# 波次任务契约模板

> 用法：复制本文件内容，替换所有 `<...>` 占位符，然后把「成员」与「任务」两段作为
> `agent_teams_create(approval="required", plan={members, tasks})` 的输入。
>
> **契约纪律**：`verify` 里只写真实可执行的命令，不写"跑一下测试"这类不可判定的话。
> 命令必须从当前仓库真实结构推导出来 —— 本仓库代码根是 `src/`（扁平多包），测试是两套
> （engineer `test/` + QA `test/qa/`），解释器命令就是 `python`（Windows 上没有带数字后缀的那种写法）。

---

## 变量清单（先填这些）

| 变量 | 含义 | 本仓库示例 |
| --- | --- | --- |
| `<change>` | 本波 change 名，kebab-case 动词开头 | `add-fundflow-divergence` |
| `<capability>` | 本次新增/修改的 capability（`openspec/specs/` 下的目录名） | `cli-report-fundflow` |
| `<case>` | 本波对照的 case，`docs/cases/<case>/` 的目录名（**必须有 ground-truth**） | `fundflow-outflow-divergence` |
| `<mrd>` | MRD 版本文件 | `docs/mrd/mrd-v1.md` |
| `<mrd-anchors>` | 本波覆盖的 MRD 锚点 | `MRD-3.1, MRD-4.1` |
| `<test-cmd>` | 测试命令 | `python -m pytest -q` |
| `<lint-cmd>` | 静态检查命令 | `python -m ruff check .` |
| `<knowledge-root>` | 知识库目录（**现存**：初始只有 README + `known_unknowns.yaml`；K1 产出 `_design.md` 定分层，K2 填 `<layer>/*.yaml`） | `config/knowledge/` |
| `<team>` | 团队名，与 change 同名 | `add-fundflow-divergence` |

> **变量纪律**：`<test-cmd>` / `<lint-cmd>` 起波前各跑一遍，把实际输出（passed / failed 数、退出码）
> 写进对应 acceptance 的「起跑时实测值」；`<case>` 没有 ground-truth 标注就不许起波（见 `docs/cases/README.md`）。

## 本仓库常量（不用填，照抄）

| 项 | 值 |
| --- | --- |
| 代码根 | `src/`（扁平多包：`apps/ controller/ service/ data_provider/ dao/ common/`） |
| 测试双轨 | engineer `test/`；QA `test/qa/`（互不越界） |
| 需求 / 规格 / case | `docs/mrd/`、`openspec/`、`docs/cases/<case>/` |
| openspec 调用 | 一律 `openspec.cmd <args>`（本机 ExecutionPolicy 禁 `.ps1`，裸 `openspec` 会报"禁止运行脚本"） |
| 静态检查 | `python -m ruff check .`（line-length 120，规则 `E,F,I,W`）+ `python -m compileall -q src test` |
| git | 主干 `main`，波次分支 `feature/<change>` |
| 提交身份 | `chenghan7113029 <chenghan7113029@users.noreply.github.com>` |

## 知识线（本仓库唯一版本，替换手册里的飞书蒸馏）

> 本仓库**没有可蒸馏的机器人或知识库账号**，知识蒸馏一律**人工咨询**：
>
> 1. **采集入口只有两类**：① 向人咨询的答复（成员不得直接问用户，`agent_teams_send_message`
>    报 captain 转交，表单式一次问清）；② 仓库内一手材料（`docs/mrd/`、`docs/design/`、
>    `config/*.yaml`、`openspec/specs/`、现有代码与测试，**只读**）。目录约定以
>    `config/knowledge/README.md` 为真源。
> 2. **禁止**：自动抓取、凭库内容猜「已有 vs 新」、把推断写成确定。
> 3. **置信度口径**：人工明确答复 = 确定；一手材料原文 = 确定；推断 = 假设；**无来源不入库**
>    （进 `config/knowledge/known_unknowns.yaml`）。
> 4. **1 小时无答复** → 标未解决 + 记入 `docs/improvements/IMPROVEMENTS.md`。

---

## 成员

| name | role | model | reasoning_effort | 说明 |
| --- | --- | --- | --- | --- |
| `product-manager` | product manager | DeepSeek-V4.1-Flash | high | T1（case 牵引 + 拆功能 + 需求澄清 + 提案 + spec）与 T7（闭环两端同一人）；可写 `docs/`、change 目录 proposal/specs/case-teardown、`docs/cases/<case>/annotations.md` |
| `knowledge-architect` | knowledge architect | DeepSeek-V4.1-Flash | high | K1（知识缺口识别 + 分层 + schema + 升降级/退役规则），写 `knowledge-delta` 与 `config/knowledge/_design.md`，**不填知识内容** |
| `architect` | solution architect | DeepSeek-V4-Pro | high | T2（功能方案 + 拆任务），写 `design.md` + `tasks.md`；C 节消费 knowledge-design |
| `knowledge-engineer` | knowledge engineer | DeepSeek-V4.1-Flash | low | K2（知识采集/结构化落库），**只采集不发明** |
| `engineer` | implementer | DeepSeek-V4.1-Flash | high | T3，写 `src/` + `test/`（TDD 单测）并勾选 `tasks.md` |
| `qa` | qa engineer | DeepSeek-V4.1-Flash | low | T4（`test/qa/` 测试设计）+ K3（知识 case 回归盲验）+ T5（测试执行 + 报告） |
| `reviewer` | reviewer | DeepSeek-V4-Pro | high | T6，只产出 findings（含知识/能力去重） |
| `integrator` | integrator | DeepSeek-V4.1-Flash | low | T8，归档、修 `Purpose`、知识入库放行、`feature/<change>` 合并回 `main` |

> **模型 + effort 分级（省 token，只留两档）**：
>
> **模型**
> - `DeepSeek-V4-Pro`（贵，仅 2 个）：`architect`（技术方案/边界判断，方案错则全返工）、
>   `reviewer`（白盒评审/准出判断，漏拦则缺陷进主干）。
> - `DeepSeek-V4.1-Flash`（便宜，其余 6 个）：product-manager、knowledge-architect、
>   knowledge-engineer、engineer、qa、integrator。
>
> **effort**
> - `high`（5 个）：product-manager、knowledge-architect、architect、engineer、reviewer
>   —— 判断与写作质量敏感。
> - `low`（3 个）：`knowledge-engineer`（成本在人工咨询与文件读写，不在推理）、
>   `qa`（用例设计与执行模式化程度高）、`integrator`（归档/合流步骤确定）。
>
> **模型名只是 name**：本表 `model` 列写的是 registry 里的 `name`，**建成员用的真实 id 一律由
> `python scripts/agent_team_models.py --json` 解析**，不要把 id 写死在计划里；
> `list_subagent_models` 不是成员模型权威来源（只显示子集，会漏模型）。
>
> **captain** 不在成员表（由会话本身承担），其模型与 effort 随会话；如需再降，在会话层切换。
>
> 调优纪律：**单点升降，不整体回退**。若 T1 提案或 K1 分层下滑 → 该角色升回 Pro；
> 若 K3 盲验或 case 复现核对开始漏判 → `qa` 的 effort 升回 high。降级只认实测证据，不认感觉。

`executionPrompt` 不再内联写死，改为按角色拼装（完整定义见 [`docs/agent-team/roles/`](../roles/)）：

```text
executionPrompt = [ roles/_shared.md 内容 ] + "\n\n" + [ roles/<角色>.md 内容 ]
```

`_shared.md` 是通用纪律（不手改 specs、知识不可发明、附证据、走 feature 分支、环境约束…），
每个角色的 `.md` 是专属 SOP（身份/工作流/产出契约/完成定义/边界/失败定义）。

每个成员的 `executionPrompt` 末尾再追一段**可直接复制的提交身份片段**：

```text
所有 git commit 必须用下面这行（逐字复制，不要改写姓名/邮箱）：
git -c user.name='chenghan7113029' -c user.email='chenghan7113029@users.noreply.github.com' commit -m "<msg>"
提交后自检：git log -1 --format='%an <%ae>' —— 机器只认 <> 里的邮箱，
'chenghan7113029@users.noreply.github.com' 以外一律视为违规（姓名变体不触发 pre-receive 但违反契约）。
```

---

## 任务

> **任务字段的存在形态**：`requirements` / `implementation` / `verification` / `review` / `repair` /
> `integration` 六种 kind 承载 objective + acceptance（`implementation` / `repair` 另需
> inScope + verify）；其余任务都是 `work`，**不承载契约字段**，其 objective / acceptance /
> verify / inScope / outOfScope 一并写进 `description`（本文件即为 description 的正文）。
> 所以下面每段两种形态通用：建任务时按 kind 把字段搬进 `create_task` 或 `description`。
>
> **inScope 写法（`plan.yaml` 的 S1/S3 会拦）**：inScope 必须**逐条是文件路径**（有扩展名、
> 不得是裸目录），新增文件在路径末尾标 `（待新建）`；**目录只能写进 `outOfScope`**。
> 下面每段给的是所有权边界与示例，建计划时按 `design.md` 的影响面文件清单展开成逐文件——
> 把目录写进 inScope 会笼住别人的文件，是这套流程复发最多的越权来源。

### 建任务的三条硬规矩（2026-11-10 复核收口）

1. **数字基线一律写成「起跑时实测值」，禁止写死绝对数字**：acceptance 里凡出现测试/lint/覆盖率的
   绝对数字（「307 passed」「覆盖率 82%」），必须改写成「不低于**起跑时实测值**（起跑实测：
   `<建任务时跑一遍填进来>`）」。写死的数字会随代码增长而必然过期，后续 `repair` 为了凑数字
   只能改测试或直接死锁——过期的不是实现，是契约。
2. **`work` 类任务没有契约可 amend，所以建之前就要保证字段够用**：`work` 任务启动后不可再编辑，
   `amend_task` 只对质量 kind 生效。因此建 `work` 任务前，必须把该角色的「完成定义 / 失败定义」
   （`roles/<角色>.md`）逐条落进 `description`，写清"什么算完成、什么算失败"，不要指望事后补救。
3. **依赖只从下游加，不给上游加依赖**：`edit_plan` 追加依赖时会做 inScope 重叠校验，对已经串行
   执行的任务也会误报重叠、甚至造环。需要串行时，把依赖加在**下游**任务上（`下游 depends on 上游`）；
   两个任务 inScope 有重叠时，显式串行并在此处注明原因，不要试图用依赖把上游"钉住"。

### T1 — case 牵引 + 拆解（功能）+ 需求澄清 + 切分与变更提案（kind: `requirements`）

- **assignee**: `product-manager`
- **dependencies**: 无
- **objective**: 牵引完善 `<case>` 的**业务事实**（原始问题/背景/结论/ground-truth，**不问知识细节**），
  沿本仓库分析链（提问 / 取数 / 计算 / 结论 / 呈现，见 `templates/case-teardown.md`）逐环拆
  **功能**差距，澄清需求（有实质歧义时经 captain 一次性问清），再切出 `<change>` 的范围，
  产出 `case-teardown.md` + `proposal.md` + specs delta，不写代码、不碰知识细节。
- **acceptance**:
  1. `case-teardown.md` 按 `docs/agent-team/templates/case-teardown.md`：业务事实补齐（或显式标
     partial）；每条**功能**差距有环锚点（指回某一环）；「产品现状」**可证伪**（指得到
     `openspec/specs/<capability>/spec.md` 的具体 Requirement，或 `src/<模块>/<文件>.py:<行>`）；
     「用到的知识」列留空给 K1，PM 不填。
  1b. 牵引补全的业务事实已回填 `docs/cases/<case>/annotations.md`（标注区：逐环 + ground-truth +
     结论编号），**不写 `traces.yaml`、不手抄 trace 数字**。
  2. 不产 knowledge-delta；遇到"疑似知识缺口"只在 case-teardown 标「待 K1 确认」，不自己蒸馏、
     不自己判知识/功能。
  3. 需求澄清：用 grillme 思路收敛目标（追问出可验证边界，而非发散出新需求）；有实质歧义时先产出
     澄清清单并经 captain 转交；未澄清的歧义在 proposal 的「假设/开放问题」显式记录，不静默脑补。
  4. `proposal.md` 含 `## Why`（≥50 字）、`## What Changes`、`## Capabilities`（New/Modified 至少其一）、
     `## 成功标准`（可观测可验证）、`## Case 复现锚点`（声明本波让 case 的哪一环/哪条结论从 X→Y）、
     `## 失败标准 / 反目标`、`## Impact`。
  5. 每条需求标注 MRD 锚点（`<mrd-anchors>` 之一）或 case 环锚点；`docs/mrd/mrd-v1.md` 仍是骨架时，
     改挂 `docs/mrd/product-overview.md` 的章节号（如 §5.1.2）并在 proposal 写明映射关系。
  6. delta 规格使用 `## ADDED Requirements` / `## MODIFIED Requirements`，行为用 `SHALL` 描述，
     每个 Requirement 至少一个 `#### Scenario`（WHEN/THEN）。
  7. 明确列出本波**不做**什么（out of scope），避免后续范围蔓延。
- **verify**:
  - `openspec.cmd validate <change> --strict`
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('openspec/changes/<change>/case-teardown.md').exists() else 1)"`
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('docs/cases/<case>/annotations.md').exists() else 1)"`
- **inScope**: `openspec/changes/<change>/proposal.md（待新建）`,
  `openspec/changes/<change>/specs/<capability>/spec.md（待新建）`,
  `openspec/changes/<change>/case-teardown.md（待新建）`, `docs/cases/<case>/annotations.md（待新建）`
- **outOfScope**: `openspec/specs/`, `src/`, `test/`, `config/knowledge/`,
  `docs/cases/<case>/traces.yaml`（溯源区归 QA，PM 只读）

### K1 — 知识缺口识别 + 架构设计（kind: `work`）

- **assignee**: `knowledge-architect`
- **dependencies**: T1
- **objective**: 读 T1 的 `case-teardown.md` + `docs/cases/<case>/annotations.md` + 仓库内一手材料，
  识别出 case 用到的知识（口径/规则/判例/映射），逐条判断知识库已有 vs 新（`config/knowledge/` 现存
  但无条目、无分层定义：首波知识全部判「新」并写明依据）；对新缺口牵引知识细节（经 captain 一次性
  问清，不得直接问用户）；产出 `knowledge-delta.md`，再落成知识分层设计
  （`config/knowledge/_design.md`：分层 + 准入 + schema + 升降级/退役规则）。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① `knowledge-delta.md` 每条含 知识条目 / 支撑 case 哪一环 / 性质 / 已有 vs 新 / 证据
    （人工答复原文，或 `文件:行`）；② 每条新知识需求有归属层；③ 每层有语义 + 准入标准 +
    schema（含 `source` / `confidence` / `owner` / 强度 / 频次 / 生命周期字段）；④ 升降级/退役规则
    明确；⑤ 与代码边界画清（确定性知识可写死进代码/配置 vs 隐性知识必须人确认/留接口）；
    ⑥ ≥1 被否的分层方案 + 理由；⑦ 采集入口只用「人工答复（经 captain 转交）+ 仓库内一手材料」两类，
    并写进设计。
  - 失败：缺口识别偷懒（漏缺口 / 已有当新）/ 把隐性知识设计成写死 / 层语义含糊 / 无退役机制 /
    schema 无来源字段 / 越界写知识内容 / 凭库内容猜已有 vs 新 / 自行抓取外部来源。
- **verify**:
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('openspec/changes/<change>/knowledge-delta.md').exists() else 1)"`
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('config/knowledge/_design.md').exists() else 1)"`
- **inScope**: `config/knowledge/_design.md（待新建）`（仅分层/schema/退役定义，不填条目内容）,
  `openspec/changes/<change>/knowledge-delta.md（待新建）`, `docs/cases/<case>/annotations.md（待新建）`
  （仅「用到的知识」列与「知识差距」段）
- **outOfScope**: `src/`, `openspec/specs/`, `test/`, `docs/cases/<case>/traces.yaml`（只读）

### T2 — 技术方案 + 任务拆解（kind: `work`）

- **assignee**: `architect`
- **dependencies**: T1, K1
- **objective**: 产出 `openspec/changes/<change>/design.md`，把 T1 的每条 Requirement 落成可执行技术
  方案（`src/` 下的模块/接口/数据结构），并按 `docs/agent-team/roles/architect.md` 的「Agent 架构
  专属思考清单」画清 LLM / 编排 / 知识 / 可信边界；C 节**消费 K1 的 knowledge-design**（只做实现，
  不自造分层、不改层语义）；再把 Decisions 拆成 `tasks.md`。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① 每条 Requirement 都能在 `design.md` 指到落地位置；② `## Agent 架构决策` 按 A–H 清单
    逐项给「决策/理由」或「本波不涉及/原因」，无留白，C 节只做知识层实现、未改层语义；
    ③ `tasks.md` 拆成可勾选、可验证步骤，每条能指到 design 决策，无「完成整个模块」这类不可验收
    条目；④ ≥1 个被否方案及否掉理由；⑤ 影响面给出**具体文件路径清单**（`src/service/…` 级别）；
    ⑥ 风险表：风险、触发条件、缓解措施、回滚方式（Agent 风险优先：幻觉、循环、成本、上下文膨胀）；
    ⑦ 人工 CP2：`design.md` 经项目负责人确认后 T3 才启动（captain 派发 T3 前核对）。
  - 失败：A–H 有留白 / 把确定性计算交给 LLM / 未设计可信保证 / 影响面含糊 / 无被否方案 /
    自造知识分层 / 违反 `docs/agent-team/ENV.md`。
- **verify**:
  - `openspec.cmd validate <change> --strict`
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('openspec/changes/<change>/design.md').exists() and pathlib.Path('openspec/changes/<change>/tasks.md').exists() else 1)"`
- **inScope**: `openspec/changes/<change>/design.md（待新建）`, `openspec/changes/<change>/tasks.md（待新建）`
- **outOfScope**: `openspec/specs/`, `src/`, `test/`, `config/knowledge/`

### K2 — 知识采集 / 结构化落库（kind: `work`）

- **assignee**: `knowledge-engineer`
- **dependencies**: K1
- **objective**: 按 K1 的 `knowledge-delta` + `config/knowledge/_design.md` 的分层与 schema，从 `<case>` +
  仓库内一手材料 + 人工答复**采集、结构化**知识落进 `<knowledge-root>` 的 `<layer>/*.yaml`。每条带
  来源/置信度/owner/强度/频次/生命周期；采不到的记「已知未知」，不脑补。**无发明权，只有采集/标注/接入权**。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① 每条知识有 `source`（人工答复原文出处，或 `文件:行`）、`confidence`（确定/假设/未知）、
    `owner`；② case 回归自检：每条知识放回 `<case>` 能复现结论，或显式降置信度并写清不能复现原因；
    ③ `known_unknowns.yaml` 如实记录（缺口 + 影响面 + 待谁确认）；1 小时无答复标未解决 + 记
    `docs/improvements/IMPROVEMENTS.md`；④ 落库位置与 K1 分层一致，无越层；⑤ 无来源知识为零。
  - 失败：无来源入库 / 把假设标确定 / 把未确认口径写进库 / 发明知识 / 越层落库 / 自行抓取外部来源。
- **verify**:
  - `python scripts/check_knowledge_source.py`（无来源知识=0；改掉一条 `source` 应 exit 非 0，可证伪）
  - `python -c "import pathlib,sys; d=pathlib.Path('config/knowledge'); ok=any(p.is_file() and p.suffix in {'.yaml','.yml'} and p.name!='known_unknowns.yaml' for p in d.rglob('*')); sys.exit(0 if ok else 1)"`（至少落了一条知识条目 yaml，不是模板/已知未知文件）
- **inScope**: `config/knowledge/<layer>/<条目名>.yaml（待新建）`（按 `_design.md` 分层逐文件列）,
  `config/knowledge/known_unknowns.yaml`（待新建或改动）
- **outOfScope**: `src/`, `openspec/specs/`, `test/`, `docs/cases/`（只读）

### T3 — 代码实现（kind: `implementation`）

- **assignee**: `engineer`
- **dependencies**: T2
- **objective**: 按 architect 产出的 `design.md` 与 `tasks.md` 实现代码并逐条勾选（不自拆任务、
  不新增任务）。
- **acceptance**:
  1. `tasks.md` 全部勾选，且 `openspec.cmd instructions apply --change <change> --json` 报告无剩余任务。
  2. `<test-cmd>` 全绿，新增测试覆盖 T1 的每个 Scenario；测试数量不低于**起跑时实测值**
     （起跑实测：`<建任务时跑一遍填进来>`）。
  3. `<lint-cmd>` 与 `python -m compileall -q src test` 通过。
  4. 未修改 `openspec/specs/`、`design.md`、`test/qa/`；未引入未登记依赖（新依赖先登记
     `docs/agent-team/ENV.md` 再进代码）。
- **verify**:
  - `<test-cmd>`
  - `<lint-cmd>`
  - `python -m compileall -q src test`
  - `openspec.cmd instructions apply --change <change> --json`
- **inScope**: `src/<子包>/<模块>.py`（本波每个改动文件逐条列；新增文件标 `（待新建）`）,
  `test/<子包>/test_<模块>.py`（同上）, `config/app.yaml`（仅当 design 影响面含运行配置时）,
  `pyproject.toml`（仅当新增已登记依赖时）, `openspec/changes/<change>/tasks.md（待新建）`
  （仅勾选 `[x]`，不改任务定义）
- **outOfScope**: `openspec/specs/`, `openspec/changes/<change>/design.md`, `test/qa/`, `config/knowledge/`

### T4 — QA 测试设计（kind: `work`）

- **assignee**: `qa`
- **dependencies**: T2（与 T3 实现并行，盲测设计）
- **objective**: 从 specs delta + proposal 成功/失败标准 + `design.md` 独立设计补充用例，落到
  `test/qa/`；**不读 engineer 的实现与 `test/`**（盲测，避免被实现带偏）。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① `test/qa/` 覆盖 spec 每个 `#### Scenario`（WHEN/THEN 断言）；② 每条 proposal「成功标准」
    → 可执行验收，每条「失败标准/反目标」→ 证伪/阻断用例；③ 含负向/边界/对抗用例（空输入、越界、
    篡改、依赖缺失）；④ 用例是可执行 pytest、可溯源到锚点（测试节点 id 能指回 Scenario）；⑤ 未读
    engineer 实现（盲测）；⑥ 文件放 `test/qa/<包名>/test_*.py`，不写进 `test/`。
  - 失败：测试从实现派生（没盲测）/ 覆盖遗漏 / 只写 happy path / 用例不可执行 / 越界写 `test/`。
- **verify**:
  - `python -m pytest -q test/qa`（QA 用例自身可收集、可运行）
- **inScope**: `test/qa/<包名>/test_<能力>.py（待新建）`（本波新增的 QA 用例逐文件列）
- **outOfScope**: `src/`, `test/`, `openspec/specs/`, `openspec/changes/<change>/design.md`（执行后不改）、
  `config/knowledge/`

### K3 — 知识验证（case 回归盲验）（kind: `work`）

- **assignee**: `qa`
- **dependencies**: K2, T1
- **objective**: 拿 `<case>` + K2 采集的知识做**盲验**（不读 K2 的采集过程）：把每条知识放回
  `<case>`，能否复现 case 结论；产出知识验证报告。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① 每条知识逐条过 case 回归：复现 → 通过；不能复现 → 显式标注"降置信度/退回 K2"；
    ② 盲验：不读 K2 采集过程，只拿 case + 知识；③ 报告列出通过 / 降置信度 / 退回，各有 case 证据
    （命令 + 退出码 + 关键输出，或 `文件:行`）；④ 无来源、无 case 可验的知识判定为"自 high 知识"，
    退回 K2；⑤ 知识层复现结论 append 进 `docs/cases/<case>/traces.yaml`（`layer: knowledge`，
    一条一记录），证据与报告一致（能引用的一律不转述）。
  - 失败：读了 K2 采集过程再"验"（假盲验）/ 结论无证据 / 与 K2 同一个人的判断（利益冲突）/
    手写「复现进度」表 / trace 与报告证据对不上。
- **verify**:
  - `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('openspec/changes/<change>/knowledge-verification.md').exists() else 1)"`
  - `python -c "import pathlib,sys,yaml; p=pathlib.Path('docs/cases/<case>/traces.yaml'); rows=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else []; sys.exit(0 if isinstance(rows,list) and any(isinstance(r,dict) and r.get('layer')=='knowledge' for r in rows) else 1)"`
- **inScope**: `openspec/changes/<change>/knowledge-verification.md（待新建）`,
  `docs/cases/<case>/traces.yaml（待新建）`（只 append `layer: knowledge` 记录）
- **outOfScope**: `src/`, `config/knowledge/`（执行后不改）, `test/qa/`, `openspec/specs/`

### T5 — QA 测试执行 + 报告（kind: `verification`）

- **assignee**: `qa`
- **dependencies**: T3, T4
- **objective**: 跑 `test/` + `test/qa/` 全量，逐条核对 proposal 成功/失败标准，按
  `docs/agent-team/templates/verification-report.md` 的 **9 章节**产出 `verification.md`（第 9 章节做
  case 复现核对并 append trace）；失败写结构化 finding。
- **acceptance**:
  1. 全量 `<test-cmd>` 结果如实记录（`test/` 与 `test/qa/` 分列，写明命令与 deselect 数——
     本机默认 deselect 32 个 `akshare_legacy`）。
  2. T3 每条 acceptance 对应报告一行（命令 / 退出码 / 关键输出 / 结论）+ proposal 成功/失败标准逐条核对。
  3. 失败 → 结构化 finding（id / severity / problem / requiredFix / 位置），requiredFix 可执行，
     禁止「测试失败请修复」废话。
  4. 含负向/边界用例表；未覆盖项如实列；失败项标注是否阻塞归档。
  5. **第 9 章节：case 复现核对落 trace**——对照 proposal「Case 复现锚点」逐条核对，本波每条
     结论/环的复现结论 append 一条记录进 `docs/cases/<case>/traces.yaml`（字段见
     `docs/cases/_template-traces.yaml`）；本仓库没有独立运行产物目录、也没有查询 id，
     `evidence` 一律写「命令 + 退出码 + 关键输出」或「`文件:行` / 测试节点 id」；
     **不手写「复现进度」表**（由 traces.yaml 派生）。
- **verify**:
  - `<test-cmd>`
  - `openspec.cmd validate <change> --strict`
- **inScope**: `openspec/changes/<change>/verification.md（待新建）`,
  `docs/cases/<case>/traces.yaml（待新建）`（只 append 溯源记录）
- **outOfScope**: `src/`, `test/`, `test/qa/`（执行后不改）, `openspec/changes/<change>/design.md`,
  `openspec/specs/`

### T6 — 交付评审（kind: `review`，`reviewedTaskId` = T3）

- **assignee**: `reviewer`
- **dependencies**: T3, T5, K3
- **objective**: 白盒代码评审——通读本波 diff，按 `docs/agent-team/templates/review-checklist.md` 逐条
  审查（A 通用 / B Agent 特有 / C 分流 / D 越权），产出 verdict + findings 并按 type/severity 分流。
- **acceptance**:
  1. 实际通读本波全部 diff（`git diff main...feature/<change>`），不是只看报告。
  2. 清单 A/B 逐项审查，无留白（发现 + 依据 / 未发现 + 依据）。
  3. **去重审查**：diff 新增字面量全仓 grep（命中 ≥2 处 = 疑似知识硬编码，要指到 `src/` 或
     `config/` 的具体位置）；新增函数 vs 现有 helper 语义比对（疑似能力重复）。
  4. 越权检查：`openspec/specs/` 未被手改；engineer 未偷改 `test/qa/`；未新增未登记依赖
     （对照 `docs/agent-team/ENV.md`）；知识没被写进代码（`config/knowledge/` 才是知识真源）。
  5. findings 分流按清单 C 表：`bug` 的 `blocker`/`high` → `needs_revision`；
     `knowledge-abstraction`（代码里同一知识硬编码多处、**值一致**）/`capability-abstraction` →
     `medium` → `pass` 保留 findings；
     **同一知识在 `config/knowledge/*.yaml` 里值冲突 → `pass` + captain 同波建 K2 整改任务**；
     `knowledge-abstraction`（代码里两种实现值冲突）→ `blocker`/`high` → `needs_revision`。
  6. verdict：`pass` / `needs_revision` / `reject`（blocking findings 的 requiredFix 可执行）。
  7. verdict + 全部 findings（含 type）落 `openspec/changes/<change>/review.md`（防丢失，供 T7/integrator 读）。
  8. verdict 必须含两项开放条件：① `tasks.md` 是否全完成（未完成的逐条列）；② 声称的行为是否在
     **生产路径**（`src/apps/` CLI、`src/controller/` API）可达，不可达写明是能力缺口还是缺陷。
- **verify**: 无（`review` kind 由 verdict 承载准出；逐条结论与命令证据写进 `review.md` 的 §E 结构）
- **inScope**: `openspec/changes/<change>/review.md（待新建）`（只读被评审产物；结论只写这一个文件）
- **outOfScope**: 修改任何被评审产物（`src/`、`test/`、`test/qa/`、`design.md`、`openspec/specs/`、
  `config/knowledge/`）

### T7 — 改进点 + 知识需求回流 + MRD 演进（kind: `work`）

- **assignee**: `product-manager`
- **dependencies**: T5, T6, K3（T8 归档依赖 T7，故 T7 先于 T8 执行）
- **objective**: 从 `verification.md` §6 未覆盖项、`review.md` 的非阻塞 findings（medium/low）、
  K3 退回的知识提取改进点；**按 finding type 分流**（`knowledge-abstraction` → 知识需求，
  `capability-abstraction` → 抽象共享能力改进点），追加 `IMPROVEMENTS.md`，并给
  `docs/mrd/mrd-v{N+1}.md` 演进建议稿。
- **完成定义 / 失败定义（建 `work` 任务时必须逐条进 description）**：
  - 完成：① 每条改进点含 ID、来源证据（可指到具体行 / finding id）、影响面、建议变更名
    （kebab-case）、优先级、分流结论；② `knowledge-abstraction` 转成知识需求条目（进下一波
    knowledge delta）、`capability-abstraction` 转成"抽象共享能力"改进点；③ 分流遵循准入三条
    （有证据、影响面清晰、可切成独立 change），不满足的标 `P2 观察`；④ MRD 演进稿以 **diff 形式**
    书写，保留旧锚点编号；⑤ 建议变更名不与现有 change / 已归档 change 重名。
  - 失败：无证据的改进点 / 只追加不分类 / 改写旧锚点编号 / 建议变更名与现存重名 /
    越界蒸馏知识（只记需求，不蒸馏）。
- **verify**:
  - `openspec.cmd list`（确认建议 change 名无冲突）
  - `python -c "import pathlib,sys; f=sorted(pathlib.Path('docs/mrd').glob('mrd-v*.md')); sys.exit(0 if f and f[-1].name != 'mrd-v1.md' else 1)"`（演进稿已落新版本文件）
- **inScope**: `docs/improvements/IMPROVEMENTS.md`, `docs/mrd/mrd-v{N+1}.md（待新建）`
- **outOfScope**: `src/`, `openspec/specs/`, `config/knowledge/`

### T8 — 归档 + 知识入库 + 合并回 main（kind: `integration`）

- **assignee**: `integrator`
- **dependencies**: T5, T6, T7, K3（等改进点与知识需求落盘、知识盲验通过后，再归档并合并回 main）
- **objective**: 归档 `<change>` 并合并 delta 规格进主规格、修掉 `Purpose` 占位、确认知识盲验通过后
  放行知识入库，然后把 `feature/<change>` 合并回 `main`（唯一发布口）。
- **acceptance**:
  1. `tasks.md` 全勾选、`verification.md` 存在、`review.md` 的 verdict 为 `pass`、K3 知识盲验通过
     （无退回未处理）——四者齐备才允许归档与知识入库（`openspec.cmd archive --yes` 不会替你拦未完成任务）。
  2. 归档后变更位于 `openspec/changes/archive/<date>-<change>/`，`verification.md` 随行。
  3. `openspec/specs/<capability>/spec.md` 的 `Purpose` 不再含 `TBD` 且不少于 50 字符
     （这两条都会让 `validate --specs` 判 failed）。
  4. **收口闸门全绿（归档前跑）**：`python scripts/agent_team_plan.py check`、
     `python scripts/check_knowledge_source.py`、`openspec.cmd validate --specs --strict`、
     `openspec.cmd doctor`。闸门报的 warning 允许带进收口，但必须在收口报告里点名它是什么、
     为什么不阻塞。
     已知基线：`validate --specs --strict` 当前就不通过（多个 capability 的 `Purpose` 仍是占位句）。
     起波前必须决定「先起清理类 change / Owner 显式豁免」，选豁免就写进收口报告 —— **不许放宽 acceptance**。
  5. acceptance 分三段：**发布步骤 / 闸门清单 / 闸门不成立时的合法动作**（停下 + 落边界报告
     `T8-closure-report.md` + 报 captain，且**不构成任务失败**）。
  6. 在 `feature/<change>` 分支上提交（信息引用 `<change>`），然后 `git checkout main` +
     `git merge --no-ff feature/<change>`，合并后 main 历史一致、工作树干净。
- **verify**:
  - `python scripts/agent_team_plan.py check`
  - `python scripts/check_knowledge_source.py`
  - `openspec.cmd validate --specs --strict`
  - `openspec.cmd doctor`
  - `openspec.cmd list`（结果中不应再有 `<change>`）
  - `git branch --show-current`（合并后应回到 `main`）与 `git status --short`（应干净）
- **inScope**: `openspec/specs/<capability>/spec.md`（**只由 `openspec.cmd archive` 写入，不手改**）;
  归档与合并是 git / CLI 动作（`openspec/changes/` → `archive/<date>-<change>/`、`feature/<change>` → `main`），
  不产生手写文件
- **outOfScope**: `config/knowledge/`（知识条目由 K2 写入，integrator 只放行不写入）, `src/`

---

## 起波检查表（captain 自查）

> **先跑闸门，人只判剩下的。** 能机械判定的检查在三个脚本里，不要靠人眼：
>
> - `python scripts/agent_team_models.py --json`（成员模型 name → 真实 id，不手工翻译裸名）
> - `python scripts/agent_team_preflight.py`（起波前置：工具/口径/依赖就绪，退出码 0 才起波）
> - `python scripts/agent_team_plan.py check`（计划机检：成员与模型一致、11 任务编制与 kind/负责人、
>   DAG 无环与关键边、review 指向、work 类完成/失败定义、inScope、acceptance 无写死数字、知识线 kind、
>   case/MRD 存在、分支与提交身份）
>
> 三个脚本是本仓库 `scripts/` 的资产；命令不存在或直接报错，说明脚本尚未落地/未就绪，
> 起波前先补齐修好，**不许跳过机检**。
> 闸门红了先查历史缺陷映射、再决定是改计划还是改契约，**不许改脚本放宽检查**——放宽一次，
> 后面每一波都不再有人看这一项。

- [ ] **第 0 步 · 三个脚本都跑过**：`python scripts/agent_team_models.py --json`、
      `python scripts/agent_team_preflight.py`、`python scripts/agent_team_plan.py check` 退出码为 0
- [ ] **建任务用渲染不手抄**：计划骨架用
      `python scripts/agent_team_plan.py init --change <change> --case <case>` 生成、填完再 `check`；
      建任务时用 `python scripts/agent_team_plan.py render <ID> --json` 取参数粘进 `create_task`
      （依赖里的 `T*/K*` 换成真实 id）；脚本未提供 render 时按本文件对应段落逐字段填。
      手抄是本项目最高频的静默错误来源：字段错位不会报错，只会在派发后表现为「成员做的事和 finding 无关」
- [ ] `<mrd>` 存在且锚点编号真实可查（脚本只验文件存在，验不了编号）；`docs/mrd/mrd-v1.md` 仍是骨架时，
      锚点改挂 `docs/mrd/product-overview.md` 的章节号并在 proposal 写明映射
- [ ] `<case>` 在 `docs/cases/<case>/` 下有 `annotations.md` 且带 ground-truth 标注
      （`采纳 / 存疑 / 不采纳`，**只能由业务方标**）；没有 case 不许起波
- [ ] `src/`、`test/`、`test/qa/`、`config/knowledge/`（现存）、`<test-cmd>`、`<lint-cmd>` 都按仓库
      实际情况核对过（不是猜的目录名）
- [ ] 11 个任务都填了 assignee 与 dependencies，DAG 无环：K1←T1、T2←T1+K1、K2←K1、T3←T2、T4←T2、
      K3←K2+T1、T5←T3+T4、T6←T3+T5+K3、T7←T5+T6+K3、T8←T5+T6+T7+K3；T4 与 T3 并行
- [ ] `T6` 的 `reviewedTaskId` 指向 T3（`review` kind 必须挂在一个 implementation/repair 任务上）
- [ ] 每个 `implementation` / `repair` 任务都有 `inScope` 与 `verify`；`requirements` / `verification` /
      `review` / `integration` 任务有 objective + acceptance
- [ ] K2 的 verify 是 `python scripts/check_knowledge_source.py`（无来源知识=0 的可执行校验，
      不是 grep 关键词）
- [ ] `test/qa/` 与 `test/` 分离：engineer 不碰 `test/qa/`，QA 不碰 `test/`
- [ ] 知识线已按本文件「知识线」段落地：采集入口只有「人工答复（经 captain 转交）+ 仓库一手材料」，
      无抓取、无凭库猜、无来源不入库
- [ ] `approval="required"`，等人工 CP1 再放行

**以下需要人判断**（脚本给不了的东西：语义正确性、判据有没有能力变红、运行时动作）：

- [ ] **本机环境坑已核对**：`python` 3.14.3（**命令名就是 `python`，不存在带 3 后缀的写法**）；`python -m pytest -q` 默认
      deselect 32 个 `akshare_legacy` 用例（全量收集 864 个）；`-m` 会覆盖 `pyproject.toml` 的 addopts，
      要排联网用例必须写 `-m "not network and not akshare_legacy"`；`matplotlib` **未安装**
      （verify 与产物里不得凭空引用图表）；openspec 一律 `openspec.cmd`（ExecutionPolicy 禁 `.ps1`）
- [ ] **T8 归档闸门基线与豁免已定**：`openspec.cmd validate --specs --strict` 当前不通过
      （多个 capability 的 `Purpose` 仍是占位句）。起波前决定「先起清理类 change」还是
      「Owner 显式豁免」；选豁免必须写进 `T8-closure-report.md`，**不许为了让闸门变绿放宽 acceptance**
- [ ] **每条 `verify` 命令都有能力变红**：字段名/正则写错时「查出 0 条」与「真实为 0」退出码相同，
      等于什么都没证明；至少配一个已知「应命中」样本或断言计数 > 0
- [ ] 每条 `inScope` 已在 `plan.yaml` 里落成**逐文件路径**（`check` 的 S1）、engineer 不含 `test/qa/` 且
      qa 不含 `src/` 与 `test/`（S3），并已对齐 `design.md` 的双轨文件所有权（归属对错脚本验不了，只能人判）
- [ ] **调度期守则已知会成员**：任务 `in_progress` + 成员 `idle/ready` + 无产物无报错 = attempt 已断，
      15 分钟内 `reassign_task`，不许干等
- [ ] **自动派生的 `repair` / `review` 契约已逐字段复核**：不只改 `inScope`——objective / acceptance
      不得残留上一轮的旧目标，与 finding 对不上就 `amend_task` 全字段重写；自动生成的 `inScope`
      若是裸名/少一层路径，`changedPaths ⊆ inScope` 会让任务死锁
- [ ] **自动 repair 的 acceptance 只保留触发 repair 的 blocker/high finding**：medium/low 不触发
      repair（reviewer 规则），应交 T7 而非塞进 repair acceptance
- [ ] **判定绑定已在计划期预留**：凡可能出现「评审 needs_revision → repair」的链条，起波时就把
      「最终字节复验」建成挂在 repair 之后、并被 T7/T8 依赖的任务，不要等 verdict 失效了再补
- [ ] **每条 acceptance/verify 已过「判据三问」**：①拿已知违规样本跑过、确认它会红；②红的理由就是
      它要防的那件事（不是 `except` 兜底、不是命中了注释里的禁令原文）；③它绿的时候是真绿
      （长度/计数类判据复用仓内既有函数，禁手算）
- [ ] **证据由命令输出产生**：报告里的数字、`文件:行`、commit sha 一律复制自输出；自检链必须含
      `git rev-parse HEAD`
- [ ] **commit 纪律**：禁 `-a` / `-am`，只 `git add <具体路径>`；**有成员在跑
      `openspec.cmd archive` / `merge` / `reset` 时，除执行者外禁一切 git 写**
- [ ] **看门狗定时巡检已建立**：起波后立刻 `schedule_create`（`target=this_session`，
      `FREQ=MINUTELY;INTERVAL=10`，`COUNT` 绑定波次时长），巡检判三条卡死（`in_progress` + 成员 `idle`、
      无新提交且工作树干净、超 40 分钟无产出），命中即 `reassign_task` 或 captain takeover；
      **波次结束时删除该定时任务**
- [ ] **大 payload 已自检 JSON**：`update_task` / `amend_task` 的字符串值内不得出现未转义双引号、
      不得嵌 `.replace(...)` 这类代码表达式，命令与路径一律纯字面量
- [ ] **归档后 verdict 失效属预期**：`openspec.cmd archive` 删除活动 change 目录 → T5/T6 的字节绑定
      必然失效（verdict covers a revision that no longer exists）。判定以 `T8-closure-report.md` +
      归档后重跑的测试 / `validate --specs --strict` 为准，不为此重开复验
- [ ] **review 的 verdict 必含两项开放条件**：①任务清单是否全完成（未完成的逐条列）；
      ②声称的行为是否在**生产路径**可达（不可达的写明是能力缺口还是缺陷）
- [ ] **T8 类契约已给「闸门不成立时」的合法出口**：禁止同时出现「必须 archive/merge/push」与
      「缺一不得归档」而不给出口，否则守规矩的成员只能失败或被迫硬归档
- [ ] **收口同时读 `tasks.md` 与 proposal 成功标准**：`tasks.md` 记「有没有做」，成功标准记
      「做成了没有」；未达成照实写，不得降级为「部分达成」
