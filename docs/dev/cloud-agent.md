# Cloud Agent 移动开发指南

> **读者：项目 Owner（你）。** Cloud Agent 读 [.cursor/CLOUD_AGENT.md](../.cursor/CLOUD_AGENT.md)。

在手机上通过 Cursor Cloud Agent 继续开发时，Agent **看不到**你电脑上的 `config/app.yaml`、完整 SQLite、`.venv`、`ref/` clone。本指南说明如何一次性配置，以及开任务时怎么说清楚。

---

## 一次性 Dashboard 配置

1. 打开 [cursor.com/dashboard/cloud-agents](https://cursor.com/dashboard/cloud-agents)
2. 连接 GitHub 仓库：`chenghan7113029/stock_copilot`
3. 环境：使用仓库内 [`.cursor/environment.json`](../.cursor/environment.json)（`install` 会自动 `pip install` + bootstrap）
4. **Secrets**（Repository 或 Team 级）：

| Secret 名 | 必填 | 用途 |
|-----------|------|------|
| `TUSHARE_TOKEN` | 可选 | 启用 Tushare 财报 merge、network 测试 |

5. （可选）首次 install + `pytest` 成功后 **Save Snapshot**，将 snapshot ID 写入 `.cursor/environment.json` 加速冷启动

---

## 非 git 文件对照表

| 你本地有什么 | Cloud Agent 怎么获得 |
|-------------|---------------------|
| `.venv` + pip 包 | `install` 自动 `pip install -e ".[dev]"` |
| `config/app.yaml` | bootstrap 从 `app.example.yaml` 生成；token 走 Secret |
| `data/stock_copilot.db` | Git 中的 **seed fixture** 复制 → 需要时可 `sync` 刷新 |
| `ref/*` 三仓库 | bootstrap 浅 clone |
| `reports/*` | 运行时生成，无需同步 |

---

## 移动场景工作流

1. Push 代码到 GitHub
2. 手机/网页开 Cloud Agent，使用下方**开口模板**
3. Agent 改代码 → `pytest` → 可选联网 sync / trial
4. Review PR / merge

---

## 给 Cloud Agent 的开口模板

开新任务时复制粘贴（替换尖括号内容）：

```text
请按 .cursor/CLOUD_AGENT.md 执行会话自检（cloud_bootstrap + pytest），然后完成：<你的任务>。

约束：数值由代码计算；ref/ 只读不 import；验证用 pytest。
数据：默认用 seed DB 离线验证；如需联网 sync 请先说明并确认 TUSHARE_TOKEN 可用。
```

示例任务描述：

- `实现 openspec/changes/value-bank-e2e 的 tasks.md 第 1-3 项`
- `修复 report value 对 601398 的 offline 报错，用 seed DB 验证`
- `补充 test/data_provider 对 prior period 的单元测试`

---

## 维护 seed 数据库

seed fixture 供 Cloud **离线**跑 `report tech/value`。本地更新后重新导出并 commit：

```powershell
# 确保本地 DB 已 sync 过目标股票
py scripts/fetch_value_data.py --code 600519 --code 601398 --code 601939

# 导出 fixture
py scripts/export_seed_db.py --codes 600519,601398,601939

git add data/fixtures/stock_copilot_seed.db
```

---

## 相关文件

| 文件 | 作用 |
|------|------|
| [`.cursor/environment.json`](../.cursor/environment.json) | Cloud install 钩子 |
| [`.cursor/CLOUD_AGENT.md`](../.cursor/CLOUD_AGENT.md) | Agent 构建/运行真源 |
| [`scripts/cloud_bootstrap.py`](../scripts/cloud_bootstrap.py) | 幂等 bootstrap |
| [`scripts/export_seed_db.py`](../scripts/export_seed_db.py) | 导出 seed fixture |
| [`AGENTS.md`](../AGENTS.md) | Agent 入口（含 Cloud 段） |
