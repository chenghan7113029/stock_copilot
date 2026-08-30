# stock_copilot 使用说明书

> 面向：**实际使用本工具分析 A 股的个人投资者**（非开发者文档）  
> 当前入口：**命令行（CLI）**；Web 界面仍在规划中
> 最后更新：2026-08-15

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
| 飞书 dual 推送 | `feishu push --watchlist`（经 `lark-cli`，见 §3.5） |
| 同步行情与财报快照 | `python -m apps.cli sync <代码>` 或 `sync --watchlist` |
| 技术面报告 | `python -m apps.cli report tech <代码>` |
| 价值面报告 | `python -m apps.cli report value <代码>` |
| 多维看板（一页汇总） | `python -m apps.cli report dashboard <代码>` |
| 综合摘要（可选 LLM 叙事） | `python -m apps.cli report summary <代码> [--narrate]` |
| 红蓝证据分桶（多空清单） | `python -m apps.cli report dual <代码>` |
| 市场情绪 V1 | `python -m apps.cli sync market` 后执行 `report sentiment <代码>` 或 `report dual <代码>` |
| 红蓝对抗叙事（多方/空方互驳） | Cursor 里让 Agent 做「红蓝对抗」（见 §7） |
| 决策清单（提交 / 历史） | `python -m apps.cli checklist submit/show <代码>`（见 §4.7） |
| 无仓位视角入场检查 | `position set` + `entry-check`（见附录） |
| 人工覆盖估值原型 | `value override <代码> <原型> --reason ...`（见附录） |
| 交易记录与复盘 | `trade record` + `report trade-review`（见附录） |
| 持仓组合集中度 | `report portfolio`（见附录） |
| 锚定防御呈现 | `report value` 定性分位；可选 `--show-anchor-price` |
| **看不懂报告里的术语？** | 报告**默认内嵌讲解**（指标注释 / 估值方法卡片 / 价值陷阱拆解）；也可对照 §5 |
| 一键试跑多只样本股 | `scripts/run_trial.cmd`（Windows） |

### 1.2 尚未交付（请勿期待）

Web 界面、个股融资余额/龙虎榜/社媒文本情绪、协方差组合优化等仍在路线图中。详见 [mrd/roadmap-todo.md](mrd/roadmap-todo.md)。

