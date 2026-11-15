# 环境事实（本机实测）

> 团队写 `verify` 命令前必读。**这里只记本机验证过的事实，不猜。**
> 更新时机：装/换依赖、改运行时、换机器后。某波需要新依赖，先在此登记再写进任务契约。
> 实测时间：**2026-11-14**（agent team v2：8 角色 / 11 任务，新增知识线 K1–K3）；上一版 2026-11-08（6 角色 / 8 任务）。实测机器：Windows 11 家庭版 中文版 10.0.26200。

## Agent Teams 成员模型（captain 起队前必读）

唯一真值源是 [`models.yaml`](models.yaml)（只写模型 **name**），成员的真实 model id 由脚本解析，**不手抄**：

```bash
python scripts/agent_team_models.py --json     # 角色 → name → 本机真实 id + effort
```

| 角色 | models.yaml 里的 name | 本机解析出的 id | effort |
| --- | --- | --- | --- |
| `architect`、`reviewer` | `DeepSeek-V4-Pro` | `deepseek-v4-pro` | high |
| `product-manager`、`knowledge-architect`、`engineer` | `DeepSeek-V4.1-Flash` | `deepseek-flash` | high |
| `knowledge-engineer`、`qa`、`integrator` | `DeepSeek-V4.1-Flash` | `deepseek-flash` | low |

实测要点（三条，都是踩过的坑）：

1. **`list_subagent_models` 不是成员模型权威来源**：本机它只列出 `deepseek-official/deepseek-flash`（`coding_plan` 子集），**漏掉 `deepseek-v4-pro`**。app 内置 catalog 实测含这两个 id（`DeepSeek-V4-Pro` / `DeepSeek-V4.1-Flash`），`deepseek-v4-pro` 的可用性在本机 catalog 成立，但**成员是否真能拿到需要首次起队验证**——若建成员时报 `UNKNOWN_MODEL`，回退方案是全员 flash + effort 分级，并把「pro 档未生效」如实记进本文件与当波记录。
2. **effort 取值受模型能力约束**：`deepseek-flash` 支持 `off / low / high / max`，**没有 `medium`**。因此本项目的 effort 只用 `high` 与 `low` 两档（原手册的 medium 一律落到 low）。
3. **registry 位置**：`$DSH_HOME/settings.yaml.imported`（本机只有 dsh-desktop 段，**没有** `llm-pi-ai.providers`）、`$DSH_PROFILE_DIR/cordis.patch.yml`（`agent-default-model` = deepseek-official / deepseek-flash / high）。脚本按「settings → cordis.patch → 内置实测映射」三级解析，解析不出来就 exit 1 并打印候选，**不许猜**。

## 起波前预检（captain 必跑）

```bash
python scripts/agent_team_models.py --json      # 成员模型解析（8 条都要有 id）
python scripts/agent_team_preflight.py          # 运行时 / CLI / 仓库身份：退出码 0 才起波
python scripts/agent_team_plan.py check         # 计划的 29 条断言：退出码 0 才起波
```

`agent_team_preflight.py` 的三段实测口径（**不含**原手册的 idata / lark-cli / git push——本项目不用）：

| 段 | 检查 | 本机实测 |
| --- | --- | --- |
| 运行时 | `python --version` ≥3.11、`python -m pytest --version`、`python -m ruff --version`、`import yaml` | ✔ Python 3.14.3 / pytest 9.0.3 / ruff 0.15.17 / PyYAML 6.0.3 |
| CLI | `openspec.cmd --version` | ✔ 1.16.1（**只能走 `.cmd` shim**，见下方第 4 条） |
| 仓库 | 在 work tree 内、`git config user.email`、当前分支、`git status --short` | ✔ 邮箱 `chenghan7113029@users.noreply.github.com`；分支 `main`；脏工作树只给 warning |

## 知识线（本项目：全部人工咨询）

- **没有任何可蒸馏的飞书机器人或飞书号**（2026-11-14 用户裁决）。禁止 `lark-cli` / 飞书机器人 / 自动抓取。
- 知识条目落 `config/knowledge/`：分层与 schema 由 K1 写进 `config/knowledge/_design.md`，条目由 K2 写在 `<layer>/*.yaml`，已知未知写 `known_unknowns.yaml`。
- 采集入口只有两个：**人工答复**（经 captain 转交，1 小时无答复即标「未解决」）与**仓库内一手材料**（`docs/mrd/`、`docs/design/`、`config/*.yaml`、`openspec/specs/`、现有代码与 `test/`）。
- 机检：`python scripts/check_knowledge_source.py`（无来源知识 = 0）。**`check_knowledge_schema.py` / `verify_traces.py` / `scan_prohibitions.py` 未安装**，因为它们依赖本仓库不存在的产物（知识 loader、`artifacts/` run 目录、idata `query_id`）。

