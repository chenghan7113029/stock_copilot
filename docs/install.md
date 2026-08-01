# stock_copilot 新设备安装方案

> 从 **Git 克隆** 到 **能跑 sync / report** 的完整装机步骤  
> 适用：把工程部署到另一台 Windows / macOS / Linux 电脑  
> 最后更新：2026-08-01

日常怎么用报告，见 [user-guide.md](user-guide.md)。本文只讲**装机与迁移**。

---

## 0. 你需要准备什么

| 项 | 是否必须 | 说明 |
|----|----------|------|
| Git | 必须 | 克隆仓库 |
| Python **3.10+** | 必须 | Windows 建议装 [python.org](https://www.python.org/downloads/) 正式版，并勾选 “Add to PATH” |
| 网络 | 必须 | 克隆、装依赖、`sync` 拉行情都需要 |
| GitHub 账号权限 | 视仓库而定 | 若仓库是私有的，新设备要能 `git clone` / 有 SSH key |
| Tushare Token | 强烈推荐 | 价值面质量更好；可从旧设备复制 |
| 旧设备上的 `config/app.yaml`、`data/*.db` | 可选 | 想保留历史缓存时再拷贝，见 §6 |

**不需要**事先准备：`ref/` 参考仓库（仅开发对照用）、Web 服务、Docker。

---

## 1. 克隆仓库

在目标设备上选一个工作目录，例如：

**Windows（PowerShell / CMD）：**

```cmd
cd /d D:\workspace
git clone https://github.com/chenghan7113029/stock_copilot.git
cd stock_copilot
```

**macOS / Linux：**

```bash
mkdir -p ~/workspace && cd ~/workspace
git clone https://github.com/chenghan7113029/stock_copilot.git
cd stock_copilot
```

若你用的是 SSH：

```bash
git clone git@github.com:chenghan7113029/stock_copilot.git
cd stock_copilot
```

确认当前在仓库根目录（应能看到 `pyproject.toml`、`src/`、`config/`）。

```bash
git status
git log -1 --oneline
```

---

## 2. 安装 Python 依赖（推荐虚拟环境）

### 2.1 Windows（推荐）

```cmd
REM 确认版本（不要用微软商店占位 python）
py --version

REM 创建并激活虚拟环境
py -m venv .venv
.venv\Scripts\activate.bat

REM CMD 若用 PowerShell：
REM .venv\Scripts\Activate.ps1
REM 若报执行策略错误，可执行：
REM Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

python -m pip install -U pip
pip install -e ".[dev]"
```

**不想用 venv 时（最快）：**

```cmd
py -m pip install -e ".[dev]"
```

之后所有命令用 `py -m apps.cli ...`。

### 2.2 macOS / Linux

```bash
python3 --version   # 需 >= 3.10

# 方式 A：脚本一键（创建 venv + 装依赖）
bash scripts/setup-dev-env.sh
source .venv/bin/activate

# 方式 B：手动
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

### 2.3 验证安装

在仓库根目录：

```bash
# Windows: py -m pytest -q -m "not network"
# macOS/Linux: pytest -q -m "not network"
pytest -q -m "not network"
```

离线单测应大部分通过。若 `pytest` 找不到命令，用：

```bash
python -m pytest -q -m "not network"
```

---

## 3. 配置（app.yaml + Token）

### 3.1 生成配置文件

任选其一：

```bash
# 手动复制
cp config/app.example.yaml config/app.yaml
# Windows CMD:
# copy config\app.example.yaml config\app.yaml
```

或**什么都不做**：第一次跑 `sync` / CLI 时，程序会自动从 example 复制。

`config/app.yaml` 已在 `.gitignore` 中，**不会**被提交。

常看股票列表 `config/watchlist.yaml` **会入库**（便于多设备同步）。克隆后可直接 `watchlist list`，或按需 `watchlist add` 后 commit。

### 3.2 启用 Tushare（强烈推荐）

1. 打开 [tushare.pro](https://tushare.pro) 注册，复制个人 Token（积分建议 ≥2000，财报表权限才够用）
2. 编辑 `config/app.yaml`，在 `data_sources.enabled` 中启用：

```yaml
data_sources:
  enabled:
    - name: akshare
      priority: 1
    - name: baostock
      priority: 2
    - name: tushare
      priority: 3
      # token 也可不写在这里，改用环境变量
```

3. **推荐用环境变量存 Token**（避免文件拷来拷去泄露）：

**Windows CMD：**

```cmd
setx TUSHARE_TOKEN "你的token"
```

（`setx` 对新开的终端生效；当前窗口可再执行 `set TUSHARE_TOKEN=你的token`）

**PowerShell：**

```powershell
[System.Environment]::SetEnvironmentVariable("TUSHARE_TOKEN", "你的token", "User")
$env:TUSHARE_TOKEN = "你的token"
```

**macOS / Linux（写入 `~/.bashrc` 或 `~/.zshrc`）：**

```bash
export TUSHARE_TOKEN="你的token"
```

### 3.3 可选：LLM（目前仅部分能力用到）

若后续启用 LLM 相关命令，可在 `app.yaml` 配置 `llm:` 段，或设置环境变量 `LLM_API_KEY`。纯 `sync` / `report tech|value|dual` **不依赖** LLM。

---

## 4. 冒烟验收（装完必跑）

用一只熟悉的股票验证整条链路（以茅台为例）：

**Windows：**

```cmd
py -m apps.cli sync 600519
py -m apps.cli report tech 600519
py -m apps.cli report value 600519
py -m apps.cli report dual 600519
```

或一键试跑：

```cmd
scripts\run_trial.cmd --code 600519
```

**macOS / Linux：**

```bash
python -m apps.cli sync 600519
python -m apps.cli report tech 600519
python -m apps.cli report value 600519
python -m apps.cli report dual 600519
```

**成功标志：**

- `sync` 打印类似 `value snapshot OK | K线 …行 OK`
- 三份 report 有可读文本输出（非立刻报「请先 sync」）
- 本地出现 `data/stock_copilot.db`（若目录不存在会自动创建）

报告可存盘：

```bash
python -m apps.cli report value 600519 -o reports/600519_value.txt
```

---

## 5. 可选组件

### 5.1 `ref/` 外部参考仓库（仅开发对照，运行不需要）

日常使用 **不必** clone。只有你要对照 `valueinvest` / FinanceToolkit 源码时才装：

```bash
mkdir -p ref
git clone https://github.com/JerBouma/FinanceToolkit ref/FinanceToolkit
git clone https://github.com/wangzhe3224/valueinvest ref/valueinvest
git clone https://github.com/ZhuLinsen/daily_stock_analysis ref/daily_stock_analysis
```

**禁止** `import ref.*`；业务只走 `src/`。

### 5.2 Cursor / Cloud Agent（可选）

若新设备用 Cursor 继续开发：

- 打开本仓库文件夹
- Cloud Agent 说明见 [dev/cloud-agent.md](dev/cloud-agent.md)
- Agent 构建真源：[.cursor/CLOUD_AGENT.md](../.cursor/CLOUD_AGENT.md)

运行时分析**不依赖** Cursor；CLI 单独可用。

---

## 6. 从旧设备迁移数据（可选）

Git **不会**带上你的本地库和密钥。若希望新设备「接着用」旧数据：

| 旧设备路径 | 是否拷贝 | 说明 |
|------------|----------|------|
| `config/app.yaml` | 建议 | 含数据源开关；**Token 更建议改用环境变量** |
| `config/watchlist.yaml` | 走 Git | 常看列表已入库，`git pull` 即可；勿与验证样本 yaml 混淆 |
| `data/stock_copilot.db` | 可选 | 已 sync 的快照与 K 线；拷过去可少拉几天网 |
| `data/stock_copilot.db-wal` / `-shm` | 若存在一并拷 | SQLite WAL 附属文件，否则可能不完整 |
| `reports/` | 可选 | 历史报告文本 |
| `.venv/` | **不要拷** | 在新设备重新 `pip install` |
| `ref/` | 一般不拷 | 体积大，需要再 clone |

拷贝后在新设备再跑一次 `report` 验证；若 schema 有升级，首次 `sync` / CLI 会走 `ensure_sqlite_schema` 补列。

**更干净的做法：** 只迁配置与 Token，在新设备重新 `sync` 关心的股票。

---

## 7. 日常更新代码

```bash
cd stock_copilot
git pull

# 激活 venv 后
pip install -e ".[dev]"   # 依赖变更时再执行
pytest -q -m "not network"
```

---

## 8. 安装检查清单（打印对照）

- [ ] `git clone` 成功，在仓库根目录
- [ ] `python` / `py` ≥ 3.10
- [ ] `pip install -e ".[dev]"` 成功
- [ ] `pytest -q -m "not network"` 基本通过
- [ ] 已有 `config/app.yaml`（手动或自动生成）
- [ ] （推荐）`TUSHARE_TOKEN` 已配置且 `tushare` 已在 `enabled` 中
- [ ] `sync 600519` 成功
- [ ] `report tech/value/dual` 能出报告

---

## 9. 常见问题

| 现象 | 处理 |
|------|------|
| Windows `python` 无输出 | 改用 `py -m ...`；勿用微软商店占位解释器 |
| `ModuleNotFoundError: apps` | 未在仓库根执行，或未 `pip install -e .` |
| `report` 提示先 sync | 新库为空，先对该代码 `sync` |
| Tushare 无数据 / 权限错误 | 检查 Token、积分、是否在 `enabled` 中启用 |
| `git pull` 后测试挂了 | 再跑 `pip install -e ".[dev]"`；看 CHANGE / OpenSpec 是否有破坏性变更 |
| 想卸干净 | 删目录即可；另清环境变量 `TUSHARE_TOKEN` |

---

## 10. 一页纸最短路径（复制即用）

**Windows：**

```cmd
cd /d D:\workspace
git clone https://github.com/chenghan7113029/stock_copilot.git
cd stock_copilot
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -U pip
pip install -e ".[dev]"
copy config\app.example.yaml config\app.yaml
REM 编辑 app.yaml 启用 tushare，并设置 TUSHARE_TOKEN
py -m apps.cli sync 600519
py -m apps.cli report value 600519
```

**macOS / Linux：**

```bash
cd ~/workspace
git clone https://github.com/chenghan7113029/stock_copilot.git
cd stock_copilot
bash scripts/setup-dev-env.sh
source .venv/bin/activate
cp config/app.example.yaml config/app.yaml
# 编辑 app.yaml 启用 tushare，并 export TUSHARE_TOKEN=...
python -m apps.cli sync 600519
python -m apps.cli report value 600519
```

装完后的日常用法 → [user-guide.md](user-guide.md)。
