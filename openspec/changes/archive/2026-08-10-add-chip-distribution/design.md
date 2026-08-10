## Context

`TechAnalyzer.analyze(code)` 当前流程（`src/service/tech/analyzer.py`）：`KlineProvider.get_kline()` → `IndicatorCalculator.calculate()`（日线）→ `IndicatorCalculator.calculate_weekly()`（周线）→ `ScoringEngine.score()` → 组装 `TechAnalysisResult`。六个评分维度全部由同一份 90 天窗口的日 K 线 DataFrame（`kline_days` 默认 90，见 `TechAnalysisConfig`）派生。筹码分布（获利比例/套牢比例/成本集中度）在概念上依赖“筹码从建仓以来的累积分布”，理论上需要比 90 天更长的历史价量数据才能算准——但 AKShare 已提供 `stock_cyq_em` 这一服务端预计算接口，直接返回东方财富口径的每日筹码分布序列，我们不需要、也不应该自己用 K 线重新实现这套算法。

现有可复用范式：
- `KlineProvider` + `KlineRepo` + `Kline` ORM：主备源切换 + SQLite 按 `(code, trade_date)` 主键缓存 + 当日不入库
- `add-cli-core` D-1：`report` 命令永不联网，新数据只能通过 `sync` 拉取
- `TechAnalysisResult` 字段分组模式（趋势/均线/量能/支撑/MACD/RSI/KDJ/信号），新增指标应遵循同一「数值字段 + 状态枚举 + signal 文案」三件套

## Goals / Non-Goals

**Goals:**
- 新增 `winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70` 等结构化数值字段，可被 CLI/未来 Web 直接消费，不仅是自由文本
- 派生 `trap_ratio`（套牢比例）为纯代码计算（`100 - winner_ratio`），不引入额外数据源
- 明确回答「是否需要扩展 K 线抓取窗口」：不需要，筹码分布走独立数据管道
- 筹码数据获取失败时优雅降级，不影响现有技术面指标与 `buy_signal`
- 遵循 `add-cli-core` D-1：筹码数据在 `sync` 阶段拉取持久化，`report tech` 保持严格离线

**Non-Goals:**
- 不实现筹码分布曲线可视化（价格-筹码堆积图）
- 不在 V1 将筹码字段纳入 `signal_score`/`buy_signal` 打分体系
- 不新增 Baostock 备用源（`stock_cyq_em` 无 Baostock 等价接口，单源可接受，见风险）
- 不追溯计算历史筹码分布趋势（如「集中度较 30 日前上升」），V1 仅取最新一行

## Decisions

### 决策 1：独立 Provider + 独立缓存表，不复用/不扩展 `kline_days` 窗口

**选择**：新增 `ChipDistributionProvider`（`src/data_provider/chip_distribution_provider.py`）与 `ChipDistributionRepo`（`src/dao/chip_distribution_repo.py`），表结构镜像 `Kline`（`code, trade_date` 复合主键），但字段完全不同（`winner_ratio, avg_cost, concentration_90, concentration_70, cost_90_low, cost_90_high, cost_70_low, cost_70_high`）。`AKShareFetcher.fetch_chip_distribution(code)` 一次调用即返回 AKShare 服务端计算好的全历史每日序列（非增量分页），Provider 层只需把返回的历史行中「尚未缓存」的部分 `upsert_batch` 写入，取最新一行合并进 `TechAnalysisResult`。**不修改** `TechAnalysisConfig.kline_days`（仍为 90），也不要求 `KlineProvider` 抓取更长窗口。

**理由**：`stock_cyq_em` 返回的获利比例/成本集中度是 AKShare/东方财富服务端基于该股票上市以来全部历史价量数据算出的，不是从我们自己截取的 90 天 K 线窗口派生。若为了「筹码分布」把 `kline_days` 从 90 提到例如 500+，会导致 MA60/MACD/RSI/KDJ 等既有指标计算量陡增（`sync` 单票耗时上升、SQLite 写入量上升），但对筹码分布字段本身毫无必要——纯属浪费。两个数据管道解耦，各自按需索取数据量，是成本最低的方案。

