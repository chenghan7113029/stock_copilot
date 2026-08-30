# 竞品参考 — GitHub 开源投资助手调研

> 最后更新：2026-08-29  
> 用途：对照外部成熟项目，识别 stock_copilot 可借鉴的能力与应规避的方向。  
> 权威需求来源仍为 [product-overview.md](product-overview.md)、[roadmap-todo.md](roadmap-todo.md)。

## 变更记录

| 日期 | 摘要 |
|------|------|
| 2026-08-29 | §4.1 Investor Persona：**已立项并实现中** `add-confrontation-persona-stress-test`（三固定 lens） |
| 2026-08-29 | 决策护航 V2 OpenSpec 立项（narrate-api / declaration / persona-stress-test）；§7 后续动作更新 |
| 2026-08-29 | 本地镜像：§9 所列 12 个 GitHub 项目已 shallow clone 至 `ref/`（不入库） |
| 2026-08-29 | 初稿：GitHub 开源投资助手分层梳理、与 stock_copilot 差异对照、可借鉴 Feature 映射与 ROI 排序 |

---

## 1. 调研背景与范围

本次调研针对 GitHub 上相对成熟的开源「投资助手 / 多 Agent 投研」项目，对照 stock_copilot 的产品定位：

- **三维信息收集** — 价值面 + 技术面 + 情绪面
- **决策护航审计** — 红蓝对抗、Checklist、首开仓视角、锚定防御
- **全周期闭环** — 交易前分析 → 交易中审计 → 交易后复盘
- **明确非目标** — 不替用户下单、不承诺收益、数值以确定性模块为准

调研目的：找出外部项目中**值得借鉴的 feature**，并映射到现有 Roadmap（PO-* / T-* / F-*），而非照搬自动交易或多 Agent 黑盒信号。

---

## 2. stock_copilot vs 主流开源项目

| 维度 | stock_copilot | 多数 GitHub 热门项目 |
|------|---------------|----------------------|
| 核心目标 | 个人决策 Copilot，提高决策质量 | 多 Agent 研报 / 模拟交易 / 自动信号 |
| 独特优势 | Checklist 硬拦截、首开仓视角、锚定防御、FIFO 复盘 | 多 Agent 编排、回测、选股发现 |
| 数据哲学 | **确定性计算 + LLM 叙述分离** | 往往 LLM 直接给买卖结论 |
| 市场 | A 股深度（23 种估值、Tushare/Baostock） | 美股为主，A 股多为 fork/汉化 |
| 明显缺口 | Web UI、宏观/政策层、龙虎榜/解禁、命题回测 | 决策审计闭环、价值引擎深度 |

**结论：** 外部项目多在拼「多 Agent 出研报 / 模拟交易 / 自动信号」；stock_copilot 的稀缺性在于 **「决策过程审计 + 确定性价值引擎 + 全周期复盘」**。

---

## 3. 成熟度分层：值得关注的项目

### 3.1 Tier 1 — 高星、架构成熟（偏多 Agent 研报/模拟）

