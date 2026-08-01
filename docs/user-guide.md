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
| 常看股票列表 | `watchlist list/add/remove`；`sync`/`report` 支持 `--watchlist` |
| 同步行情与财报快照 | `python -m apps.cli sync <代码>` 或 `sync --watchlist` |
| 技术面报告 | `python -m apps.cli report tech <代码>` |
| 价值面报告 | `python -m apps.cli report value <代码>` |
| 多维看板（一页汇总） | `python -m apps.cli report dashboard <代码>` |
| 综合摘要（可选 LLM 叙事） | `python -m apps.cli report summary <代码> [--narrate]` |
| 红蓝证据分桶（多空清单） | `python -m apps.cli report dual <代码>` |
| 红蓝对抗叙事（多方/空方互驳） | Cursor 里让 Agent 做「红蓝对抗」（见 §7） |
| **看不懂报告里的术语？** | **先读 §5「信号与术语白话词典」** |
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
| `llm:`（可选） | `report summary --narrate` 综合叙事 | OpenAI 兼容 API；见 §2.5 |
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

### 2.5 启用 LLM 综合叙事（可选）

仅在使用 `report summary --narrate` 时需要。未配置时该命令仍会输出确定性摘要，并提示「LLM 未配置」。

在 `config/app.yaml` 取消注释并填写（示例见 `config/app.example.yaml`）：

```yaml
llm:
  base_url: "https://api.deepseek.com/v1"   # 任意 OpenAI 兼容端点
  model: "deepseek-chat"
  api_key: ""                               # 或使用环境变量 LLM_API_KEY
  max_evidence_chars: 24000
```

或只设环境变量：

```powershell
$env:LLM_API_KEY = "你的key"
```

优先级：`llm.api_key` > 环境变量 `LLM_API_KEY`。

---

## 3. 核心工作流（每天怎么用）

```text
sync（联网拉数） → report dashboard / summary / tech / value / dual（离线读库出报告）
```

**原则：**

1. **先 sync，再 report** — 本地没缓存时，`report` 会报错提示你先同步
2. **sync 之后的报告可反复离线重跑** — 不费数据源额度
3. **盘中要贴近现价** — sync 时加 `--realtime`
4. **想先看全局再深入** — 用 `report dashboard` 一页汇总，再按需跑 tech/value/dual
5. **想要自然语言总结** — `report summary`（离线）或 `report summary --narrate`（需 LLM）

### 3.1 最短路径（分析一只股票）

以贵州茅台 `600519` 为例（Windows CMD）：

```cmd
cd /d D:\workspace\stock_copilot

REM 1. 同步数据（约 1～2 分钟）
py -m apps.cli sync 600519

REM 2. 一页看板（价值 + 技术 + 红蓝证据条数摘要）
py -m apps.cli report dashboard 600519

REM 3. 综合摘要（可选：加 --narrate 生成 LLM 叙事）
py -m apps.cli report summary 600519

REM 4. 需要时再深入单维度
py -m apps.cli report tech 600519
py -m apps.cli report value 600519
py -m apps.cli report dual 600519
```

macOS / Linux 把 `py -m` 换成 `python -m` 即可。

### 3.2 常看股票列表（推荐日常用法）

列表文件：[`config/watchlist.yaml`](../config/watchlist.yaml)（**入库**，改完后 `git commit` 即可多设备同步）。

与 `value_data_validation_stocks.yaml`（E2E 验证样本）无关，请勿混用。

```cmd
REM 查看
py -m apps.cli watchlist list

REM 添加 / 删除
py -m apps.cli watchlist add 600519 --name 贵州茅台
py -m apps.cli watchlist remove 600519

REM 对整表同步与出报告（-o 视为目录）
py -m apps.cli sync --watchlist
py -m apps.cli report dashboard --watchlist -o reports/watchlist
py -m apps.cli report value --watchlist -o reports/watchlist
py -m apps.cli report tech --watchlist -o reports/watchlist
py -m apps.cli report dual --watchlist -o reports/watchlist
```

改列表后记得提交：

```cmd
git add config/watchlist.yaml
git commit -m "chore: update watchlist"
git push
```

### 3.3 把报告存成文件

```cmd
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.txt
py -m apps.cli report tech 600519 -o reports/600519_tech.txt
py -m apps.cli report value 600519 -o reports/600519_value.txt
py -m apps.cli report dual 600519 -o reports/600519_dual.txt
```

`reports/` 目录默认不进 Git，适合本地留存。

### 3.4 一键试跑（推荐新手）

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

### 4.0 `watchlist` — 常看列表