**备选方案**：
- 扩展 `kline_days` 到 300+ 天并在 `IndicatorCalculator` 内自实现筹码分布算法（基于筹码换手衰减模型）——拒绝：算法复杂（需要模拟逐日换手率对历史筹码的覆盖衰减），AKShare 已有现成、与东财客户端对齐的实现，重新发明轮子且需要长期维护口径一致性，不符合"能用现成确定性数据源就不要自研"的工程取舍
- 复用 `KlineProvider` 的表结构和主备切换逻辑（把筹码分布伪装成"另一种 K 线"）——拒绝：字段语义完全不同（无 OHLCV），且无 Baostock 备源，强行套用主备切换接口只会增加误导性的抽象层

### 决策 2：新增专门结构化字段 + 文案追加双轨并行，V1 不纳入打分

**选择**：`TechAnalysisResult` 新增 `winner_ratio: float | None`、`trap_ratio: float | None`（= `100 - winner_ratio`，纯代码派生）、`avg_cost: float | None`、`concentration_90: float | None`、`concentration_70: float | None`、`chip_status: ChipStatus | None`。同时在 `signal_reasons`/`risk_factors` 追加人类可读文案（如「筹码高度集中（90%集中度 8.2%），主力控盘明显」/「套牢盘沉重（套牢比例 62%），反弹阻力较大」）。**两者并存，不是二选一**；`signal_score`/`buy_signal` V1 不参与筹码维度，`BullTrendScorer` 权重总和保持 100 不变。

**理由**：`docs/agent-engineering-quality.md` §9.2 明确「技术面 `signal_score`、MA/MACD/RSI 数值必须由确定性模块计算」，新增数值字段而非只塞进自由文本是同一原则的延续——未来 Web 看板、CLI `--json` 输出都需要能直接读取 `winner_ratio` 数值而不是从字符串里正则提取。不纳入打分的原因：`stock_cyq_em` 存在已知的口径/数据质量争议（AKShare GitHub issue #5720 反馈获利比例与东财桌面端有差距，官方回复"以网页版为准"但未修复底层算法差异），把一个口径未完全稳定的信号直接注入已验证的 100 分打分体系风险较高；先作为独立展示维度上线，观察数据质量后再评估是否纳入 `ScoringParams`（见 Open Questions）。

**备选方案**：
- 只追加到 `risk_factors`/`signal_reasons` 文本，不新增数值字段——拒绝：数值字段丢失后 CLI `--json`/未来 API 无法结构化消费，且违反"确定性数值必须结构化输出"的规范
- V1 直接纳入 `ScoringParams` 新增 `chip_weight` 并压缩其他维度权重——拒绝：改变现有已验证的 6 维度 100 分权重分配是有回归风险的决策，且上面提到的数据质量顾虑尚未消化，不应该在同一个 change 里既加新数据源又动既有打分权重

### 决策 3：`sync` 拉取持久化 + `report tech` 严格离线；无备用源，失败静默降级

**选择**：
- `sync <code>` 新增筹码分布拉取：调用 `ChipDistributionProvider.get_latest(code, on_progress=...)`，内部拉取 `fetch_chip_distribution()` 全历史序列、`upsert_batch` 未缓存的历史行，与 K 线 sync 步骤并列执行，事务与现有 `session.commit()` 一并提交
- `report tech <code>` 保持严格离线：`TechAnalyzer.analyze(code, offline=True)` 内部对筹码分布也走 `offline=True` 路径（只读 `ChipDistributionRepo` 缓存，不触发任何 API 调用）
- `stock_cyq_em` 无 Baostock 或其他备用源；获取失败（网络异常、无数据、缓存为空）时，`TechAnalysisResult` 的筹码字段全部保持 `None`，`chip_status = None`，`warnings` 追加「筹码分布数据不可用: {原因}」，**不**触发 `buy_signal` 降级、**不**抛出异常——与 K 线数据不同，筹码分布是增量信息维度而非分析前提

