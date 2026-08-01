# stock_copilot 使用说明书

> 面向：**实际使用本工具分析 A 股的个人投资者**（非开发者文档）  
> 当前入口：**命令行（CLI）**；Web / Checklist / 情绪面等能力仍在规划中  
> 最后更新：2026-08-01

---

## 1. 这是什么、能做什么

**stock_copilot** 是个人股票投资助手。它不替你下单、不保证盈利，而是帮你：

1. **补齐信息面** — 同一只股票同时看**价值面**（公司值多少钱）和**技术面**（趋势与买点风险）
2. **降低片面判断** — 通过「红蓝对抗」把多空证据摆开，避免只听一边
3. **可追溯** — 报告里的数值由代码计算，不是 AI 随口编的数字

**一句话：** 先 `sync` 拉数据，再离线出报告；决策仍由你自己做。

### 1.1 当前已可用

| 能力 | 怎么用 |
|------|--------|
| 同步单票行情与财报快照 | `python -m apps.cli sync <代码>` |
| 技术面报告 | `python -m apps.cli report tech <代码>` |
| 价值面报告 | `python -m apps.cli report value <代码>` |
| 多维看板（一页汇总） | `python -m apps.cli report dashboard <代码>` |
| 红蓝证据分桶（多空清单） | `python -m apps.cli report dual <代码>` |
| 红蓝对抗叙事（多方/空方互驳） | Cursor 里让 Agent 做「红蓝对抗」（见 §6） |
| 一键试跑多只样本股 | `scripts/run_trial.cmd`（Windows） |

### 1.2 尚未交付（请勿期待）

情绪面量化、买入 Checklist、首开仓评估、Web 界面、自动复盘归因等仍在路线图中。详见 [mrd/roadmap-todo.md](mrd/roadmap-todo.md)。

> **说明：** CLI「多维看板」已可用（`report dashboard`）；其中情绪面 / Checklist 分区目前是「待建」占位，等对应功能落地后会自动替换。Web 版看板仍待建。

### 1.3 免责声明

- 本工具基于公开市场数据与公开估值方法，**仅供学习与决策参考**
- **不构成**投资建议；买卖后果自负
- 数据源可能延迟、缺字段或偶发失败；报告中的「警告 / 置信度」请认真阅读

---

## 2. 环境准备（首次安装）

**新电脑 / 另一台设备完整装机：** 请按 **[install.md](install.md)** 从 `git clone` 做起（含 venv、Token、验收与旧数据迁移）。

以下为简要版；细节与检查清单以 `install.md` 为准。

### 2.1 要求

| 项 | 说明 |
|----|------|
| 系统 | Windows / macOS / Linux |
| Python | **3.10+** |
| 网络 | `sync` 需要联网；`report` 可离线（需已 sync 过） |

### 2.2 安装依赖

在项目根目录 `stock_copilot/` 执行：

**Windows（推荐用 `py`，避免微软商店假 `python`）：**

```cmd
py -m pip install -e ".[dev]"
```

**macOS / Linux：**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2.3 配置文件

首次运行若缺少 `config/app.yaml`，程序会从 `config/app.example.yaml` **自动复制**一份。

建议你打开 `config/app.yaml` 按需修改：

