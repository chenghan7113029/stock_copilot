# 脚本目录

存放项目运维、开发辅助脚本（Shell / Bash / Python）。

## 约定

- 脚本应可独立运行，或在 README 中说明依赖
- 敏感参数从环境变量或 `config/app.yaml` 读取，勿硬编码
- 文件名使用 kebab-case（Shell）或 snake_case（Python），如 `fetch_value_data.py`

## 首次环境初始化

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -e .

# 2. 初始化配置文件（若 config/app.yaml 不存在）
# fetch_value_data.py 会自动从 app.example.yaml 复制，也可手动执行：
cp config/app.example.yaml config/app.yaml
```

## 脚本一览

| 脚本 | 语言 | 用途 |
|------|------|------|
| `setup-dev-env.sh` | Shell | 创建 venv、安装依赖（Linux/macOS） |
| `cloud_bootstrap.py` | Python | Cloud Agent / CI 环境 bootstrap（config、seed DB、ref clone） |
| `export_seed_db.py` | Python | 从本地 DB 导出 Cloud seed fixture |
| `fetch_value_data.py` | Python | 端到端数据采集：fetch → upsert → 读回摘要 |
| `trial_cli_workflow.py` | Python | CLI 全流程试运行：sync → 技术面报告 → 价值面报告 |

**Cloud Agent** 详见 [docs/dev/cloud-agent.md](../docs/dev/cloud-agent.md)；Agent 读 [.cursor/CLOUD_AGENT.md](../.cursor/CLOUD_AGENT.md)。

**CLI 全流程试运行**详见 [trial_cli_workflow.md](trial_cli_workflow.md)（Windows 请用 `scripts\run_trial.cmd`，勿用裸 `python`）。

## fetch_value_data.py 使用说明

### 采集样本股票清单（默认模式）

```bash
# 采集 config/value_data_validation_stocks.yaml 中全部样本（6 只）
python scripts/fetch_value_data.py
```

### 采集指定股票

```bash
python scripts/fetch_value_data.py --code 600519 --code 601398
```

### 输出示例

```
============================================================
  价值面数据采集任务开始
============================================================

  [600519] 贵州茅台
    字段覆盖: 18/42
    当前价:  1800.50
    EPS:     47.7600
    ROE:     33.50%
    缺失字段: ['ebitda', 'roic', ...] ...等N个

============================================================
  完成：成功 6 只，失败 0 只
============================================================
```

### 修改样本清单

编辑 `config/value_data_validation_stocks.yaml`，新增或删除 `stocks` 条目。
E2E 测试和本脚本都从该文件读取，是**单一真源**。

## Agent Teams 起队脚本

起队（建成员 / 建任务）前先跑下面三个；能机械判定的不进 prompt，也不靠人读文档核对。

| 脚本 | 干什么 | 何时跑 |
| --- | --- | --- |
| `agent_team_models.py` | 把 `docs/agent-team/models.yaml` 的模型 name 解析成本机真实 model id，并校验 effort | 起队建成员前 |
| `agent_team_preflight.py` | 实测本机「运行时 / CLI / 仓库」三类前置，退出码 0 才起队 | 起队前 |
| `check_knowledge_source.py` | 知识条目「无来源知识 = 0」机检（`confidence=确定` ⇒ 必须有 source） | K2 自查 / reviewer 判 B9 / 收口 |

### agent_team_models.py

```bash
python scripts/agent_team_models.py          # 人类可读表（name / role / 模型 name / id / effort / 来源）
python scripts/agent_team_models.py --json   # [{"name","role","provider","model","effort","resolved_id","source"}]
```

解析顺序：`$DSH_HOME/settings.yaml.imported` 里 `llm-pi-ai.providers.<provider>.models[]` 的 name/id 对
→ `$DSH_PROFILE_DIR/cordis.patch.yml` 的 `agent-default-model`（只有 provider/model，用于一致性校验，不是 name→id 映射）
→ 脚本内置的本机 app catalog 实测映射（`DeepSeek-V4.1-Flash → deepseek-flash`、`DeepSeek-V4-Pro → deepseek-v4-pro`）。

name 稳定、id 随环境变，所以 `models.yaml` 只写 name。**不要拿 `list_subagent_models` 当成员模型来源**
（它只列 coding_plan 子集，本机只有 deepseek-flash）。解析不出的 name 会打印候选并退出 1。
退出码：0 全部解析成功 / 1 有 name 解析不出、或 effort 越界（未知模型的 effort 只 warning 不校验）。

### agent_team_preflight.py

```bash
python scripts/agent_team_preflight.py
python scripts/agent_team_preflight.py --json
```

- 运行时：`python --version` ≥ 3.11、`python -m pytest --version`、`python -m ruff --version`、`import yaml`
- CLI：`openspec.cmd --version`（Windows 上裸 `openspec` 无法直接被 subprocess 调用，脚本会明说「须用 openspec.cmd」）
- 仓库：git 工作树成立、`git config user.email` 必须是 `chenghan7113029@users.noreply.github.com`、当前分支名、
  `git status --short`（脏只 warning，不阻塞）

只做本地探测：不连网络、不读任何 token / 凭据文件内容。
退出码：0 全部就绪 / 1 有需修项（openspec 不可用、git 身份不符、pytest/ruff/PyYAML 缺失）/ 2 不可用（python 太旧、不是 git 工作树）。

### check_knowledge_source.py

```bash
python scripts/check_knowledge_source.py                    # 默认扫 config/knowledge
python scripts/check_knowledge_source.py --root <dir> --json
```

条目形态（三种之一）：顶层 list、顶层 dict 的 `entries:` list、或顶层 dict 自带 `confidence`。
每条必填 `source / confidence / owner / strength / frequency / lifecycle`，`confidence ∈ {确定, 假设, 未知}`，
且 `confidence=确定` 必须有非空 `source`（其余置信度允许空 source）。缺字段、枚举越界、确定无来源 → error，
带 `文件:路径` 定位。空库（目录不存在或没有任何条目）不是错误。
退出码：0 无 error / 1 有 error。

### 共同纪律：写完必须注入缺陷确认它会红

这三个脚本的价值全在「红了才算检查」。改完各造一个反例跑一遍（坏 yaml / 不存在的模型 name / 摘掉 PATH 里的 openspec），
确认退出码真的变成 1（不是 0）；红不了就是假绿 —— 检查在跑、永远不报错，比没有检查更糟。