```text
python -m apps.cli watchlist list
python -m apps.cli watchlist add <代码> [--name 名称]
python -m apps.cli watchlist remove <代码>
```

### 4.1 `sync` — 联网同步

```text
python -m apps.cli sync <代码> [--realtime] [--quiet]
python -m apps.cli sync --watchlist [--realtime] [--quiet]
```

| 参数 | 含义 |
|------|------|
| `<代码>` | 6 位 A 股代码，如 `600519`、`000001`；与 `--watchlist` 二选一 |
| `--watchlist` | 对 `config/watchlist.yaml` 全部代码依次同步 |
| `--realtime` | 叠加当日实时报价，并尝试写入当日 K 线 |
| `--quiet` | 少打进度，只保留结果与错误 |

**会写入本地库：**

- 价值面快照（价、财报字段、估值所需输入等）
- 日 K 线缓存（默认约 90 个交易日）

### 4.2 `report tech` — 技术面（离线）

```text
python -m apps.cli report tech <代码> [--json] [-o 文件] [--quiet]
python -m apps.cli report tech --watchlist [-o 目录] [--json] [--quiet]
```

`--watchlist` 时 `-o` 视为**目录**，写入 `{代码}_tech.txt`。

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

术语释义与例子见 **§5.3**。

### 4.3 `report value` — 价值面（离线）