| 配置项 | 作用 | 建议 |
|--------|------|------|
| `data_sources.enabled` | 用哪些数据源 | 默认 akshare + baostock 即可 |
| Tushare（可选） | 财报更全、历史 PE/PB、银行指标更准 | 注册 [tushare.pro](https://tushare.pro)，见 §2.4 |
| `db.url` | 本地数据库路径 | 默认 `data/stock_copilot.db`，一般不用改 |
| `logging.cli_progress` | CLI 是否打印进度 | `true` 方便观察 sync |

`config/app.yaml` **不会**提交到 Git，可放心写 Token。

### 2.4 启用 Tushare（强烈推荐）

没有 Tushare 也能跑（akshare + baostock），但价值面质量会差一截（尤其 FCF、净负债、历史估值分位、银行专项指标）。

**方式 A — 写进配置（二选一即可）：**

在 `config/app.yaml` 的 `data_sources.enabled` 中取消注释并填写：

```yaml
    - name: tushare
      priority: 3
      token: "你的token"
```

**方式 B — 环境变量（推荐，避免误提交）：**

```cmd
set TUSHARE_TOKEN=你的token
```

PowerShell：

```powershell
$env:TUSHARE_TOKEN = "你的token"
```

macOS / Linux：

```bash
export TUSHARE_TOKEN=你的token
```

同时需在 `enabled` 列表里启用 `tushare` 这一项（可只写 `name` + `priority`，token 走环境变量）。

---

## 3. 核心工作流（每天怎么用）

```text
sync（联网拉数） → report dashboard / tech / value / dual（离线读库出报告）
```

**原则：**

1. **先 sync，再 report** — 本地没缓存时，`report` 会报错提示你先同步
2. **sync 之后的报告可反复离线重跑** — 不费数据源额度
3. **盘中要贴近现价** — sync 时加 `--realtime`
4. **想先看全局再深入** — 用 `report dashboard` 一页汇总，再按需跑 tech/value/dual

### 3.1 最短路径（分析一只股票）

以贵州茅台 `600519` 为例（Windows CMD）：

```cmd
cd /d D:\workspace\stock_copilot

REM 1. 同步数据（约 1～2 分钟）
py -m apps.cli sync 600519

REM 2. 一页看板（价值 + 技术 + 红蓝证据条数摘要）
py -m apps.cli report dashboard 600519

REM 3. 需要时再深入单维度
py -m apps.cli report tech 600519
py -m apps.cli report value 600519
py -m apps.cli report dual 600519
```

macOS / Linux 把 `py -m` 换成 `python -m` 即可。

### 3.2 把报告存成文件

```cmd
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.txt
py -m apps.cli report tech 600519 -o reports/600519_tech.txt
py -m apps.cli report value 600519 -o reports/600519_value.txt
py -m apps.cli report dual 600519 -o reports/600519_dual.txt
```

`reports/` 目录默认不进 Git，适合本地留存。

### 3.3 一键试跑（推荐新手）

Windows：

```cmd
scripts\run_trial.cmd --code 600519
```

默认会跑茅台 / 工行 / 建行三只，报告写到 `reports/trial/<时间戳>/`。

更多参数见 [scripts/trial_cli_workflow.md](../scripts/trial_cli_workflow.md)。

---

## 4. 命令参考

统一入口：

```text
python -m apps.cli <子命令> ...
```

### 4.1 `sync` — 联网同步

```text
python -m apps.cli sync <代码> [--realtime] [--quiet]
```

| 参数 | 含义 |
|------|------|
| `<代码>` | 6 位 A 股代码，如 `600519`、`000001` |
| `--realtime` | 叠加当日实时报价，并尝试写入当日 K 线 |
| `--quiet` | 少打进度，只保留结果与错误 |

**会写入本地库：**

- 价值面快照（价、财报字段、估值所需输入等）
- 日 K 线缓存（默认约 90 个交易日）

### 4.2 `report tech` — 技术面（离线）

```text
python -m apps.cli report tech <代码> [--json] [-o 文件] [--quiet]
```

报告大致包含：

- 综合评分（0–100）与买入信号等级
- 日线趋势 / 均线排列；周线趋势（用于过滤「日线看似好、周线仍空」）
- MA、MACD、RSI、KDJ、量能、乖离率
- 支撑 / 压力、信号理由、风险与警告

**怎么读：**

| 你关注的问题 | 报告里看 |
|--------------|----------|
| 现在算不算下跌通道「接飞刀」？ | 趋势状态、周线、风险段 |
| 有没有技术买点？ | 综合评分、买入信号、信号理由 |
| 止损大致参考？ | 支撑位、跌破关键均线的风险提示 |

### 4.3 `report value` — 价值面（离线）

```text
python -m apps.cli report value <代码> [--json] [-o 文件] [--quiet]
```

报告大致包含：

- **估值原型**（银行 / 高股息·类债 / 高质量价值成长 等）
- 现价、综合评估（偏贵/合理/便宜等）、置信度
- **公允价区间**（低 / 中 / 高）与安全边际、价格分位
- 各估值方法明细（如 PE 相对、DCF、EPV…）；DCF 带增长假设，EPV 多为零增长「地板价」

**怎么读：**

| 你关注的问题 | 报告里看 |
|--------------|----------|
| 公司大概值多少？ | 公允价区间 + 安全边际 |
| 会不会用错方法？ | 原型是否合理（银行不该硬套 DCF） |
| 数据够不够信？ | 置信度、警告列表 |

V1 对保险、军工、高成长科技等原型方法论仍不完整，可能降级并提示置信度偏低——**以警告为准，勿强行解读为精确目标价。**

### 4.4 `report dual` — 红蓝证据分桶（离线）

```text
python -m apps.cli report dual <代码> [--json] [-o 文件] [--quiet]
```

把双轨分析的确定性结论拆成：

- **多方证据** `bull_evidence`
- **空方证据** `bear_evidence`

这是「清单级」输出。若要「论述 + 互相反驳」的叙事，见 §6。

`--json` 方便复制给 Cursor Skill 或自己写脚本。

### 4.5 `report dashboard` — 多维看板（离线）

```text
python -m apps.cli report dashboard <代码> [--json] [-o 文件] [--quiet]
```

一页汇总，大致包含五个分区：

| 分区 | 内容 |
|------|------|
| 价值面 | 原型、现价、评估、公允价区间、安全边际等摘要 |
| 技术面 | 趋势、信号、评分、信号理由/风险摘要 |
| 情绪面 | 当前为「待建」占位（路线图 PO-06） |
| Checklist | 当前为「待建」占位（路线图 PO-04） |
| 综合摘要 | 双轨综合信号 + 红蓝证据条数（多方 N / 空方 M） |

**怎么读：**

| 你关注的问题 | 报告里看 |
|--------------|----------|
| 先快速扫一眼全貌？ | 整页五个分区 + 综合摘要 |
| 多空是否一边倒？ | 综合摘要里的「红蓝证据: 多方 x / 空方 y」 |
| 某维度要细看？ | 再跑 `report tech` / `value` / `dual` |

**与其他 report 的关系：**

- `dashboard` = 汇总视图（短）
- `tech` / `value` / `dual` = 单维度深入（长）
- 看板**不会**替代红蓝对抗完整证据列表或 Cursor Skill 叙事

仅当价值面与技术面**都**没有本地数据时，命令会报错并提示先 `sync`；只有一侧缺失时，该分区会提示「无本地快照」，其余分区仍可输出。

---

## 5. 典型使用场景

### 场景 A：下跌中觉得「便宜」，想买

```cmd
py -m apps.cli sync 600519
py -m apps.cli report dashboard 600519
py -m apps.cli report dual 600519
```

建议顺序：**先看板看全局 → dual 看多空是否一边倒 → 需要时再深入 value/tech。**  
价值便宜但技术破位，仍应视为高风险，而不是「必须抄底」。

### 场景 B：盘中追涨前再确认一眼

```cmd
py -m apps.cli sync 600519 --realtime
py -m apps.cli report tech 600519
```

看评分、乖离率、量能与风险段是否提示「不追高」。

### 场景 C：已有缓存，只想换个格式重看报告

```cmd
py -m apps.cli report value 600519 --json -o reports/600519_value.json
```

无需再 sync（除非你要最新价）。

### 场景 D：对照银行股与成长股差异

```cmd
py -m apps.cli sync 601398
py -m apps.cli report value 601398
```

银行原型应走 PB/相对估值等路径，与茅台类「价值成长」报告结构会不同——这是预期行为。

---

## 6. 红蓝对抗（多方 / 空方互驳）

当前分两层：

| 层级 | 产出 | 入口 |
|------|------|------|
| Level 0 | 确定性证据列表 | `report dual` |
| Level 1 | 基于证据的互驳叙事 | Cursor Agent + `red-blue-confrontation` Skill |

**在 Cursor 中操作：**

1. 先保证该票已 `sync`
2. 对新开对话说例如：「对 600519 做红蓝对抗」
3. Agent 会跑 `report dual --json`，再只根据证据列表写多方/空方论述与互驳

**约束（你也应知情）：**

- 叙事不得编造证据外的财报数字
- 文末应有「AI 叙事仅供参考，请对照原始证据」类免责声明
- **采纳哪一方、是否交易，仍由你决定**（自动记录采纳结果尚未上线）

---

## 7. 数据与隐私

| 路径 | 内容 | 是否进 Git |
|------|------|------------|
| `data/stock_copilot.db` | 本地 SQLite（快照 + K 线） | 否 |
| `config/app.yaml` | 含 Token 的本地配置 | 否 |
| `reports/` | 你生成的报告 | 否（仅保留目录占位） |
| `log/` | 运行日志 | 否 |

Token、密钥请只用本地配置或环境变量，**不要**贴到公开 Issue / Chat。

---

## 8. 常见问题

### Q1：Windows 上 `python -m apps.cli ...` 没任何输出？

多半是微软商店占位 `python`。请改用：

```cmd
py -m apps.cli sync 600519
```

或安装/激活真实 venv 后再用 `python`。

### Q2：`report` 提示找不到缓存 / 请先 sync？

先对该代码执行 `sync`。换电脑或删了 `data/` 也需要重新 sync。

### Q3：价值面置信度很低、很多 N/A？

常见原因：

1. 未启用 Tushare，或缺积分权限
2. 该股原型方法论未覆盖（如保险）
3. 个别字段数据源缺失 —— 看报告「警告」段

### Q4：sync 很慢或失败？

- 单票约 1～2 分钟属正常（多源合并）
- 检查网络；可稍后重试
- 某一数据源失败时通常会尝试下一源；若全部失败会报错退出

### Q5：报告里的数字和券商 App 不一致？

可能因：复权口径、财报期（年报 vs 季报）、实时 vs 收盘、多源合并优先级不同。以本工具报告中的「数据时间 / quote_mode / 警告」为准理解差异。

### Q6：可以分析港股 / 美股吗？

当前 CLI 与数据管线以 **A 股** 为主；其他市场会报不支持或取数失败。

---

## 9. 与开发文档的关系

| 你想… | 看哪份文档 |
|-------|------------|
| **学会日常使用** | 本文 [user-guide.md](user-guide.md) |
| 了解产品愿景与未做能力 | [mrd/product-overview.md](mrd/product-overview.md) |
| 价值面 / 技术面需求细节 | [mrd/features/](mrd/features/) |
| 改代码、目录约定 | [dev/engineering-conventions.md](dev/engineering-conventions.md) |
| Cloud Agent 远程开发 | [dev/cloud-agent.md](dev/cloud-agent.md) |

---

## 10. 命令速查卡

```text
# 同步
py -m apps.cli sync 600519
py -m apps.cli sync 600519 --realtime

# 报告
py -m apps.cli report dashboard 600519
py -m apps.cli report tech 600519
py -m apps.cli report value 600519
py -m apps.cli report dual 600519

# 存盘
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.txt
py -m apps.cli report value 600519 -o reports/600519_value.txt
py -m apps.cli report dual 600519 --json -o reports/600519_dual.json

# 一键试跑
scripts\run_trial.cmd --code 600519
```