| 项目 | Stars（约） | 定位 | 与 stock_copilot 关系 |
|------|-------------|------|------------------------|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | ~85k | LangGraph 多 Agent 交易研究框架 | 红蓝辩论、回测、反思记忆 — 架构参考 |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | ~63k | 19 个「投资大师 persona」+ 回测模拟 | Persona 压力测试、Fund YAML 配置 |
| [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | ~7.8k | 机构级 equity research 自动化 | 13 章报告结构、数值溯源、证据链 |

### 3.2 Tier 2 — A 股特化（与数据源/场景更近）

| 项目 | 特点 |
|------|------|
| [OoShowboatoO/TradingAgents-astock](https://github.com/OoShowboatoO/TradingAgents-astock) | +政策分析师、游资追踪、解禁监控；T+1/涨跌停规则 |
| [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | 中文 Web、自选股、新闻质量过滤、Docker |
| [HuaYaoAI/FinGenius](https://github.com/HuaYaoAI/FinGenius) | Research–Battle 双子星；舆情/游资/筹码/大单异动 Agent |

### 3.3 Tier 3 — 方法论创新（星数不高但思路贴合）

| 项目 | 特点 |
|------|------|
| [turtlequant/thesis-backtester](https://github.com/turtlequant/thesis-backtester) | 把「价值陷阱/高股息可持续」等定性判断做成可回测命题 |
| [tohnee/investagent](https://github.com/tohnee/investagent) | 产业链研究 → 巴菲特 8 问 → 深度分析 → 辩论 → 回测 流水线 |
| [muye1202/VerumTrade](https://github.com/muye1202/VerumTrade) | Discovery 选股 + 证据包 + 决策 trace 可视化 |

### 3.4 其他提及项目（参考级）

| 项目 | 说明 |
|------|------|
| [yashasg/AlpacaTradingAgent](https://github.com/yashasg/AlpacaTradingAgent) | TradingAgents + Alpaca 实盘/纸面 — **与 stock_copilot 非目标冲突** |
| [Mai0313/TradingAgents](https://github.com/Mai0313/TradingAgents) | TradingAgents fork：CLI 回测、reflect/BM25 记忆、结构化 TradeRecommendation |
| [jack139/Vibe-Trading](https://github.com/jack139/Vibe-Trading) | NL→策略、多回测引擎、跨会话记忆 — 偏 quant 平台 |

---

## 4. 按 Roadmap 缺口映射可借鉴 Feature

### 4.1 决策护航增强（PO-03 ~ PO-05）

**来源：** TradingAgents / ai-hedge-fund

| 借鉴点 | 说明 | stock_copilot 现状 |
|--------|------|-------------------|
| 结构化辩论轮次 | Aggressive → Conservative → Neutral 固定轮换，有终止条件 | 红蓝 Skill 版已有；可补轮次 + 终止 + Judge schema |
| TradeRecommendation Schema | signal / position_fraction / stop_loss / time_horizon / confidence | 可嵌入 Checklist 输出，不变成自动下单 |
| Investor Persona 压力测试 | Buffett / Lynch / Burry 等同票不同 lens | **已立项**：`add-confrontation-persona-stress-test`（V1 三固定 lens：`value_quality` / `trend_momentum` / `risk_governor`；CLI `report persona-stress`） |
| Post-trade Reflection + BM25 Memory | 交易后反思写入记忆，影响下次分析 | FIFO 复盘已有；规则反哺 Checklist 仍偏人工 |

**建议优先级：高** — 与 PO-03、PO-09 直接衔接，不违背「不自动交易」。

---

### 4.2 情绪/政策/治理信息面（PO-11 ~ PO-14）

**来源：** TradingAgents-astock / FinGenius

| 借鉴点 | 对应 Roadmap |
|--------|--------------|
| 政策分析师 Agent — 监管/产业政策/窗口指导 | PO-11 宏观/政策 |
| 游资追踪师 — 龙虎榜、大单、主力行为 | PO-13 龙虎榜 |
| 解禁监控师 — 限售解禁、减持、质押 | PO-11 治理事件 |
| 舆情 Agent 算因子 — 新闻/社媒情绪量化 | PO-14 文本情绪 |

实现约束：仍走确定性数据层（Tushare/缓存），LLM 只做解读；须与价值/技术联合呈现（见 product-overview §5.1.3）。

**建议优先级：高** — 填 product-overview §4.3 开放项。

---

### 4.3 报告质量与可解释性

**来源：** FinRobot

| 借鉴点 | 价值 |
|--------|------|
| 13 章固定研报结构 | 深度报告、IC memo、章节化输出 |
| Numeric Provenance | 每个数字带来源字段/API |
| Evidence Links | 结论 → 证据 → 原始数据三级链 |

与现有 `explainers.py`、`report summary`、飞书 dual 推送可结合，升级为「章节模板 + 溯源 footnote」。

**建议优先级：中**

---

### 4.4 定性判断的历史验证（命题回测）

**来源：** thesis-backtester

| 借鉴点 | 与 stock_copilot 的契合 |
|--------|-------------------------|
| DAG 分步分析引擎 | 后一步依赖前一步结论，减少 LLM 跳步 |
| 命题回测 | 「低 PE 是便宜还是价值陷阱？」用历史截面验证 |
| 回避信号 > 选股信号 | V6 案例：排雷 alpha 显著高于选股 alpha |
| 三层生产架构 | 季报驱动评估 + 日频价格监控 + 触发式资讯校验 |

与现有 `value_trap_alert`、23 种估值互补：补「价值判断在历史上是否靠谱」的验证层（离线截面，不碰实盘）。

**建议优先级：中高** — 强化可解释 + 可验证，符合 agent-engineering-quality 三层防御。

---

### 4.5 主题/产业链研究（PO-11 延伸）

**来源：** investagent

| 借鉴点 | 场景 |
|--------|------|
| Serenity 产业链 8 层映射 | 「研究 AI 半导体赛道」→ 候选池 |
| Buffett 8 问筛选 | 护城河/管理层/安全边际结构化问答 |
| 自然语言意图路由 | 「研究 XX 赛道」vs「深度分析 XXX」 |

适合作为单票分析之上的「自上而下」入口。

**建议优先级：中** — Phase 4+ 或独立 OpenSpec。

---

### 4.6 选股发现

**来源：** VerumTrade / TradingAgents-CN

| 借鉴点 | 说明 |
|--------|------|
| Discovery Mode 多阶段筛选 | 催化剂 → 主题 → 评分 → 深度分析 |
| Evidence Pack + Thesis Card | 候选股附带证据摘要 |
| 自选股 + 分组跟踪 | 持续监控而非一次性报告 |

若产品边界扩到「发现」，值得立项；若坚持「已知标的 deep dive + 审计」，可只做轻量 watchlist 触发（已有 `feishu push`）。

**建议优先级：低~中**

---

### 4.7 工程/产品体验（PO-08 Web 待建）

**来源：** TradingAgents-CN / ai-hedge-fund

| 借鉴点 | 说明 |
|--------|------|
| Web 配置界面 + Docker | 降低 CLI 门槛 |
| 实时进度 / 流式 Agent 状态 | 长分析体验 |
| 报告导出 PDF/Docx | 与飞书 push 互补 |
| Checkpoint Resume | 多 Agent 长任务断点续跑 |

**建议优先级：中**

---

## 5. 建议不要照搬的方向

对照 [product-overview.md](product-overview.md) §8.3 非目标：

| 能力 | 代表项目 | 为何不贴 stock_copilot |
|------|----------|------------------------|
| 实盘/纸面自动下单 | AlpacaTradingAgent, Vibe-Trading | 与「不替用户下单」冲突 |
| 纯 LLM 买卖信号 | 部分 TradingAgents 用法 | 违背确定性计算优先 |
| 7 引擎量化回测 + 策略 codegen | Vibe-Trading | 偏 quant 平台，偏离决策审计 |
| 19 Agent 全自动 Fund | ai-hedge-fund v2 | 可借鉴 persona/回测，不宜做成自动 Fund |

---

## 6. ROI 排序：最值得借鉴 Top 8

结合已交付能力（Checklist、首开仓、双轨、23 估值、飞书 push）与 [roadmap-todo.md](roadmap-todo.md) 缺口：

| 排序 | 借鉴方向 | 主要来源 | 映射 |
|------|----------|----------|------|
| 1 | A 股特化 Agent 角色（政策/游资/解禁） | astock, FinGenius | PO-11 ~ PO-13 |
| 2 | 命题回测（定性判断历史验证） | thesis-backtester | 价值面 + value_trap |
| 3 | Post-trade Reflection → Checklist 规则库 | TradingAgents reflect | PO-09 |
| 4 | Investor Persona 压力测试 | ai-hedge-fund | PO-03 升级 |
| 5 | 报告章节 + 数值溯源 | FinRobot | report summary / 飞书 |
| 6 | DAG 分步分析引擎 | thesis-backtester, thinkdag | agent-engineering-quality |
| 7 | Web + 进度流式 + 自选股监控 | TradingAgents-CN | PO-08 |
| 8 | 产业链/主题研究流水线 | investagent | PO-11 延伸 |

---

## 7. 后续动作（可选）

以下已立项 OpenSpec（2026-08-29，见 [roadmap-todo.md](roadmap-todo.md) §2.4）：

1. **`add-confrontation-narrate-api`** — API 版红蓝互驳 + numbered evidence + `ConfrontationRecord`
2. **`add-confrontation-declaration`** — 结构化 declare（须引用 evidence 序号）+ `--confrontation-id` 关联 Checklist/trade
3. **`add-confrontation-persona-stress-test`** — 三 persona lens 压力测试（对抗单框架思维）

仍待 propose：`add-entry-check-response`、`add-trade-review-rule-hints`（见 roadmap §2.4.2）。

---

## 8. 相关文档

| 文档 | 说明 |
|------|------|
| [product-overview.md](product-overview.md) | 产品定位与非目标 |
| [roadmap-todo.md](roadmap-todo.md) | 功能待办与 PO-* 状态 |
| [../agent-engineering-quality.md](../agent-engineering-quality.md) | 确定性计算与 LLM 协作规范 |
| [../design/references/](../design/references/) | 本地 ref/ 参考实现分析报告 |

---

## 9. 本地参考镜像（`ref/`）

> `ref/` 在 `.gitignore` 中，**只读参考、禁止 import 进 src**。更新方式：`git -C ref/<dir> pull`，或删除目录后重新 `git clone --depth 1`。

| GitHub | 本地目录 | 文档 § |
|--------|----------|--------|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | `ref/TradingAgents/` | §3.1 |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | `ref/ai-hedge-fund/` | §3.1 |
| [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | `ref/FinRobot/` | §3.1 |
| [OoShowboatoO/TradingAgents-astock](https://github.com/OoShowboatoO/TradingAgents-astock) | `ref/TradingAgents-astock/` | §3.2 |
| [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | `ref/TradingAgents-CN/` | §3.2 |
| [HuaYaoAI/FinGenius](https://github.com/HuaYaoAI/FinGenius) | `ref/FinGenius/` | §3.2 |
| [turtlequant/thesis-backtester](https://github.com/turtlequant/thesis-backtester) | `ref/thesis-backtester/` | §3.3 |
| [tohnee/investagent](https://github.com/tohnee/investagent) | `ref/investagent/` | §3.3 |
| [muye1202/VerumTrade](https://github.com/muye1202/VerumTrade) | `ref/VerumTrade/` | §3.3 |
| [yashasg/AlpacaTradingAgent](https://github.com/yashasg/AlpacaTradingAgent) | `ref/AlpacaTradingAgent/` | §3.4 |
| [Mai0313/TradingAgents](https://github.com/Mai0313/TradingAgents) | `ref/TradingAgents-Mai0313/` | §3.4 |
| [jack139/Vibe-Trading](https://github.com/jack139/Vibe-Trading) | `ref/Vibe-Trading/` | §3.4 |

**克隆记录（2026-08-29）：** 上述 12 项均已 `git clone --depth 1` 完成。`ref/` 内另有历史参考项 `daily_stock_analysis/`、`valueinvest/`、`FinanceToolkit/`（见 [product-overview.md](product-overview.md) §9）。