```text
python -m apps.cli report value <代码> [--json] [-o 文件] [--quiet]
python -m apps.cli report value --watchlist [-o 目录] [--json] [--quiet]
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

术语释义与例子见 **§5.2**。

### 4.4 `report dual` — 红蓝证据分桶（离线）

```text
python -m apps.cli report dual <代码> [--json] [-o 文件] [--quiet]
python -m apps.cli report dual --watchlist [-o 目录] [--json] [--quiet]
```

把双轨分析的确定性结论拆成：

- **多方证据** `bull_evidence`
- **空方证据** `bear_evidence`

这是「清单级」输出。若要「论述 + 互相反驳」的叙事，见 §7。

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

### 4.6 `report summary` — 综合摘要（默认离线，可选 LLM）

```text
python -m apps.cli report summary <代码> [--json] [-o 文件] [--quiet] [--narrate]
```

- **默认（不加 `--narrate`）**：严格离线，输出**代码+名称**、综合信号、价值评级、红蓝证据条数与确定性摘要行
- **`--narrate`**：额外联网调用 LLM，生成 `summary` / `key_points` / `risks` 叙事段落（需在 `config/app.yaml` 配置 `llm:` 或设置环境变量 `LLM_API_KEY`）
- LLM 失败时**不会**整命令失败：仍输出确定性摘要，并提示失败原因

标题形如 `=== 综合摘要 002027 分众传媒 ===`（名称来自价值面快照；无名称时仅显示代码）。

数值仍以确定性模块为准；叙事不得编造 evidence 外数字（由 `narrate()` grounded 校验拦截）。

---

## 5. 看报告：信号与术语白话词典

报告里会堆很多指标。**你不需要每个都懂**——先用 §5.1 的「三件事」读法，卡住某个词再查下面词典。  
例子尽量取自 `reports/` 里真实跑出来的报告（如分众 `002027`、海康 `002415`、长江电力 `600900`）。

### 5.1 先只看三件事（约 30 秒）

打开 `report dashboard` 或 `report summary`，按顺序看：

| 顺序 | 看什么 | 白话 | 怎么用 |
|------|--------|------|--------|
| ① | **综合信号**（买入 / 观望 / 卖出等） | 双轨合在一起的「总态度」 | 这是**建议倾向**，不是下单指令 |
| ② | **价值评级 / 评估** + **安全边际** | 现价相对「大概值多少」是贵还是便宜 | 负得很多 → 偏贵；正得很多 → 偏便宜 |
| ③ | **技术面趋势 + 风险段** | 最近涨跌方向，以及有没有「过热/破位」警告 | 趋势好但风险段全是超买 → 更像追涨，不是捡漏 |

然后再决定要不要打开 `value` / `tech` / `dual` 细看。

**心智模型（很重要）：**

```text
价值面回答：这家公司大概值多少？（贵不贵）
技术面回答：现在买点/卖点好不好？（会不会接飞刀、追高）
红蓝证据：把「看多」和「看空」的理由分开放，避免你只盯着一边
```

两边经常打架（例如「价值偏贵 + 技术强势」）——**打架本身就是信息**，不是软件坏了。综合信号常会因此变成「观望」。

### 5.2 价值面术语

#### 原型（prototype）

工具按公司类型选估值方法。常见：

| 报告里的值 | 白话 | 例子 |
|------------|------|------|
| `high_dividend` | 高股息 / 类债：更看分红折现 | 分众 `002027`、长江电力 `600900` |
| `value_growth` | 价值成长：DCF、相对 PE 等更常见 | 海康 `002415` |
| `bank` | 银行：更看 PB / 剩余收益等 | 工行 `601398` |

**怎么用：** 先确认原型是否离谱（银行被当成成长股硬套 DCF 就该怀疑）。原型不对 → 后面数字再漂亮也要打折看。

#### 现价 / 公允价区间 / 安全边际 / 价格分位

| 术语 | 白话 | 怎么用 | 例子 |
|------|------|--------|------|
| **现价** | 报告用的股价（多为 sync 时点） | 所有「贵/便宜」都相对这个价 | 长江电力现价 `29.09` |
| **公允价区间** `低 ~ 中 ~ 高` | 多方法估出来的「大致合理价带」 | 现价在区间下方偏便宜，上方偏贵；**中位**最常拿来比 | `20.92 ~ 29.83 ~ 36.08`：现价 29.09 靠近中位 → 不极端 |
| **安全边际（MOS）** | 相对公允价（常取中位）还剩多少「折扣」；**正数偏便宜，负数偏贵** | 先看正负与量级，别死磕小数 | `600900` 安全边际 `+2.5%` ≈ 贴近公允；明显很大的负数要当「偏贵」警报 |
| **价格分位** | 现价落在公允价区间里的位置（0%～100%） | 接近 100% → 已在区间上沿附近 | `002415` 价格分位 `100%`：现价贴着区间高位 |

#### Undervalued / Fair / Overvalued（低估 / 合理 / 高估）

单个估值方法对「现价 vs 该方法公允价」的标签：

| 英文 | 中文 | 白话 |
|------|------|------|
| **Undervalued** | 低估 | 该方法算出的公允价 **高于** 现价 → 偏便宜 |
| **Fair / Fair Value** | 合理 | 差不多 |
| **Overvalued** | 高估 | 该方法公允价 **低于** 现价 → 偏贵 |

**怎么用：** 看的是**这一条方法**的意见，不是最终结论。同一只票可以「DDM Undervalued + EPV Overvalued」——分红折现觉得便宜、零增长盈利能力觉得贵。

**例子（分众 `002027` value 报告）：**

- `ddm` / `two_stage_ddm` → Undervalued（按股息折现偏便宜）
- `epv` / `owner_earnings` → Overvalued（按盈利能力偏贵）

→ 红蓝对抗里就会一边拿 DDM 当多方，一边拿 EPV 当空方。

#### 常见估值方法（报告「估值方法」段）

| 报告代号 | 白话一句话 | 怎么用 |
|----------|------------|--------|
| **DDM / Two-Stage DDM** | 把未来分红折成今天的价 | 适合稳定分红股；增长假设一变，结论会变 |
| **DCF** | 把未来自由现金流折现 | 含增长假设（如 `g₁=10% 5年`）；假设乐观时容易给出很「便宜」的数 |
| **EPV** | 假设**零增长**的盈利能力「地板价」 | 偏保守；现价远高于 EPV → 常标 Overvalued |
| **Owner Earnings** | 巴菲特式「所有者收益」估值 | 看企业真实可分配能力，常与 EPV 同方向 |
| **PE relative / PB relative** | 相对自己历史估值贵不贵 | `bottom quartile`≈历史偏便宜；`top quartile`≈历史偏贵 |
| **EV/EBITDA** | 企业价值相对 EBITDA 的倍数估值 | 跨公司比「贵不贵」常用；资本结构差异大时要小心 |
| **Graham** | 格雷厄姆经典公式/数字 | 不适用时会 `Not Applicable`（如账面太低）——忽略即可 |
| **Piotroski F-Score** | 财务健康打分 0–9 | 越高越好；`5/9 Average` = 中等，有些财务隐忧 |
| **Beneish M-Score** | 盈余操纵风险 | `Low` 通常放心；`High` 要警惕财报质量 |
| **Altman Z-Score** | 破产风险粗筛 | `Low Bankruptcy Risk` = 破产风险低（偏正面）；**银行/重资产金融股上常失真**，勿单独当空头理由 |
| **Value Trap（价值陷阱）** | 「看起来便宜，但可能一直便宜或基本面有坑」 | `Medium/High` → 便宜也不能闭眼买 |

**Applicable / Not Applicable / Limited：** 该方法是否适用于这只票。不适用就跳过，别强行解读。

#### 评估 / 价值评级 / 置信度

| 术语 | 白话 | 怎么用 |
|------|------|--------|
| **评估**（value 报告抬头） | 该票价值面的综合标签：低估 / 合理 / 高估 等 | 比单个方法更「总结」，但仍是模型输出 |
| **价值评级**（summary / dual / 看板综合摘要） | 双轨融合里用的价值侧结论 | 常与「综合信号」一起看 |
| **置信度** High / Medium / Low | 数据与方法够不够撑这个结论 | Low + 一堆警告 → 当参考，别当精确目标价 |

### 5.3 技术面术语

| 术语 | 白话 | 怎么用 | 例子 |
|------|------|--------|------|
| **综合评分** 0–100 | 技术面打分，越高越「技术上看多」 | 中高分仍要看风险段；不是收益率预测 | `002027` 评分 `62` |
| **信号** 买入/观望/卖出 | 技术规则给出的动作倾向 | 常和价值面打架；以综合摘要为准做总览 | tech 写「买入」，看板综合却是「观望」——正常 |
| **趋势 / 多头排列 / 强势多头** | 短期均线在上、价格偏强 | 说明最近涨势；**不等于低估** | 「强势多头，顺势做多」 |
| **周线** | 用周线趋势过滤日线噪音 | 日线很好但周线空头 → 小心「假突破」 | 「周线均线缠绕，趋势不明」→ 过滤力弱 |
| **MA5 / MA10 / MA20 / MA60** | 5/10/20/60 日均线 | 价格在均线上方偏强；跌破常当风险 | 现价 5.62 > MA5 5.44 |
| **乖离率 Bias** | 现价偏离某条均线的百分比 | 偏离过大 = 短期涨太多/跌太多 | `Bias MA5=3.27%`：略高于五日线 |
| **MACD** | 趋势动量指标 | 报告写「多头」≈ 动量偏向上 | 「多头排列，持续上涨」 |
| **RSI** | 超买超卖（常见 0–100） | **>70 超买**（短期回调风险↑）；**<30 超卖** | `RSI 75.3>70` → 风险段会警告 |
| **KDJ** | 另一套超买超卖 | K/D 很高或 **J>100** 常标超买/超界 | `J=103` → 短线过热信号 |
| **量能 / 量比** | 成交量是否放大 | 「量能正常」≠ 无信息；暴量要另看 | `5日量比 1.25` |
| **支撑 / 压力** | 下方易获买盘 / 上方易遇卖盘的参考价 | 止损、突破观察的粗锚点，不是保证 | 支撑 5.07、压力 5.64 |
| **金叉 / 死叉** | 短期线向上/向下穿越长期线 | 金叉偏多动能；死叉偏空 | 「KDJ 金叉」 |
| **✅ / ⚡ / ⚠️** | 理由 / 可小仓 / 风险警告 | 先读 ⚠️，再决定要不要信 ✅ | 超买警告出现时，慎把「买入」当追涨许可 |

### 5.4 综合信号与红蓝对抗

| 术语 | 白话 | 怎么用 |
|------|------|--------|
| **综合信号** | 价值 + 技术合在一起的总倾向 | 「价值高估 + 技术买入」经常得到 **观望** |
| **多方证据 (bull)** | 支持偏多/偏便宜/偏强的条目 | 用来理解「乐观理由有哪些」 |
| **空方证据 (bear)** | 支持偏空/偏贵/有风险的条目 | **至少扫一眼**，避免只看多方自我感觉良好 |
| **红蓝对抗叙事** | AI 根据证据列表写的互驳作文 | 必须对照上方「原始证据」；数字以证据为准 |

**例子（分众 `002027` dual）：**

- 多方：两个 DDM Undervalued + 强势多头技术信号  
- 空方：价值高估、EPV/Owner Earnings Overvalued、RSI/KDJ 超买、价值陷阱 Medium  
- 综合信号：**观望**（两边都有力，不宜一边倒下结论）

### 5.5 用一份真实报告走读（分众 002027）

假设你打开了 `002027_dashboard.txt` / `002027_summary.txt`：

1. **综合信号 = 观望** → 先别想「软件让我买/卖」  
2. **价值：公允价区间 3.14～5.58～8.67，安全边际为负，评级偏高估** → 相对工具算法，现价不便宜（甚至偏贵）  
3. **技术：强势多头、评分 62、信号买入，但风险写着 RSI/KDJ 超买** → 涨势在，但短线过热  
4. 结论翻译成人话：**「涨得好，但不便宜，还超买 → 观望更合适」**  
5. 若要争论细节，再打开 `*_dual.txt` 或 `*_confrontation.md`，对照多方/空方条目，而不是只读 AI 论述段

**海康 `002415` 的补充直觉：**  
value 报告里 DCF 给了很高的公允价并标 Undervalued，但 EPV/EV·EBITDA 标 Overvalued，综合评估却可以是「合理」。  
→ **单看一个「Undervalued」不够**；要看有几个方法同意、置信度、以及陷阱/财务分数。

### 5.6 常见误读（避坑）

1. **技术「买入」≠ 价值便宜** — 可能是贵了还在涨。  
2. **某个方法 Undervalued ≠ 整票低估** — 看评估/评级与多个方法是否同向。  
3. **Altman「High Bankruptcy Risk」在银行股上别过度解读** — 银行资产负债表特殊，该指标常误报。  
4. **对抗叙事里的形容词可以夸张，证据列表里的数字才是锚**。  
5. **置信度 Low / 大量 Not Applicable** — 当「信息不足」，不要当精确导航。

---

## 6. 典型使用场景

### 场景 A：下跌中觉得「便宜」，想买

```cmd
py -m apps.cli sync 600519
py -m apps.cli report dashboard 600519
py -m apps.cli report summary 600519
py -m apps.cli report dual 600519
```

建议顺序：**先看板看全局 → summary 看确定性摘要 → dual 看多空是否一边倒 → 需要时再深入 value/tech。**  
术语不懂时翻 **§5**。价值便宜但技术破位，仍应视为高风险，而不是「必须抄底」。

### 场景 B：盘中追涨前再确认一眼

```cmd
py -m apps.cli sync 600519 --realtime
py -m apps.cli report tech 600519
```

看评分、乖离率、量能与风险段是否提示「不追高」（术语见 §5.3）。

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

## 7. 红蓝对抗（多方 / 空方互驳）

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

## 8. 数据与隐私

| 路径 | 内容 | 是否进 Git |
|------|------|------------|
| `data/stock_copilot.db` | 本地 SQLite（快照 + K 线） | 否 |
| `config/app.yaml` | 含 Token 的本地配置 | 否 |
| `reports/` | 你生成的报告 | 否（仅保留目录占位） |
| `log/` | 运行日志 | 否 |

Token、密钥请只用本地配置或环境变量，**不要**贴到公开 Issue / Chat。

---

## 9. 常见问题

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

### Q5b：报告里一堆 Undervalued / RSI / 安全边际，完全看不懂？

先读 **§5 信号与术语白话词典**：用「三件事」读法扫看板，再按需查词。不必先学会全部指标。

### Q6：可以分析港股 / 美股吗？

当前 CLI 与数据管线以 **A 股** 为主；其他市场会报不支持或取数失败。

### Q7：`report summary --narrate` 提示 LLM 未配置？

未配置 `llm:` 或环境变量 `LLM_API_KEY` 时属预期：命令仍输出确定性摘要，并提示失败原因，退出码为 0。按 §2.5 配置后重试即可。叙事数字须能锚定 evidence；若 grounded 校验失败也会同样降级。

---

## 10. 与开发文档的关系

| 你想… | 看哪份文档 |
|-------|------------|
| **学会日常使用** | 本文 [user-guide.md](user-guide.md) |
| **看懂报告术语与信号** | 本文 **§5** |
| 了解产品愿景与未做能力 | [mrd/product-overview.md](mrd/product-overview.md) |
| 价值面 / 技术面需求细节 | [mrd/features/](mrd/features/) |
| 改代码、目录约定 | [dev/engineering-conventions.md](dev/engineering-conventions.md) |
| Cloud Agent 远程开发 | [dev/cloud-agent.md](dev/cloud-agent.md) |

---

## 11. 命令速查卡

```text
# 常看列表
py -m apps.cli watchlist list
py -m apps.cli watchlist add 600519 --name 贵州茅台
py -m apps.cli watchlist remove 600519

# 同步
py -m apps.cli sync 600519
py -m apps.cli sync 600519 --realtime
py -m apps.cli sync --watchlist

# 报告
py -m apps.cli report dashboard 600519
py -m apps.cli report summary 600519
py -m apps.cli report summary 600519 --narrate
py -m apps.cli report tech 600519
py -m apps.cli report value 600519
py -m apps.cli report dual 600519
py -m apps.cli report value --watchlist -o reports/watchlist

# 存盘
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.txt
py -m apps.cli report summary 600519 -o reports/600519_summary.txt
py -m apps.cli report value 600519 -o reports/600519_value.txt
py -m apps.cli report dual 600519 --json -o reports/600519_dual.json

# 一键试跑
scripts\run_trial.cmd --code 600519
```
