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
