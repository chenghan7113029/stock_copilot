# Propose List（待 apply 的 OpenSpec change 清单）

> 生成时间：2026-07-27
> 来源：`docs/mrd/roadmap-todo.md` 全量待开发项梳理
> 范围：P0 + P1 + P2 + 已就绪的技术面/价值面增强项（`T-1`/`PO-11`/`E` 状态早于「待建」，本轮不生成 proposal，见文末）
> 状态：**P0+P1+P2 已全部 apply（代码+测试+user-guide）；归档任务可另行 `/opsx-archive`。V2 项未在本轮 apply。**
> 用法：`/opsx-apply <change-name>` 开始实现；实现完成后 `/opsx-archive <change-name>`

---

## P0（产品级最高优先级）

| Change 名称 | roadmap ID | 简介 | validate |
|---|---|---|---|
| `add-stock-dashboard` | PO-01 + PO-08 | CLI 单页看板 `report dashboard`：一次性汇总价值/技术/情绪(占位)/Checklist(占位)/综合摘要；V1 只做 CLI 文本版，Web 明确推迟到 REST API 就绪；维度缺失时优雅降级而非整体报错 | ✅ |
| `add-llm-comprehensive-report` | PO-02 | 直接消费已冻结的 `common.llm.narrate()`，把 `DualTrackReport` 打包为 evidence 生成 `summary/key_points/risks` 结构化叙事；新增独立命令 `report summary --narrate`（不改 `report dual` 的离线契约）。**落地后 `add-llm-narrative-core` 将从"冻结"变为"解冻"** | ✅ |
| `add-decision-checklist` | PO-04 | 新增 `ChecklistRecord` 表 + 纯规则校验（价值理由≥2条、非可得性单一来源启发式）+ CLI `checklist submit/show`；校验失败硬拦截但仍落库留痕 | ✅ |
| `add-fresh-entry-check` | PO-05 | 新增最小化 `PositionRecord` 持仓表（字段严格限定 code/cost_price/shares）+ CLI `entry-check`，隐藏成本价/盈亏%，改用"若无仓位是否仍愿买入"框架提问 | ✅ |

## P1

| Change 名称 | roadmap ID | 简介 | validate |
|---|---|---|---|
| `add-sentiment-module` | PO-06 | 情绪面量化 V1：涨跌停家数比 + 自建恐慌贪婪代理指数两个核心指标；不改 `DualTrackAnalyzer` 命名/CLI 契约，新增 `sentiment_result` 字段并强制生成三维联合解读文本 | ✅ |
| `add-anchor-defense` | PO-07 | 呈现层增强（非新计算）：复用已存在的 `price_percentile` 包装为定性分档描述 + 历史最高价默认隐藏（opt-in 展示+警示）；成本价隐藏推迟给 `add-fresh-entry-check` | ✅ |
| `add-value-trap-high-alert` | T-2 | value_trap High 风险时新增独立醒目警示字段 `value_trap_alert` + confidence 一级降级，CLI 头部强制渲染；不改变现有 `assessment` 语义，已核查红蓝对抗无联动风险 | ✅ |
| `add-industry-prototype-router` | T-7 | 复用已接入的 Tushare `industry` 字段做"行业→原型"优先映射，短路于财务启发式之前；**修复真实 bug**：保险股（如平安）高负债率被现有杠杆率启发式误判为"银行" | ✅ |

## P2

| Change 名称 | roadmap ID | 简介 | validate |
|---|---|---|---|
| `add-trade-review-attribution` | PO-09 | 最小 `TradeRecord` 交易记录表 + FIFO 胜率统计；Badcase 归因强依赖尚未实现的 `add-decision-checklist`（软引用降级，无数据时仍可输出纯价格胜率）；"规则反哺"不做自动化 | ✅ |
| `add-portfolio-correlation` | PO-10 | 持仓集中度 + 行业暴露度粗估；**直接复用 `add-trade-review-attribution` 的 `TradeRecord` 表**，不新建第三套持仓模型；明确排除协方差矩阵/组合优化 | ✅ |
| `add-chip-distribution` | F-17 | 接入 AKShare `stock_cyq_em`，新增 `winner_ratio`/`trap_ratio` 等结构化字段；独立数据管道（不复用/扩展 90 天 K 线窗口）；V1 不纳入 `signal_score`（口径有争议） | ✅ |
| `add-prototype-override-persistence` | T-8 | 新增 `prototype_overrides` 表 + Repo + CLI `value override` 命令，落地 VA-CLS-2；三层路由优先级"人工覆盖 > 行业映射 > 财务启发式"，与 `add-industry-prototype-router` 代码零耦合可任意顺序实施 | ✅ |
| `add-prototype-fallback-message` | T-15 | `unknown` 原型分支从笼统"原型未识别"升级为精确"检测到保险行业，EV/NBV 方法论暂缺"等文案；**强依赖 `add-industry-prototype-router`**（复用其行业识别字典，否则需重复建设，不推荐） | ✅ |