**理由**：延续 `add-cli-core` D-1「report 永不联网」的既有 CLI 原则，避免重新引入"report 命令联网"的张力（`add-red-blue-confrontation` 已经为了同一原则做过一次架构调整，见其 design.md 决策 3）。无备用源是接受的风险（见 Risks），因为筹码分布是辅助判断维度，不是趋势判断的前提条件，静默降级不影响核心买卖信号的可靠性。

**备选方案**：
- `report tech` 允许 `--realtime`/联网参数按需现拉筹码分布——拒绝：违反既有 CLI 分层原则，且筹码分布本身是 EOD 数据（无实时版本概念），联网现拉没有实际收益
- 获取失败时将 `buy_signal` 降级或加大 `risk_factors` 权重——拒绝：会把"数据源可用性问题"错误地转化为"个股风险信号"，误导使用者

## Risks / Trade-offs

- **[风险] `stock_cyq_em` 获利比例口径与东财客户端存在已知偏差（AKShare issue #5720），且无第三方复核**→ **缓解**：V1 不纳入打分（决策 2），仅作展示与文案参考；`risk_factors`/`warnings` 中的筹码文案措辞克制（用"参考"而非"确认"式表达），避免使用者误以为是高置信度结论
- **[风险] 无备用数据源，AKShare 接口变更或限流会导致筹码分布长期不可用**→ **接受**：静默降级为 `None` + `warnings`，不阻塞核心技术面分析；后续若发现故障率高，可评估是否值得为单一辅助维度investment 双源方案
- **[风险] `sync` 新增一次 API 调用，增量拉取全历史序列可能比 K 线增量拉取更慢（无法像 K 线一样只请求缺口日期区间）**→ **缓解**：`stock_cyq_em` 本身是单次调用返回全部历史（非分页/非逐日请求），实测量级与 `fetch_kline` 相近；`upsert_batch` 只写入未缓存的历史行，重复 `sync` 的增量成本很低；若未来发现该接口显著拖慢 `sync`，可考虑增加 `--skip-chip` 开关（V1 不预先设计，按需再加）
- **[风险] `ChipStatus` 分类阈值（90% 集中度分档）缺乏权威依据，凭经验设定**→ **缓解**：阈值放入 `IndicatorParams` 可配置，不硬编码；单测覆盖边界值；后续可根据实际样本股票分布调整默认值

## Migration Plan

- 新增表 `chip_distribution`（`dao/models.py` 新增 `ChipDistribution` ORM），首次运行 `Base.metadata.create_all(engine)` 自动建表，不影响现有 `kline`/`stock_snapshots` 等表
- `TechAnalysisResult` 新增字段全部带默认值（`None`），对现有反序列化/`--json` 消费方是纯新增字段，不破坏既有字段语义（非 breaking）
- `TechAnalyzer` 构造函数新增可选依赖 `chip_provider: ChipDistributionProvider | None = None`，缺省自动从 `from_config` 构造；不改变现有单测中手工构造 `TechAnalyzer(kline_provider=..., config=...)` 的调用方式（新依赖有默认值）
- 回滚：删除新增文件（`chip_distribution_provider.py`、`chip_distribution_repo.py`、`chip_classifier.py`）、还原 `analyzer.py`/`tech_result.py`/`cli.py`/`formatters.py` 的增量修改即可；已写入的 `chip_distribution` 表数据不影响其余功能，可保留或清空

## Open Questions

- 是否需要在 V2 将筹码维度纳入 `ScoringParams`（新增 `chip_weight`，压缩现有权重）？取决于观察 V1 上线后 `stock_cyq_em` 数据质量与使用反馈，本 change 不预先设计扩展点
- 是否需要展示"筹码分布趋势"（如集中度较 N 日前上升/下降）？V1 只取最新一行，若未来需要趋势对比，需要额外读取历史缓存行并做简单差分，属于后续增量，不在本 change 范围
