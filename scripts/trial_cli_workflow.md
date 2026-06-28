# CLI 全流程试运行指南

脚本对指定股票依次执行：

1. **sync** — 联网同步价值面快照 + 技术面 K 线
2. **report tech** — 离线技术面报告
3. **report value** — 离线价值面报告

默认三只 A 股：**600519 茅台**、**601398 工商银行**、**601939 建设银行**。

---

## Windows 用户必读（你遇到的情况）

### 现象：`python scripts/...` 没有任何输出，reports 也没有文件

在 Windows 上，`python` 经常是**微软商店的占位程序**，并不会真正运行脚本（静默失败）。

请改用下面任一方式（**不要用裸 `python`**）：

```powershell
# 方式 A：推荐，项目根目录 CMD
scripts\run_trial.cmd

# 方式 B：PowerShell（若提示无法运行脚本，见下方「执行策略」）
.\scripts\run_trial.ps1

# 方式 C：直接用 py 启动器
py scripts/trial_cli_workflow.py
```

成功启动后，**第一行**应立刻看到：

```
trial_cli_workflow: starting...
```

若连这行都没有，说明命令仍没真正跑到 Python，请检查是否误用了 `python`。

### 现象：`.venv\Scripts\activate` 找不到路径

说明**还没有创建虚拟环境**。虚拟环境是**可选的**，不创建也能跑：

```powershell
# 在项目根目录，用 py 安装依赖（只需一次）
py -m pip install -e ".[dev]"
```

然后：

```powershell
py scripts/trial_cli_workflow.py
```

若希望使用虚拟环境（可选）：

```powershell
# 1. 创建（只需一次）
py -m venv .venv

# 2. 激活 — CMD 用这个：
.venv\Scripts\activate.bat

# 2. 激活 — PowerShell 用这个：
.venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 运行
python scripts/trial_cli_workflow.py
```

> **PowerShell 无法运行 Activate.ps1？**  
> 以管理员执行一次：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`  
> 或改用 CMD + `activate.bat`，或直接用 `scripts\run_trial.cmd`（无需激活 venv）。

---

## 最简步骤（Windows，无 venv）

在 **项目根目录** `stock_copilot\` 打开 CMD，依次执行：

```cmd
py -m pip install -e ".[dev]"
scripts\run_trial.cmd
```

单只股票试跑（更快）：

```cmd
scripts\run_trial.cmd --code 600519
```

---

## 前置条件

| 项 | 说明 |
|----|------|
| Python | 3.10+，Windows 用 **`py`** 验证：`py --version` |
| 依赖 | `py -m pip install -e ".[dev]"` |
| 配置 | 首次运行自动从 `config/app.example.yaml` 生成 `config/app.yaml` |
| 网络 | sync 步骤需联网；单票约 1～2 分钟 |
| 输出 | `reports/trial/<时间戳>/`（已在 .gitignore） |

---

## 成功时的输出示例

```
trial_cli_workflow: starting...
trial_cli_workflow: loading config...

============================================================
  stock_copilot CLI trial workflow
============================================================
  stocks:     600519, 601398, 601939
  output-dir: D:\...\stock_copilot\reports\trial\20260628_153045
============================================================

============================================================
  [600519] 贵州茅台
============================================================
  [1/3] sync (online)...
        (may take 1-2 min per stock, please wait)
[sync] 600519 done: value snapshot OK | K线 60行 OK
  [2/3] report tech (offline)...
已保存至 ...\600519_tech.txt
  [3/3] report value (offline)...
已保存至 ...\600519_value.txt
  OK  reports -> 600519_tech.txt, 600519_value.txt

============================================================
  done: success=3, fail=0
  reports dir: D:\...\reports\trial\20260628_153045
============================================================
```

每只股票生成：

- `{代码}_tech.txt` — 技术面
- `{代码}_value.txt` — 价值面

---

## 常用参数

```cmd
REM 默认三只股
scripts\run_trial.cmd

REM 只跑茅台
scripts\run_trial.cmd --code 600519

REM 指定输出目录
scripts\run_trial.cmd --output-dir reports\my_trial

REM 已有缓存，跳过 sync 只重跑报告
scripts\run_trial.cmd --skip-sync

REM 盘中 sync 叠加实时价
scripts\run_trial.cmd --realtime
```

Linux / macOS：

```bash
py scripts/trial_cli_workflow.py          # 或 python3
py scripts/trial_cli_workflow.py --code 600519
```

---

## 分步手动 CLI（可选）

```cmd
set PYTHONPATH=src
py -m apps.cli sync 600519
py -m apps.cli report tech 600519 --output reports\600519_tech.txt
py -m apps.cli report value 600519 --output reports\600519_value.txt
```

已 `pip install -e .` 时可省略 `PYTHONPATH`。

---

## 常见问题

### Q: 命令行完全没反应、也没有 reports

- 不要用 `python`，改用 **`py`** 或 **`scripts\run_trial.cmd`**
- 确认在项目根目录执行（能看到 `scripts\` 文件夹）
- 运行 `py --version` 应显示 3.10+

### Q: sync 报错「数据拉取失败」

- 检查网络；非交易时段接口可能较慢，稍后重试
- AKShare 偶发告警可忽略，只要后续 `[sync] ... done` 出现即成功

### Q: report 报错「请先运行 sync」

- 去掉 `--skip-sync` 重新跑完整流程

### Q: 控制台中文乱码（如 `[run_trial] 浣跨敤...`）

**原因：** Windows CMD 默认 GBK，而 `.cmd` 若含中文注释/echo 且文件为 UTF-8，会被误解析（甚至报「不是内部或外部命令」）。

**已修复：** `run_trial.cmd` 改为纯英文 + 自动 `chcp 65001`；Python 侧也会设置 UTF-8。

请重新拉取代码后执行：

```cmd
scripts\run_trial.cmd --code 600519
```

若仍有乱码，在 CMD 先手动执行 `chcp 65001` 再运行。报告 `.txt` 始终为 UTF-8，用 VS Code 打开最稳妥。

### Q: 数据存在哪里？

`config/app.yaml` 中 `db.url`，默认 `data/stock_copilot.db`。

---

## 与 fetch_value_data.py 的区别

| 脚本 | 作用 |
|------|------|
| `fetch_value_data.py` | 批量 sync + 字段覆盖摘要 |
| `trial_cli_workflow.py` | sync + **技术面/价值面报告落盘** |

两者 sync 均调用 `apps.cli.run_sync`。