## 运行时

| 项 | 事实 | 备注 |
| --- | --- | --- |
| OS / Shell | Windows 11（10.0.26200） | DSH 会话内 shell 为 `pwsh`（Windows 原生）与 MSYS2 `bash` |
| Python | **3.14.3** | `C:\Users\程晗\AppData\Local\Python\bin\python.exe`；⚠️ **Windows 上没有 `python3` 命令**，一律用 `python` |
| pytest | 9.0.3 | `python -m pytest -q` 可用；全量收集 **864** 个用例，默认 deselect **32** 个 `akshare_legacy` |
| ruff | 0.15.17 | `python -m ruff check .` 可用 |
| Node | v25.6.1 | 仅用于 openspec CLI（本项目的知识线已停用 lark-cli） |
| openspec CLI | 1.16.1 | `openspec doctor` → OpenSpec root: ok |

## Python 第三方包（实测）

| 包 | 状态 / 版本 |
| --- | --- |
| pandas | ✅ 3.0.2 |
| numpy | ✅ 2.4.2 |
| openpyxl | ✅ 3.1.5 |
| sqlalchemy | ✅ 2.0.50 |
| akshare | ✅ 1.18.54 |
| baostock | ✅ 0.9.20 |
| tushare | ✅ 1.4.29 |
| pyyaml | ✅ 6.0.3 |
| jsonschema | ✅ 4.26.0 |
| openai | ✅ 2.31.0 |
| matplotlib | ❌ **未安装**（需要图表时先登记再装，不要在 verify 里凭空用） |

## 命令与配置事实

1. **pytest 配置**（`pyproject.toml`）：`testpaths = ["test"]`、`pythonpath = ["src"]`、`addopts = --import-mode=importlib -m "not akshare_legacy"`。标记：`network`（需联网）、`akshare_legacy`（默认排除）。
   - 全量（默认）：`python -m pytest -q`
   - 离线（排除联网用例）：`python -m pytest -q -m "not network"`
   - QA 补充测试单独跑：`python -m pytest -q test/qa`
2. **静态检查**：`python -m ruff check .`（line-length 120，规则 `E,F,I,W`）；语法编译 `python -m compileall -q src test`。
3. **openspec 必须指明条目**：变更用 `openspec.cmd validate <change> --strict`，归档后用 `openspec.cmd validate --specs --strict`；裸跑 `openspec.cmd validate --strict` 在非交互终端会进入「选择条目」交互，脚本里会卡住。
4. **npm 全局 CLI 的 PowerShell 执行策略限制**：本机 `ExecutionPolicy` 禁止运行 `.ps1`，直接敲 `openspec` 会报「因为在此系统上禁止运行脚本」。**必须**写成 `openspec.cmd`（shim 在 `C:\Users\程晗\AppData\Roaming\npm\openspec.cmd`，已在 PATH 上）；脚本里可用 `& "$env:APPDATA\npm\openspec.cmd" <args>`。`python scripts/agent_team_plan.py check` 的 V3 断言会拦住忘写 `.cmd` 的 verify 命令。
5. **pytest 临时目录**：仓库内已有 `.pytest_cache` / `pytestbasetemp` / `.pytest-tmp` 等本地产物，已纳入 `.gitignore` 体系之外时不要提交；verify 命令不要依赖它们存在。
6. **git**：主分支 `main`；波次分支 `feature/<change>`。起波前 `git status --short` 必须干净（不允许把未提交改动混进波次）。提交身份 `chenghan7113029 <chenghan7113029@users.noreply.github.com>`（G4 按邮箱判定）。

## 团队自检脚本（本仓库已装 4 个）

| 脚本 | 用途 | 退出码 |
| --- | --- | --- |
| `python scripts/agent_team_models.py [--json]` | 角色 → name → 本机真实 model id + effort | 0 全解析 / 1 有解析失败 |
| `python scripts/agent_team_preflight.py` | 运行时 / CLI / 仓库身份预检 | 0 全就绪 / 1 需修 / 2 不可用 |
| `python scripts/agent_team_plan.py check` | 计划的 29 条起跑断言（编制 / DAG / 契约 / inScope / verify / 预算 / case / git） | 0 全绿 / 1 有 error |
| `python scripts/agent_team_plan.py closeout` | 收口 R0–R5 | 同上 |
| `python scripts/check_knowledge_source.py` | 无来源知识 = 0 | 0 无 error / 1 有 error |