## V2 / 长期项

| Change 名称 | roadmap ID | 简介 | validate |
|---|---|---|---|
| `add-pattern-recognition` | F-18 | 纯规则代码识别十字星/锤头/吊颈/看涨看跌吞没 4 类经典形态；结果作为独立字段 `candlestick_patterns` 展示，不进入 `signal_score`/`signal_reasons`，避免污染已验证的评分体系 | ✅ |
| `add-bollinger-bands` | F-19 | 布林带（中/上/下轨+带宽百分位）计算，新增 `BollingerStatus` 5 级枚举（对齐 `VolumeStatus`/`RSIStatus` 命名风格）；V1 只做指标+单状态判断，跨指标组合信号留作 Open Question | ✅ |

---

## 本轮跳过（状态早于「待建」，建议先用 `openspec-explore` 澄清后再 propose）

| roadmap ID | 名称 | 原因 |
|---|---|---|
| T-1 | 安全边际按原型差异化 | 状态「待设计」，尚无具体方案方向，需先 explore |
| PO-11 | 宏观/政策/治理事件层 | 状态「待规划」，需求范围未定 |
| E | REST API（`add-value-api`） | change 名本身标注「待定」，依赖 Web 层整体决策 |

---

## 依赖关系提醒（跨 change，apply 时留意顺序）

- **持仓数据只建一次**：`add-trade-review-attribution` 是唯一定义持仓/交易记录模型（`TradeRecord`）的一方；`add-portfolio-correlation` 直接复用该表，**不要**为持仓数据单独再建表。`add-fresh-entry-check` 的 `PositionRecord` 是独立的最小成本价表，字段更窄（code/cost_price/shares），与 `TradeRecord` 定位不同，若后续发现重叠可在 apply 时合并评估。
- **行业路由链（建议顺序）**：`add-industry-prototype-router` → `add-prototype-override-persistence`（覆盖优先级最高，代码零耦合可并行）→ `add-prototype-fallback-message`（降级文案精度依赖行业识别，强依赖前者）
- **Checklist → 复盘归因**：`add-decision-checklist` 建议先于 `add-trade-review-attribution` 实施，否则后者的 Badcase 归因会降级为纯价格胜率统计（软引用 `checklist_id`，不阻塞但价值打折）
- **LLM 解冻**：`add-llm-comprehensive-report` 是 `add-llm-narrative-core`（已冻结）的首个消费方，apply 该 change 时需同步把 `openspec/changes/add-llm-narrative-core/proposal.md` 顶部的"已冻结"状态说明移除，并推进其 §10.3 归档任务
- **看板依赖多方**：`add-stock-dashboard` 会引用情绪面（`add-sentiment-module`）与 Checklist（`add-decision-checklist`）的结果，但设计上对两者缺失有降级处理，**不强制**要求先完成才能 apply

---

## 建议 apply 顺序（按 ROI 与依赖关系）

1. `add-llm-comprehensive-report`（解冻已有 LLM 基建，性价比最高）
2. `add-decision-checklist`（P0 核心，且是复盘归因的前置）
3. `add-industry-prototype-router`（修复真实 bug：保险股误判为银行）
4. `add-prototype-override-persistence` / `add-prototype-fallback-message`（跟随 3）
5. `add-value-trap-high-alert`（独立，随时可做）
6. `add-fresh-entry-check` → `add-anchor-defense`（沉没成本/锚定防御，均较小范围）
7. `add-stock-dashboard`（汇总呈现层，此时情绪面/Checklist 已有一定基础）
8. `add-sentiment-module`（整模块，工作量较大）
9. `add-trade-review-attribution` → `add-portfolio-correlation`（复盘链路，依赖 Checklist）
10. `add-chip-distribution` / `add-pattern-recognition` / `add-bollinger-bands`（技术面增量，独立于上述所有链路，可随时穿插）
