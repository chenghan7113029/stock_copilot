# 工程目录结构

> 本文是**目录索引**：agent 靠目录名找东西、不靠猜。
> **约束性规则的唯一真源是 [`docs/dev/engineering-conventions.md`](../dev/engineering-conventions.md)**（架构、分层、依赖方向、编码约束、LLM 规范）；本文与其冲突时，以 engineering-conventions 为准。
>
> 决策记录：本项目为**已有成熟代码**的项目，agent team 初始化时选择「**保持现状**」——不按模板重构目录，只把角色 instruction 里的路径对齐到本项目实际结构（见 `docs/agent-team/PLAYBOOK.md`）。

## 全貌

```
stock_copilot/
├── src/                        # Python 源码（扁平多包，setuptools packages.find where=src）
│   ├── apps/                   # CLI / 交互入口
│   ├── controller/             # API 接口层
│   ├── service/                # 业务服务
│   ├── data_provider/          # 外部数据源适配（tushare / baostock / akshare）
│   ├── dao/                    # 数据库访问（SQLAlchemy）
│   └── common/                 # 通用模块（配置、日志、工具）
├── test/                       # engineer 的 TDD 单测（标准 spec 行为）
│   ├── apps/ controller/ service/ data_provider/ dao/ common/
│   ├── e2e/                    # 端到端
│   ├── fixtures/               # 测试夹具数据
│   ├── scripts/                # 测试辅助脚本
│   └── qa/                     # QA 的补充测试（验收 / 负向 / 边界 / 对抗，盲测设计）
├── config/                     # 运行配置（YAML）
│   └── knowledge/              # 知识层（口径 / 规则 / 判例 / 映射；_design.md 定分层与 schema，
│                               #   <layer>/*.yaml 存条目，known_unknowns.yaml 记已知未知）
├── scripts/                    # shell / 运维 / 数据初始化脚本
│   └── agent_team_*.py         # 团队自检脚本（模型解析 / 环境预检 / 计划断言 / 知识来源检查）
├── docs/
│   ├── agent-team/             # 团队编制与流程（roles / PLAYBOOK / templates / plans / models.yaml / ENV）
│   ├── architecture/           # 本文件
│   ├── mrd/                    # 需求基线（product-overview + features + mrd-v{N}.md）
│   ├── design/                 # 专项设计文档（含 references/：外部参考分析报告与调研索引）
│   ├── dev/                    # 工程约定（唯一真源）
│   ├── cases/                  # 现实锚点（<case-id>/annotations.md 标注 + traces.yaml 溯源）
│   └── improvements/           # 改进点台账
├── openspec/                   # 规格（specs/ 现行能力 + changes/ 变更 + config.yaml）
├── .agents/skills/             # agent 指令 skill（SKILL.md，项目级）
├── .dsh/skills/                # DSH 侧 skill（openspec-* 等）
├── log/                        # 运行日志
├── reports/                    # 分析报告产出（gitignore）
├── data/                       # 本地数据与夹具（gitignore 中的库文件）
├── ref/                        # 外部参考资料（gitignore，只读，禁止 import）
│   ├── <repo>/                 # 第三方 clone 快照（只读）
│   └── research/<topic>/<slug>/ # 调研资料区（只增不改；索引在 docs/design/references/）
├── pyproject.toml              # 包元数据 + 依赖 + pytest/ruff 配置
├── conftest.py                 # 根级 pytest 配置
└── AGENTS.md                   # AI 协作入口
```

## 每层放什么

### `src/`（源码，扁平多包）

`pyproject.toml` 中 `[tool.setuptools.packages.find] where = ["src"]`，因此 `src/` 下每个目录是一个**顶层包**，不是单一包的子包。

| 子包 | 放什么 |
| --- | --- |
| `apps/` | CLI / 交互入口（命令行子命令的装配） |
| `controller/` | API 接口层（请求编排、参数校验） |
| `service/` | 业务服务（技术面 / 价值面 / 报告 / 决策编排） |
| `data_provider/` | 外部数据源适配器；换数据源只换适配器 |
| `dao/` | 数据库访问（SQLAlchemy 模型与仓储） |
| `common/` | 配置加载、日志、通用工具 |

**依赖方向**：`apps → controller → service → data_provider / dao → common`（详见 `docs/dev/engineering-conventions.md`）。

### `test/` 与 `test/qa/`（两套测试，互不越界）

- `test/` = engineer 的 TDD 单测，覆盖 spec 的标准行为（SHALL / Scenario）。
- `test/qa/` = QA 的补充测试：验收、负向、边界、对抗用例；**盲测设计**（写用例时只读 specs delta + proposal 成功/失败标准 + `design.md`，不读 engineer 实现）。
- 所有权边界：engineer 不得改 `test/qa/`；QA 不得改 `test/` 与 `src/`。

### `scripts/`（脚本）

shell / 运维 / 数据初始化脚本。**CLI 入口进 `pyproject.toml` 的 `[project.scripts]`**，不放这里。

### `config/knowledge/`（知识层）

「系统现在知道什么」的权威源，与代码生命周期不同：**代码随 change 归档，知识跨波存活**（持续升降级 / 退役）。

- `_design.md`：分层 + 每层语义 + 准入标准 + 元数据 schema + 升降级 / 退役规则（knowledge-architect 写）
- `<layer>/*.yaml`：知识条目，每条带 来源 / 置信度 / owner / 强度 / 频次 / 生命周期（knowledge-engineer 写）
- `known_unknowns.yaml`：采不到的知识点（知识负债，显式记录，不脑补）

**采集入口只有两个**：人工答复（经 captain 转交）+ 仓库内一手材料。本机没有可蒸馏的飞书机器人 / 飞书号，禁止自动抓取。机检：`python scripts/check_knowledge_source.py`。

### 两类 "skill" 的区分（别混）

| 类型 | 位置 | 是什么 |
| --- | --- | --- |
| **agent 指令 skill** | `.agents/skills/<name>/SKILL.md` | 给 LLM agent 看的「怎么做」说明书 |
| **业务能力代码** | `src/<module>/` | 指令里描述的能力的实际实现（python 函数/模块） |

## 关键约定

1. **代码只进 `src/<module>/`**，不散在根目录；新增顶层包须同步 `pyproject.toml` 与 `docs/dev/engineering-conventions.md`。
2. **shell 脚本只进 `scripts/`**，CLI 入口进 `[project.scripts]`。
3. **测试分两套**：`test/`（engineer）与 `test/qa/`（QA），互不越界。
4. **确定性 vs LLM 边界**：取数、校验、聚合用确定性代码；LLM 只在 service 的叙事/决策环节调用，且受 `docs/agent-engineering-quality.md` 三层防御约束。
5. **规格在 `openspec/`**（`openspec/specs/` 只能由 `openspec archive` 写入），需求在 `docs/mrd/`，流程资产在 `docs/agent-team/`。
6. **`ref/` 只读**：第三方 clone 仅作查阅，需要逻辑时 COPY 进 `src/` 并留「来源 + 原路径 + commit + 许可证」头注释，禁止 `import`；`ref/research/` 只放调研资料，**索引写进 `docs/design/references/`**（`ref/` 不进 git，索引才是唯一凭据）。
