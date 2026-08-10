## Context

`product-overview.md` §4.3 与 §10 都把"持仓组合相关性"标注为**开放项**，没有既定的方法论范围（不像价值面/技术面有明确的方法论清单），这意味着本 change 的 Non-Goals 部分需要格外明确划清边界，避免把机构级量化组合管理的方法论（协方差矩阵、有效前沿、风险平价等）误当作个人投资辅助工具的 V1 范围。

**关键前提**：本 change 与 `add-trade-review-attribution`（同批提出）都需要回答"用户当前持有什么"这个问题。若两个 change 独立设计各自的持仓表，会造成：
- 数据不一致（用户在两处分别录入交易记录，容易遗漏或对不上）
- 维护成本翻倍（两套 Repo、两套 CRUD、两套 Input Guard）

因此本 change 的架构前提是：**`add-trade-review-attribution` 提出的 `TradeRecord` 表是本 change 的唯一持仓数据来源**，本 change 不重新发明。这也回应了 `product-overview.md` 在多处（如 §4.3、本 change、`add-trade-review-attribution`）反复出现"持仓"概念但从未有一个统一的持仓数据模型 change 的问题——本设计选择"不新建 `add-position-tracking` 专门 change"，而是把持仓数据的定义权交给 `add-trade-review-attribution`（因为它是同批 4 个 change 中最先需要"交易记录"这个概念的一方，持仓天然是交易记录的派生视图：当前持仓 = 历史交易记录中未被平仓的部分），`add-portfolio-correlation` 与未来任何需要"持仓"概念的功能都应复用该表，不应再各自定义。

价值面数据（`src/dao/models.py::StockSnapshot`）已经包含 `industry` 字段（自由文本，来自 AKShare，如"银行""白酒"），这是本 change"行业暴露度粗估"可以直接复用的现成数据，无需新增数据源——但 `roadmap-todo.md` T-7「行业代码映射 Router」明确标注该字段目前是自由文本而非标准化的申万/中信行业代码分类体系，存在"字符串完全匹配才能归为同行业"的粗糙度问题（如"银行"与"股份制银行"文本不同但语义上应属同行业）。本 change 接受这一已知局限作为 V1 的合理简化，不等待 T-7 完成再启动。

## Goals / Non-Goals

**Goals:**
- 复用 `TradeRecord` 表推导当前持仓（未平仓 `BUY` 数量 × 最新价格 = 持仓市值），不新建持仓表
- 计算最基础的集中度指标：单票占比、前 N 大持仓占比
- 提供"同行业暴露度"作为"相关性"的代理指标（直接复用已有 `industry` 字段做字符串分组，不引入新的行业分类体系）
- 支持"若买入/加仓某标的 N 股，对组合集中度的边际影响"模拟（不需要真实下单，只是数值模拟）

**Non-Goals:**
- **不做协方差矩阵、均值方差组合优化、有效前沿、风险平价、Beta 分解**等机构级量化方法——这些方法需要历史收益率序列的稳定协方差估计、通常还需要考虑约束优化求解器，其复杂度、数据需求（长历史收益率序列的高质量对齐）与个人决策辅助工具的定位不匹配，明确排除
- **不做真正的统计学"相关性"（如皮尔逊相关系数矩阵）**：计算两两股票历史收益率相关系数在技术上可行（复用已有 `Kline` 数据），但"系数矩阵"本身不能直接回答用户"这笔交易会不会让我风险过于集中"的问题，需要额外的解释层（如"平均相关系数"、"聚类"），V1 认为"同行业暴露度"是一个更直观、无需额外解释层就能被非量化背景用户理解的代理指标，先做这个更具行动力的版本
- 不建立独立的持仓/组合数据表（复用 `add-trade-review-attribution` 的 `TradeRecord`）
- 不等待 `roadmap-todo.md` T-7（行业代码标准化）完成，接受当前自由文本 `industry` 字段的粗糙匹配作为 V1 已知局限
- 不做实时组合估值更新/推送（V1 是按需查询的 CLI 命令，不是常驻监控服务）

## Decisions

### 决策 1：持仓数据来源——复用 `add-trade-review-attribution` 的 `TradeRecord`，不新建持仓表

**选择**：`PortfolioAnalyzer` 依赖 `trade_record_repo.find_open_positions()`（`add-trade-review-attribution` §1 已定义的方法）获取当前持仓列表（`code` → 剩余未平仓数量），结合最新行情价格（复用 `data_provider`/本地价值快照的 `current_price`）计算持仓市值。

