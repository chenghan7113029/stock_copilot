# Cloud Agent 构建与运行真源

> **读者：Cursor Cloud Agent。** 人类操作见 [docs/dev/cloud-agent.md](../docs/dev/cloud-agent.md)。

你在 **Cursor Cloud VM（Ubuntu）** 上运行，**不是**用户的 Windows 本机。仓库由 Git checkout；非 git 资产由 `install` → `scripts/cloud_bootstrap.py` 补齐。

---

## 1. 会话启动（必须先做）

```bash
python scripts/cloud_bootstrap.py
pytest -q
```

可选：读取 `data/cloud-env.status.json` 了解 bootstrap 结果（gitignore，运行时生成）。

**不要**向用户索要本地 `app.yaml`、完整 DB 或 token 明文；token 应已在 Cursor Dashboard Secrets 中配置为 `TUSHARE_TOKEN`。

---

## 2. Install 后环境清单

| 路径 | 来源 | 说明 |
|------|------|------|
| `config/app.yaml` | bootstrap 从 `app.example.yaml` 复制 | 若存在 `TUSHARE_TOKEN` env，会自动启用 tushare（priority 3），**不写 token 进 yaml** |
| `data/stock_copilot.db` | seed fixture 复制或空库 | 默认仅含 **600519 / 601398 / 601939** 最小快照+K线，**非用户全量库** |
| `data/fixtures/stock_copilot_seed.db` | Git 提交 | 离线 report 的数据源 |
| `ref/*` | bootstrap 浅 clone | 只读参考，**禁止 import** |
| Python 包 | `pip install -e ".[dev]"` | 不依赖用户本地 `.venv` |
| `TUSHARE_TOKEN` | Cursor Secrets → 环境变量 | 变量名固定；值不可见 |

---

## 3. 不存在的资产（Never assume）

- 用户本地完整 SQLite、历史 `reports/`、本地 trial 产出
- 用户未 push 的未提交改动
- 用户 Windows 路径、`py` 启动器习惯（Cloud 上用 `python`）
- 「和本地一样」——Cloud 以 seed DB + bootstrap 为准，**不保证与用户本机 parity**

---

## 4. 标准命令

| 意图 | 命令 | 需网络 |
|------|------|--------|
| 环境自检 | `python scripts/cloud_bootstrap.py` | 否（ref clone 需网络，首次 install 已跑过） |
| 单元测试 | `pytest -q` | 否 |
| 离线价值面报告 | `python -m apps.cli report value --code 600519` | 否（需 seed DB） |
| 离线技术面报告 | `python -m apps.cli report tech --code 600519` | 否（需 seed DB） |
| 联网同步 | `python scripts/fetch_value_data.py --code 600519` | 是 |
| 单票 sync | `python -m apps.cli sync 600519` | 是 |
| 全流程 trial | `python scripts/trial_cli_workflow.py` | 是（含 sync） |

---

## 5. 用户口头指令 → Agent 动作

| 用户可能说 | Agent 应理解为 | 不应做 |
|-----------|---------------|--------|
| 「跑 trial / 全流程」 | 先 `pytest -q`，再 `trial_cli_workflow.py` | 不要假设 DB 已是最新 |
| 「看茅台估值」 | `report value --code 600519` | 不要 LLM 生成数值 |
| 「同步数据」 | `fetch_value_data.py` 或 `apps.cli sync` | 不要读用户本地 DB |
| 「参考 valueinvest」 | 读 `ref/valueinvest/` **只读**，改 `src/` | 禁止 `import ref.*` |
| 「配置好了 token」 | 检查 `TUSHARE_TOKEN`，必要时 `verify_tushare_access` | 不要要求用户粘贴 token |
| 「和本地一样」 | **不成立**；以 seed + bootstrap 为准 | 不要假设环境 parity |
| 「继续完善项目」 | 读 MRD / OpenSpec change，改 `src/`+`test/` | 不要改 `ref/` |

---

## 6. 工程硬约束

- 架构/目录：[docs/dev/engineering-conventions.md](../docs/dev/engineering-conventions.md)
- LLM 规范：[docs/agent-engineering-quality.md](../docs/agent-engineering-quality.md)
- **数值字段禁止 LLM 生成**；`ref/` 禁止 import；算法拷贝进 `src/` 并注明来源

---

## 7. 任务完成定义（Cloud）

- 代码改动 + `pytest -q` 通过
- 若涉及数据管道：说明验证用的是 **seed DB** 还是 **sync 后的 live DB**
- PR 描述写清验证命令；**不声称**「已在用户本地 Windows 验证」