**未安装**（原手册有、本仓库没有对应产物）：`verify_traces.py`（无 `artifacts/` run 目录与 query_id）、`check_knowledge_schema.py`（无知识 loader）、`scan_prohibitions.py`（无「禁令 ↔ 符号」约定）。**不许把它们写进任何闸门或 verify**。

## 选型约束（据此推导，别背道而驰）

1. **数据读写**：项目已依赖 pandas，直接用 pandas / openpyxl；不需要为「少一个依赖」绕路写 csv 解析。
2. **联网用例**：数据源相关用例可能标 `network`；本地 / 无网环境验证时用 `-m "not network"`，并在 `verification.md` 里写明用了哪个命令。
3. **新增依赖**：任何新依赖必须先登记到本文件（含版本与安装方式），再出现在任务契约与代码里。禁止在 verify 命令里突然出现未登记的依赖。
4. **AI / LLM 调用**：`openai` SDK 已装；涉及真实调用的用例默认不进 CI 门禁，用 mock 或 `network` 标记隔离。

## 已知基线问题（起波前必读）

> 以下是初始化时实测到的**现存**问题，不是这套流程引入的。它们会直接撞上流程闸门，先看清楚再起波。

1. **`openspec validate --specs --strict` 当前不通过**：实测 `23 passed, 76 failed (99 items)`，退出码 1。主因 69 个 capability 的 `## Purpose` 仍是占位句（archive 写入的默认句 / `TBD`），另有若干 Requirement 超过 500 字符的 strict 警告。
   → 影响 **T8 归档闸门**（`validate --specs --strict` 必须通过）。处置二选一：先起一个清理类变更（如 `fix-spec-purpose-placeholders`）把 Purpose 补成真人写的结论；或由 Owner 显式豁免并记录在 `verification.md` / tasks 里。**不要**为了让闸门变绿去放宽 acceptance。
2. **`-m` 会覆盖 addopts 的 `-m`**：`python -m pytest -q -m "not network"` 会把 `akshare_legacy` 用例重新收集进来（addopts 里的 `-m "not akshare_legacy"` 被覆盖）。要同时排除写 `-m "not network and not akshare_legacy"`。
3. **工作树**：初始化完成时工作树仍有未提交改动（`.cursor/` 若干、`.agents/`、`.claude/`、`.codex/`、`.dsh/` 等），起波前须先清理或确认，避免混进 `feature/<change>` 分支。

## 外部网络与资料获取（实测）

| 通道 | 实测结果 | 用途 |
| --- | --- | --- |
| `web_search` | ✅ 可用（Firecrawl 云端检索） | 找候选实现、查口径 |
| `read_page` | ✅ 可用（云端渲染抓取，能取 GitHub 页面正文） | 抓 README / 文档 / 源码页正文 |
| `web_fetch` 直连 | ❌ 失败（`raw.githubusercontent.com` → `fetch failed`） | 不要用它抓外网 |
| `git ls-remote` / `fetch` / `pull`（GitHub） | ❌ 失败（exit 128，`Connection was reset`；无代理环境变量） | **不能靠 `git clone` 入库** |

由此推导的规则：

1. **调研入库不走 clone**：用 `read_page` 抓正文，存成 markdown 到 `ref/research/<topic>/<slug>/`，`README.md` 里记来源 URL + 抓取日期（拿不到 commit SHA 时以日期为准）。
2. **优先查本地 `ref/`**：已有 15 个 clone（279 MB），能覆盖大部分对比需求，不依赖外网。
3. **起波分支**：`git pull` 不可用时跳过（见 PLAYBOOK §6），基于本地 `main` 切分支，并在起波记录里注明「未拉取远端」。
4. **合并回 main 是本地操作**：`git merge --no-ff feature/<change>` 不受网络影响；推送远端由 Owner 自行处理。

## 会话与权限

- 本次初始化会话的文件策略为 `danger-full-access`；成员会话的权限由 captain 起波时决定，不在本文件声明。
- 沙箱 / 审批策略若被收紧（例如 `workspace-write`），命令只允许写工作区内路径；届时先跑一次确认，不要假设。