> **说明：** CLI「多维看板 / Checklist / 情绪 / 复盘」已可用；Web 版仍待建。
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
| `data_sources.enabled` | 用哪些数据源 | 默认 **tushare(1) + baostock(2)**；AKShare 仅紧急回滚时手动加回 |
| Tushare（推荐） | 财报更全、K 线/实时/情绪主路径 | 注册 [tushare.pro](https://tushare.pro)，见 §2.4 |
| `llm:`（可选） | `report summary --narrate` 综合叙事 | OpenAI 兼容 API；见 §2.5 |
| `db.url` | 本地数据库路径 | 默认 `data/stock_copilot.db`，一般不用改 |
| `logging.cli_progress` | CLI 是否打印进度 | `true` 方便观察 sync |

`config/app.yaml` **不会**提交到 Git，可放心写 Token。

### 2.4 启用 Tushare（强烈推荐）

没有 Tushare 时仅 Baostock 也能跑离线报告，但联网 sync / 价值面质量会差一截（尤其 FCF、净负债、历史估值分位、银行专项指标）；实时与情绪也依赖 Tushare。

**方式 A — 写进配置（二选一即可）：**

在 `config/app.yaml` 的 `data_sources.enabled` 中确认（默认已包含）：

```yaml
    - name: tushare
      priority: 1
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

### 2.4.1 紧急回滚：手动加回 AKShare

默认配置已不含 AKShare。若 Tushare 全站故障、需临时回退，在 `config/app.yaml` 的 `data_sources.enabled` 中追加：

```yaml
    - name: akshare
      priority: 3
```

然后重跑 `sync` / `sync market`。稳定后建议删回该条目，继续以 tushare + baostock 为主。

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

### 3.5 飞书推送 dual（通勤阅读）

只推红蓝证据分桶（`report dual`）。每份 `{code}_dual.md` 新建一篇飞书文档，成功后立刻发一条消息。

**前置：** 安装官方 [lark-cli](https://github.com/larksuite/cli)，并在本机登录：

```cmd
npx @larksuite/cli@latest install
lark-cli config init
lark-cli auth login --recommend
```

在 `config/app.yaml` 填写推送目标（示例见 `config/app.example.yaml`）：自聊用 `feishu.user_id`（`lark-cli whoami` / `auth status` 的 open_id），群聊用 `feishu.chat_id`；二者同时配置时优先 `user_id`。

**先本地试跑（不调 lark-cli 写命令）：**

```cmd
py -m apps.cli feishu push --watchlist --dry-run --no-sync --slot 1700
```

文件落在 `reports/feishu/{日期}/{slot}/{代码}_dual.md`。消息标题格式：`今日研报_{股票名称}_{YYYY-MM-DD}_{HHmm}`，正文只有文档链接。

**Windows 计划任务（当前：周一至周五 08:30）：**

本机已注册任务 `StockCopilot-FeishuPush-0830`，调用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\workspace\stock_copilot\scripts\feishu_push_slot.ps1 -Slot 0830
```

等价 CLI：`py -m apps.cli feishu push --watchlist --slot 0830`（默认会按配置先 sync）。日志写入 `log/feishu_push_0830_*.log`（UTF-8）。脚本启动前会检查 `lark-cli auth status`，用户 token 失效时直接失败并写日志。

须以**已执行过 `lark-cli auth login` 的同一 Windows 用户**登录会话运行（任务为 Interactive 登录）。非交易日会 `[skip]` 并以退出码 0 结束。PC 休眠/未登录可能漏推；任务已开「错过时尽快运行」（`StartWhenAvailable`）。

**常见收不到推送的原因：**

1. `lark-cli` refresh token 过期（约 7 天未成功续期）→ 运行 `lark-cli auth login --recommend` 重新扫码授权（OAuth 安全限制，无法完全免扫码）
2. access token 过期（约 2 小时）→ **无需手动操作**；推送前脚本会 `auth status --verify`，lark-cli 自动用 refresh token 续期
2. 8:30 时 PC 未开机或未登录 → 任务不会按时执行
3. 查看 `log/feishu_push_0830_*.log` 末尾的 `exit_code` 与 `[error]` 行

若以后要加 13:00 / 17:00，可再注册同脚本并分别传 `-Slot 1300 -Realtime` / `-Slot 1700`。

### 3.3 把报告存成文件

```cmd
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.md
py -m apps.cli report tech 600519 -o reports/600519_tech.md
py -m apps.cli report value 600519 -o reports/600519_value.md
py -m apps.cli report dual 600519 -o reports/600519_dual.md
```

`reports/` 目录默认不进 Git，适合本地留存。默认人类可读报告扩展名为 `.md`（Markdown）；若你显式传入 `-o .../*.txt` 仍按该路径写入。

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

### 4.0a `feishu push` — 飞书 dual 推送

```text
python -m apps.cli feishu push --watchlist [--dry-run] [--sync|--no-sync] [--realtime] [--slot 1700]
```

详见 §3.5。依赖本机 `lark-cli auth login`。

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

`--watchlist` 时 `-o` 视为**目录**，写入 `{代码}_tech.md`。

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

`sync` 从 Tushare 基础资料读取行业名称后，`report value` 会先做「行业 → 原型」映射，再使用财务启发式：银行、电力、水务、燃气、高速公路、港口会直接匹配已支持原型；保险、军工会明确显示 `unknown`，避免因高负债率被误判为银行。未收录或缺失行业信息时，才会回退到既有的杠杆率、股息率和成长率规则。

V1 对保险、军工、高成长科技等原型方法论仍不完整；已识别的保险、军工行业会降级为 `unknown` 并提示置信度偏低——**以警告为准，勿强行解读为精确目标价。**

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
| 情绪面 | 最近一次 `sync market` 的市场情绪摘要；无快照时降级提示 |
| Checklist | 本地该票最近决策清单摘要；无记录时提示可 `checklist submit` |
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

### 4.7 `checklist` — 决策清单提交与历史

```text
python -m apps.cli checklist submit <代码> [--action buy|sell]
python -m apps.cli checklist show <代码> [--json]
```

`submit` 会交互式收集：至少两条长期价值理由、技术面配合、情绪位置及解读、止损点、止盈点。价值理由逐条输入，直接回车结束；所有字段输入完成后，系统以确定性规则校验并写入本地数据库。

```text
开始填写 600519 的 Checklist（价值理由至少 2 条；直接回车结束理由输入）
请输入第 1 条价值理由：PE 处于历史低分位，安全边际充足，当前价格低于合理估值区间。
请输入第 2 条价值理由：现金流稳健，ROE 持续高于行业均值，基本面仍有韧性。
请输入第 3 条价值理由：
短期技术面配合情况：价格回到 MA20 上方，成交量温和放大。
当前情绪位置及解读：市场情绪偏谨慎，尚未出现极端贪婪。
止损点：1400
止盈点：1800
Checklist 提交成功（合规）
```

若价值理由少于两条、理由过短、仅是新闻/传闻式单一来源，或必填字段缺失，提交会被标记为**不合规**并打印全部原因；它不会成为合规 Checklist，但仍会留痕，方便之后复盘：

```text
Checklist 提交被拒绝：
  - 第 1 条价值理由疑似可得性单一来源
  - 价值理由中有效条目不足 2 条（存在过短或疑似新闻/传闻式单一来源理由）
本次提交不构成合规 Checklist
```

用 `checklist show 600519` 查看该股票的全部历史记录（包括合规与不合规尝试）；`--json` 适合自行处理输出。

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

#### 行业→原型映射 / Prototype Router（原型路由器）

**行业→原型映射**是报告选方法前的第一道分类：系统复用 Tushare `stock_basic.industry` 的简化行业名称，把明确的行业信号转换为估值原型。**Prototype Router（原型路由器）**则是执行完整判定顺序的组件：固定样本覆盖 → 行业映射 → 财务特征启发式。

| 行业例子 | 路由结果 | 含义 |
|----------|----------|------|
| `商业银行` | `bank` | 使用银行适用的方法集，例如 PB、剩余收益 |
| `电力` | `high_dividend` | 即使股息率暂时不满足阈值，也优先使用高股息方法集 |
| `保险`、`国防军工` | `unknown` | 行业已识别，但专用方法论尚未实现；不会套用银行的高杠杆规则 |
| 空行业或未收录行业 | 继续财务启发式 | 例如高杠杆可能判为 `bank`，高股息低成长可能判为 `high_dividend` |

这不是申万（SW）或中证（CS）的官方多级行业代码体系；当前仅使用已接入的 Tushare 简化行业名称。若报告为 `unknown`，它表示「不要把现有三类 V1 方法强行套用」，而非股票本身没有行业归属。

#### 现价 / 公允价区间 / 安全边际 / 价格分位

| 术语 | 白话 | 怎么用 | 例子 |
|------|------|--------|------|
| **现价** | 报告用的股价（多为 sync 时点） | 所有「贵/便宜」都相对这个价 | 长江电力现价 `29.09` |
| **公允价区间** `低 ~ 中 ~ 高` | 多方法估出来的「大致合理价带」 | 现价在区间下方偏便宜，上方偏贵；**中位**最常拿来比 | `20.92 ~ 29.83 ~ 36.08`：现价 29.09 靠近中位 → 不极端 |
| **安全边际（MOS）** | 相对公允价中位的折扣/溢价，单位是**百分数点**（`7.1` 显示为 `7.1%`）；**正数偏便宜，负数偏贵** | `report value` / `dual` / `dashboard` 必须同量级；若看到约 `-80%` 而价值报告约 `-0.8%`，属旧版展示 bug（已修） | 现价略高于公允中位时可能是 `-0.8%`（略贵），不是 `-80%` |
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

### 5.4a 决策清单与偏差防护

| 术语 | 白话 | 怎么用 |
|------|------|--------|
| **决策清单（Checklist）** | 在买入或卖出前写下依据、风险边界和执行条件的结构化记录 | 不是系统替你下单；它强制把「为什么做、错了怎么办」写清楚 |
| **可得性偏差 / 可得性启发式** | 因为刚看到、容易想起的信息（如爆款新闻、群聊传闻）而高估其重要性 | 「昨晚看新闻说要涨」不能作为唯一理由；至少补充可核对的估值、现金流或财报证据 |
| **价值理由** | 说明公司长期价值或估值吸引力的依据 | 优先引用 PE/PB 分位、安全边际、现金流、ROE、财报等；V1 不会自动核验数字真伪 |
| **技术面配合** | 当前趋势、关键均线、量能等是否支持入场或离场 | 例如「站上 MA20、量能温和放大」；它不是保证上涨 |
| **止损点 / 止盈点** | 交易前预先定义的风险退出与目标处理价位 | 应与支撑、压力、波动和仓位一起考虑，不能把它当成必然成交价 |

### 5.5 用一份真实报告走读（分众 002027）

假设你打开了 `002027_dashboard.md` / `002027_summary.md`：

1. **综合信号 = 观望** → 先别想「软件让我买/卖」  
2. **价值：公允价区间 3.14～5.58～8.67，安全边际为负，评级偏高估** → 相对工具算法，现价不便宜（甚至偏贵）  
3. **技术：强势多头、评分 62、信号买入，但风险写着 RSI/KDJ 超买** → 涨势在，但短线过热  
4. 结论翻译成人话：**「涨得好，但不便宜，还超买 → 观望更合适」**  
5. 若要争论细节，再打开 `*_dual.md` 或 `*_confrontation.md`，对照多方/空方条目，而不是只读 AI 论述段

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

`report tech` / `value` / `dual` **默认**在正文后附讲解：技术指标中文注释、Applicable 估值方法完整卡片（含义/适用/公式/本次入参来源/结果）、价值陷阱五维度白话。先扫决策摘要，再往下翻讲解即可。§5 词典仍可作速查。

### Q5c：dual 摘要安全边际和 value 差很多？

旧版 dual/dashboard 误用比例格式化，把百分数点再 ×100。当前版本应与 value 一致（例如都是 `-0.8%`）。若仍不一致，请升级代码后重跑报告。

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
py -m apps.cli report value 600519 --show-anchor-price
py -m apps.cli report dual 600519
py -m apps.cli report sentiment 600519
py -m apps.cli report trade-review
py -m apps.cli report portfolio
py -m apps.cli report value --watchlist -o reports/watchlist

# 决策与持仓
py -m apps.cli checklist submit 600519 --action buy
py -m apps.cli checklist show 600519
py -m apps.cli position set 600519 --cost 1500 --shares 100
py -m apps.cli entry-check 600519
py -m apps.cli value override 600519 high_dividend --reason "按高股息方法复核"
py -m apps.cli trade record 600519 buy --price 10 --quantity 100

# 市场情绪（联网）
py -m apps.cli sync market

# 存盘
py -m apps.cli report dashboard 600519 -o reports/600519_dashboard.md
py -m apps.cli report summary 600519 -o reports/600519_summary.md
py -m apps.cli report value 600519 -o reports/600519_value.md
py -m apps.cli report dual 600519 --json -o reports/600519_dual.json

# 一键试跑
scripts\run_trial.cmd --code 600519
```

---

## 附录：锚定防御速查

`report value` 会将价格分位以“定性分档优先、数值为辅”的方式呈现。例如：

```text
当前价格处于历史估值区间中高位（分位 72%）
```

这里的**价格分位**是现价在本次多方法估算的公允价区间中的位置，不是未来收益概率，也不是历史股价表现的回测结论。分位 `<20%` 为“历史估值区间低位”，`20%～<40%` 为“中低位”，`40%～<60%` 为“中性”，`60%～<80%` 为“中高位”，`≥80%` 为“高位”；边界值归入较高一档。

**历史最高价默认隐藏**，以下普通报告不会显示该数值：

```cmd
py -m apps.cli report value 600519
```

只有在需要核对本地 K 线缓存时，才显式请求展示：

```cmd
py -m apps.cli report value 600519 --show-anchor-price
```

展示结果会注明本地缓存的交易日条数，并附“仅供参考，不建议作为决策心理锚点”的提示。**锚定效应**指判断被买入价、历史高点等熟悉数字牵引；因此，本工具将这类绝对价格默认隐藏。缓存窗口不等同于完整上市历史，仍应结合安全边际、置信度、风险警示和技术面证据作判断。

---

## 附录：无仓位视角入场检查（entry-check）

当你已经持有某只股票、正考虑补仓或继续持有时，可用此命令把注意力拉回到“今天的价格和证据”，而不是过去的买入价格。

先同步本地数据，再录入当前持仓，最后执行检查：

```powershell
py -m apps.cli sync 600519
py -m apps.cli position set 600519 --cost 1500 --shares 100
py -m apps.cli entry-check 600519
```

需要保存可读报告或供其他工具读取的 JSON 时：

```powershell
py -m apps.cli entry-check 600519 -o reports/600519_entry_check.md
py -m apps.cli entry-check 600519 --json -o reports/600519_entry_check.json
```

`entry-check` 严格离线，只读取已同步的价值快照与 K 线缓存；缺少本地数据时，请先运行 `sync`。它会展示现价、价值面和技术面摘要，并提问：

> 若你今天没有 600519 的仓位，以现价买入，你还会买吗？

录入持仓后，检查报告不会展示成本价或盈亏百分比；若未录入持仓，命令仍可使用，并会说明这是标准三维分析。`position set` 的确认输出和你的终端历史会包含你输入的成本价，请勿将其共享到不可信位置。

### 术语说明

- **无仓位视角**：暂时把“我已经买了”当作不存在，只根据当前价格和可验证证据回答“今天是否愿意买”。它是重新评估工具，不是自动卖出指令。
- **沉没成本**：已经投入且无法通过当前决策改变的过去成本。因为“已经亏了很多”而继续补仓，可能掩盖“今天是否仍值得继续持有或买入”的问题。
- **锚定效应**：被熟悉的数字牵引判断，例如自己的买入价或历史最高价。入场检查通过不呈现成本与盈亏比例，减少这些数字对当次判断的干扰。

若答案是否定的，先重新审视减仓或止损是否符合你的交易计划；本工具不会自动下单，也不会保存你的“是/否”回答。需要形成正式决策记录时，使用 `checklist submit <代码>`。

---

## 附录：已识别行业的精确原型降级提示

当 `report value` 已经识别出行业、但该行业的专用估值方法尚未实现时，报告会在「警告」区说明原因，而不是只显示“原型未识别”。这表示系统知道行业归属，但不会用不适用的方法替代专用模型；相关结果只能作为有限参考，不是精确目标价或交易指令。

例如：

- **保险**：`检测到保险行业，专用估值方法论（内含价值 EV/NBV 模型）暂缺，当前使用通用方法，结果参考性有限`。
- **军工**：`检测到军工行业，专用估值方法论（在手订单驱动 + 资产重估模型）暂缺，当前使用通用方法，结果参考性有限`。

### 术语说明

- **EV（Embedded Value，内含价值）**：保险公司现有有效保单与净资产所对应的经济价值，是保险估值的重要基础。
- **NBV（New Business Value，新业务价值）**：新签保险业务预计创造的价值，常用于衡量保险公司的新业务增长质量。
- **在手订单驱动**：军工企业的业绩与估值往往受已签约、待交付订单影响，不能仅靠静态利润倍数判断。
- **资产重估**：按资产的当前可实现价值而非历史账面价值评估企业价值，常与军工等重资产行业相关。

若行业信息缺失或未列入已识别的暂缺清单，报告仍会显示“原型未识别，使用通用方法集，置信度低”。请先补齐数据或人工覆盖原型，并结合业务事实复核。

---

## 附录：筹码分布（F-17）

筹码分布是技术面的一项辅助信息：它描述市场持仓成本的大致结构，帮助判断上涨或反弹时可能遇到的解套卖压。先同步数据，再离线查看技术报告：

```powershell
py -m apps.cli sync 600519
py -m apps.cli report tech 600519
py -m apps.cli report tech 600519 --json
```

报告有缓存且数据可用时，会出现类似区块：

```text
--- 筹码分布 ---
获利比例 42.5% | 套牢比例 57.5% | 平均成本 12.34 | 集中度(90%/70%) 8.2/4.1 | 高度控盘
```

`sync` 才会联网请求 AKShare 的 `stock_cyq_em` 并写入本地缓存；`report tech` 始终严格离线。筹码数据缺失或同步失败时，核心技术面评分与买卖信号仍会输出，只会省略该区块或附加警告。V1 中筹码字段不参与 `signal_score`，不能将“高度控盘”单独理解成买入依据。

### 术语说明

- **筹码分布**：按持仓成本汇总后的结构数据，不是逐个账户的真实持仓明细；本工具采用 AKShare/东方财富聚合口径，仅供交叉验证。
- **获利比例（winner_ratio）**：按该数据源口径估计的、当前处于浮盈状态的筹码比例。比例高不等于一定会上涨，也可能意味着短期获利了结压力。
- **套牢比例（trap_ratio）**：`100% - 获利比例`。比例较高时，价格反弹可能遇到回本卖出的阻力；它是风险提示，不是自动卖出信号。
- **平均成本（avg_cost）**：该数据源估计的整体持仓成本均值，可用于了解成本中心，不能替代支撑位、止损位或你的实际持仓成本。
- **90%/70% 集中度**：覆盖约 90%/70% 筹码成本区间的宽度指标；数值越小，成本越集中。默认按 90% 集中度将 `≤10%` 归为“高度控盘”、`≥30%` 归为“筹码分散”，中间为“较为集中”或“正常分布”。

请将筹码分布与趋势、量能、估值和风险清单一起判断。数据口径可能与券商 App 不同，也不构成投资建议。

---

## 附录：交易记录与复盘归因（trade record / report trade-review）

交易记录仅保存在本地数据库。录入买卖后，可严格离线生成基于 FIFO（先进先出）配对的已实现收益统计：

```powershell
# 录入买入；可选关联当时已提交的 Checklist ID
py -m apps.cli trade record 600519 buy 1500 100 --date 2026-08-01 --checklist-id 42 --note "估值与趋势均满足"

# 录入卖出
py -m apps.cli trade record 600519 sell 1620 100 --date 2026-08-20 --note "达到目标价"

# 查看全部标的的本地复盘，或限定一只股票
py -m apps.cli report trade-review
py -m apps.cli report trade-review --code 600519 --json -o reports/600519_trade_review.json
```

`trade record` 会拒绝非 A 股代码、非 `buy`/`sell` 动作、非正价格和非正数量，避免无效数据进入统计。`report trade-review` 不联网，只读取本地交易和 Checklist 记录；没有交易时会提示先录入记录。

### 术语说明

- **FIFO 胜率**：按同一股票的交易时间顺序，让最早买入的数量优先与卖出数量配对。每个已平仓配对的收益率大于 0 即为盈利；胜率 = 盈利配对数 / 全部已平仓配对数。尚未卖出的数量不计入分母。
- **部分平仓**：一笔买入可被多笔卖出分拆配对。例如买入 100 股后分两次各卖出 50 股，会得到两笔独立的已实现收益记录。
- **Badcase 归因**：当买入关联的 Checklist 是“合规”（`passed=True`），但该已平仓配对的收益率低于 -8% 时，系统标记为 Badcase。这是用于复盘“当时流程合规却仍出现显著亏损”的样本，不是对未来收益的预测。
- **降级提示**：没有关联且可解析的 Checklist 记录时，系统仍会输出 FIFO 胜率和平均收益率，但不会判断 Badcase，并会明确提示该限制。

交易记录与复盘报告仅辅助回顾决策过程，不构成投资建议，也不会自动下单或修改 Checklist 规则。

---

## 附录：持仓组合报告（report portfolio）

当你准备新开仓或加仓时，先检查这笔假设交易会不会让组合过度集中。`report portfolio` 严格离线：它复用 `trade record` 中尚未被 FIFO 卖出配对的买入数量，并读取本地价值快照价格；不会联网、不会下单，也不会写入交易记录。

先同步涉及标的的本地价格，并录入交易记录：

```powershell
py -m apps.cli sync 600519
py -m apps.cli sync 600000
py -m apps.cli trade record 600519 buy 1500 100 --date 2026-08-01
py -m apps.cli trade record 600000 buy 10 1000 --date 2026-08-01
```

查看整体组合，或将结果保存为文本 / JSON：

```powershell
py -m apps.cli report portfolio
py -m apps.cli report portfolio -o reports/portfolio.md
py -m apps.cli report portfolio --json -o reports/portfolio.json
```

在真正下单前，模拟增加指定数量的股票：

```powershell
py -m apps.cli report portfolio --code 600519 --add-quantity 100
```

模拟输出会固定注明“以下为模拟计算，不代表任何实际交易操作”。没有未平仓交易记录时，命令会提示先用 `trade record` 录入；某持仓缺少本地价格或价格超过 7 天未更新时，报告仍会给出可计算部分，但会提示先 `sync`。

### 术语说明

- **持仓集中度**：一只股票或前 N 只股票的市值占组合总市值的比例。例如，组合总市值 10 万元、其中某股票市值 3 万元，则该股票持仓集中度为 30%；前 3 只合计 7 万元，则“前 3 大持仓占比”为 70%。比例高不必然错误，但意味着这几只股票的涨跌对组合影响更大。
- **行业暴露度**：组合中同一行业持仓市值的合计比例。例如，银行股合计市值 4 万元、组合总市值 10 万元，银行行业暴露度为 40%。若模拟继续买入银行股，报告可帮助你看到该比例是否进一步上升。
- **行业粗匹配**：当前按本地快照中的原始行业文字精确分组，如“银行”与“股份制银行”可能被拆成不同组。因此行业暴露度仅作粗估，可能低估实际同行业集中风险，不能替代标准行业分类或专业风险模型。
- **前 N 大持仓占比**：按市值排序后前 N 只股票的合计权重。它比只看单一股票更容易发现“多数资金压在少数标的上”的情形。

该报告不计算股价收益率相关系数、协方差矩阵、有效前沿或任何组合优化建议；请结合价值、技术、情绪和自己的风险承受能力独立决策。

---

## 附录：市场情绪 V1（涨跌停家数比与恐慌贪婪代理）

市场情绪是全市场维度，不随股票代码变化。先联网同步一次市场级快照，再严格离线查看指定股票的报告；股票代码用于报告标识，并为后续个股级情绪指标预留。

```powershell
# 联网：仅同步全市场情绪数据；不接受股票代码
py -m apps.cli sync market

# 严格离线：查看最新市场快照对应的情绪报告
py -m apps.cli report sentiment 600519
py -m apps.cli report sentiment 600519 --json -o reports/600519_sentiment.json

# 严格离线：三维联合解读（价值 + 技术 + 情绪）
py -m apps.cli report dual 600519
```

`report sentiment` 无本地快照时会提示先执行 `sync market`，不会自行联网。情绪数据缺失时，`report dual` 会明确显示“情绪面数据缺失，本次报告仅基于价值+技术双维”；价值评级和综合信号的既有计算不受影响。

### 术语与示例

- **涨跌停家数比**：`涨停家数 / (涨停家数 + 跌停家数)`。例如涨停 50 家、跌停 10 家时为 `50 / 60 = 83.3%`；它反映当日极端上涨相对极端下跌的市场广度，不代表某只股票必涨。
- **恐慌贪婪代理指数**：本工具自建的 0–100 分代理指标，默认组合涨跌停家数比、两融余额环比和全市场换手率分位。例如指数 86 可标为“极度贪婪”，指数 15 可标为“极度恐慌”。它不是官方指数，权重尚未经历史回测校准。
- **分量缺失降级**：若两融接口暂时不可用，指数会用剩余的涨跌停和换手率分量重新归一化计算，并在报告显示警告；若所有分量缺失，则指数显示 `N/A`，不将缺失误作 0。
- **三维联合解读**：情绪“极度恐慌”且价值面“低估”时，报告会提示可关注逆向机会，但仍需技术面企稳确认；情绪“极度贪婪”且技术面强势时，报告会提示过热和回调风险。

> **重要：** 情绪面结论不得单独作为买卖依据。必须结合 `report dual <代码>` 的价值、技术、情绪三维联合解读，并自行承担投资决策后果。