**理由**：见 Context。这是本 change 明确要求写入 proposal/design 的交叉依赖决策——`product-overview.md` §10 开放问题原文提到"持仓组合相关性"但没有说明持仓数据从哪来；如果不在本 change 中明确"复用哪张表"，实施时很可能因为"图省事"而临时建一张新表，制造第三套持仓数据模型。本设计通过显式声明依赖关系提前堵住这个口子。

**备选方案**：
- **新建独立的 `PositionRecord`/`add-position-tracking` change 作为两者共同的基础设施**——技术上更"整洁"（单一职责：一个 change 专门管持仓），但会引入第三个 change 到本已复杂的依赖网络中（`add-trade-review-attribution` 依赖它、本 change 也依赖它、且 `add-trade-review-attribution` 本身已经需要"交易记录"这个更底层的概念，"持仓"是"交易记录"的派生视图而非独立概念，没有必要为一个可推导视图单独建表）。拒绝，选择让 `add-trade-review-attribution` 一并承担"持仓"概念的数据源角色。
- **本 change 独立建一张只读的 `code + quantity` 极简持仓表**——拒绝，用户需要在两处分别维护数据（一处是完整交易记录，一处是当前持仓快照），容易产生不一致，且"持仓"完全可以从"交易记录"实时推导，没有独立存储的必要性。

### 决策 2：集中度指标——单票占比 + 前 N 大占比，不做风险加权

**选择**：
- `single_stock_weight(code) = position_value(code) / portfolio_total_value`
- `top_n_concentration(n=3) = sum(position_value for top n by value) / portfolio_total_value`

均为简单的市值占比计算，不引入波动率加权或风险贡献度（risk contribution）等更复杂的风险度量。

**理由**：市值占比是最直观、最容易被非量化背景用户理解的集中度指标，直接回应 MRD"单票决策对整体组合的影响"这一朴素问题（"这只股票现在占了我多少仓位"）。风险加权集中度（如按波动率调整后的有效仓位）虽然更"精确"，但引入了对历史波动率估计的依赖和额外的方法论解释成本，与 Non-Goals 中排除的机构级方法一脉相承，V1 不做。

**备选方案**：赫芬达尔指数（HHI，机构组合管理常用的集中度量化指标，公式 `Σ(weight_i)²`）——可以作为 `top_n_concentration` 的补充展示（数学上更严谨的单一数字），但对非量化背景用户不够直观（"HHI=0.35 是什么意思"不如"单票占比 35%"直接），V1 选择更直白的表达方式，不排除未来在 `--json` 输出中附加 HHI 作为程序化消费的补充字段（留作实现阶段的可选增量，不写入 design 的强制范围）。

### 决策 3：行业暴露度粗估——直接复用 `StockSnapshot.industry` 自由文本分组

**选择**：`industry_exposure()` 按 `industry` 字符串精确匹配对当前持仓分组，计算目标股票所属行业在组合中的现有市值占比（不含目标股票本身，因为目标股票可能尚未持有，是"若买入"的前瞻性问题）。

**理由**：这是本 change 与既有价值面数据的复用点——`industry` 字段已经在 `sync <code>` 时被采集并落库（`stock_snapshots.industry`），不需要新增数据源或新的 API 调用。虽然自由文本匹配存在"银行"与"股份制银行"这类语义相同但字符串不同从而被错误分为两组的已知局限（详见 Risks），但作为 V1 的"粗估"（proposal 中已用"粗估"一词明确预期精度），这个局限是可接受的起点。

**备选方案**：等待 `roadmap-todo.md` T-7（行业代码映射 Router，SW/CS 行业标准分类）完成后再实现行业暴露度——拒绝，T-7 目前"待建"且无明确排期，本 change 若无限期等待一个不确定何时交付的前置项，会导致本身已经是 P2 优先级的功能进一步延后；采用"先用现有粗糙数据交付一个能用的版本，待 T-7 交付后自然受益于更准确的行业分类"的增量演进策略更符合"先能用、再完整"的既定实施节奏（`roadmap-todo.md` §5 标题）。

### 决策 4：是否融合进 `DualTrackReport`——不融合，作为独立决策时点工具

**选择**：`report portfolio` 是独立 CLI 命令，不像情绪面（`add-sentiment-module`）那样被要求强制嵌入 `DualTrackReport` 联合呈现。

**理由**：MRD 对情绪面有明确的"禁止单独呈现"硬约束（§5.1.3），但对"持仓组合相关性"没有类似措辞——它被列在 §4.3"待补充信息面"和 §10"开放问题"中，性质更接近"决策护航"工具（类似"假设今日首开仓"PO-05：在用户即将做决策的时间点提供一个特定视角的检查），而不是"三维分析框架"里必须与价值/技术/情绪三者时刻联动的常驻分析维度。因此本 change 选择更轻量的独立命令形态，用户在准备下单前主动查询"这笔交易对我的组合意味着什么"，而不是每次分析单票都被动接收组合层面的信息（后者对尚未建仓或组合很简单的用户是不必要的噪音）。

**备选方案**：将 `portfolio_result` 作为 `DualTrackReport` 的第 N 个可选字段——拒绝，`DualTrackAnalyzer.analyze()` 当前的调用语境是"分析一只股票"，不天然知道"用户当前持仓"这个上下文（需要额外查询 `TradeRecord`），把组合信息强行塞进每次单票分析会让 `DualTrackAnalyzer` 承担超出其"双轨"定位的职责；保持独立命令使得二者可以独立演进、独立测试。

## Risks / Trade-offs

- **[风险] `industry` 自由文本分组可能把语义相同的行业错误拆分为多组（如"银行"vs"股份制银行"vs"城市商业银行"），导致行业暴露度被低估** → **缓解**：V1 明确标注该局限（`PortfolioAnalysisResult.warnings` 固定包含"⚠ 行业分类基于原始文本粗匹配，未做标准化归一，可能低估实际同行业暴露"）；根本解决依赖 `roadmap-todo.md` T-7，交叉引用记录在本 change 与 roadmap 中，不在本 change 内实现。
- **[风险] 持仓市值依赖"最新价格"，若某持仓标的近期未 `sync` 过，价格可能过期，导致组合估值失真** → **缓解**：复用既有 `StockDataProvider.get_stock_data_offline()`/`stock_snapshots` 的时效标注机制，`PortfolioAnalysisResult` 中为每个持仓标的携带 `price_as_of`（价格数据时间戳），价格过期（如超过 7 天，具体阈值实现时可配置）时在 `warnings` 中提示"该持仓价格数据已过期，建议先 sync"，不阻断计算但明确告知不确定性来源。
- **[风险] "若加仓 N 股"模拟是纯假设计算（不涉及真实下单），若用户误解为系统已经执行了交易** → **缓解**：CLI 输出固定包含"以下为模拟计算，不代表任何实际交易操作"的提示；命令参数命名为 `--add-quantity`（模拟）而非任何暗示真实操作的措辞。
- **[风险] 强依赖 `add-trade-review-attribution` 尚未实现时，本 change 完全无法启动（无持仓数据来源）** → **接受并显式声明**：本 change 的 Impact 部分已明确写出"应等待 `add-trade-review-attribution` 至少完成数据模型部分"，这是诚实的依赖声明而非试图绕过依赖去重新发明数据源。

## Migration Plan

- 无新增数据库表（复用 `add-trade-review-attribution` 的 `TradeRecord`），无迁移
- 回滚：删除 `src/service/portfolio/`、CLI 新增子命令即可，不影响 `TradeRecord` 表或其他既有功能
- 若 `roadmap-todo.md` T-7（行业标准化）未来落地，本 change 的 `industry_exposure()` 分组逻辑可以在不改变对外接口（`PortfolioAnalysisResult` 字段结构不变）的前提下平滑切换到标准化行业代码分组，属于内部实现升级，不需要本 change 预先设计切换开关

## Open Questions

- 是否需要在 V1 就提供 HHI（赫芬达尔指数）作为 `--json` 输出的补充字段？—— 不预先决定，若实现阶段发现成本很低（就是一个求和公式）可以顺手加上，不阻塞设计评审。
- "同行业暴露度"是否应该扩展为"同概念/同主题暴露度"（如新能源、AI 等概念板块，而非严格的行业分类）？—— 超出 V1 范围，MRD 原文只提到"行业"，概念板块归类的数据源与维护成本明显更高（概念标签频繁变化），留待未来有明确需求时再评估。
- 若 `add-trade-review-attribution` 最终决定不采用"软引用"而是完全不同的持仓表设计，本 change 需要同步调整依赖——这是两个 change 之间的协调风险，建议实现顺序上先完成 `add-trade-review-attribution` 的 tasks.md §1（数据模型）并冻结其 Repo 接口签名，再开始本 change 的实现，减少返工。
