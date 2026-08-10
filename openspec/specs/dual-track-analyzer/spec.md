# dual-track-analyzer Specification

## Purpose
TBD - created by archiving change add-dual-track-analyzer. Update Purpose after archive.
## Requirements
### Requirement: DualTrackAnalyzer.analyze(code) 双轨分析入口
`DualTrackAnalyzer.analyze(code: str) → DualTrackReport` SHALL 内部顺序调用：
1. `ValueAnalyzer.analyze(code)` → `ValueAnalysisResult`
2. `TechAnalyzer.analyze(code)` → `TechAnalysisResult`
3. `SignalFusion.fuse(value_result, tech_result)` → `combined_signal`
4. 构造并返回 `DualTrackReport`

任一子 Analyzer 抛出异常时 SHALL 捕获并记录，以 None 填充对应子结果，继续执行另一路，`combined_signal` 降级（见降级语义需求）。非 A 股代码 SHALL 抛出 `UnsupportedMarketError`（由内部 Analyzer 透传）。

#### Scenario: 完整双轨分析
- **WHEN** `analyze("600519")` 被调用且两路 Analyzer 均成功
- **THEN** 返回 `DualTrackReport`，`value_result` 非 None，`tech_result` 非 None，`combined_signal` 为有效枚举值

#### Scenario: ValueAnalyzer 失败降级
- **WHEN** `ValueAnalyzer.analyze()` 抛出异常
- **THEN** `DualTrackReport.value_result = None`，`tech_result` 正常填充，`combined_signal = tech_result.buy_signal`，`warnings` 含价值面失败原因

#### Scenario: TechAnalyzer 失败降级
- **WHEN** `TechAnalyzer.analyze()` 抛出异常
- **THEN** `DualTrackReport.tech_result = None`，`value_result` 正常填充，`combined_signal` 仅基于价值面评级，`warnings` 含技术面失败原因

#### Scenario: 两路均失败
- **WHEN** ValueAnalyzer 和 TechAnalyzer 均抛出异常
- **THEN** `combined_signal = WAIT`，`warnings` 含两路失败原因，不抛出异常

#### Scenario: 非 A 股代码
- **WHEN** `analyze("AAPL")` 被调用
- **THEN** 抛出 `UnsupportedMarketError`

---

### Requirement: DualTrackReport 数据模型
`DualTrackReport` SHALL 为 Python dataclass，包含：
- `code: str`
- `value_result: ValueAnalysisResult | None`
- `tech_result: TechAnalysisResult | None`
- `combined_signal: CombinedSignal`（6 级枚举：STRONG_BUY/BUY/HOLD/WAIT/SELL/STRONG_SELL）
- `value_rating: ValueRating | None`（UNDERVALUED/FAIR/OVERVALUED/UNKNOWN，由 MOS 派生）
- `analysis_summary: str`（结构化文本摘要，供 LLM prompt 消费）
- `warnings: list[str]`
- `data_timestamp: datetime | None`

#### Scenario: 完整报告字段
- **WHEN** 双轨分析成功完成
- **THEN** 所有字段非 None（warnings 可为空列表），`analysis_summary` 长度 > 0

#### Scenario: analysis_summary 包含关键信息
- **WHEN** 双轨分析成功
- **THEN** `analysis_summary` 包含：股票代码、公允价区间（若可用）、技术面趋势状态、综合信号

---

### Requirement: SignalFusion 确定性规则融合

`SignalFusion.fuse(value_result, tech_result) → CombinedSignal` SHALL 基于 `ValueRating` × `tech_result.buy_signal` 的矩阵输出 `CombinedSignal`。

`ValueRating` 派生规则：

1. 若 `value_result is None` → 无价值评级（见下方仅技术面）
2. 若 `value_result.methodology_applicable is False` → **强制** `ValueRating.UNKNOWN`（忽略 MOS）
3. 否则由 `value_result.margin_of_safety` 按既有阈值派生 UNDERVALUED / FAIR / OVERVALUED / UNKNOWN(mos 为空)

矩阵（当 rating 为 UNDERVALUED/FAIR/OVERVALUED 且技术面非空）：

| ValueRating \ BuySignal | STRONG_BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
|---|---|---|---|---|---|---|
| UNDERVALUED | STRONG_BUY | BUY | BUY | WAIT | WAIT | SELL |
| FAIR | BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
| OVERVALUED | HOLD | WAIT | SELL | SELL | STRONG_SELL | STRONG_SELL |

当 `value_result = None` 时，SHALL 直接返回 `tech_result.buy_signal`（转换为 `CombinedSignal`）。当 `tech_result = None` 时，SHALL 基于 `ValueRating` 单独输出（UNDERVALUED→BUY，FAIR→HOLD，OVERVALUED→WAIT，**UNKNOWN→WAIT**）。两者均 None 时返回 WAIT。当 `value_rating == UNKNOWN` 且技术面非空时，SHALL 返回技术面转换结果（不查 UNDERVALUED/FAIR/OVERVALUED 矩阵）。

#### Scenario: 低估 + 强烈买入 → 强烈买入

- **WHEN** `methodology_applicable=True`，MOS > 20% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = STRONG_BUY`

#### Scenario: 高估 + 强烈买入 → 持有（抑制技术追高）

- **WHEN** `methodology_applicable=True`，MOS < -10% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = HOLD`

#### Scenario: 低估 + 技术空头 → 观望（等技术面企稳）

- **WHEN** `methodology_applicable=True`，MOS > 20% 且 `tech_result.buy_signal = STRONG_SELL`
- **THEN** `combined_signal = SELL`

#### Scenario: 仅技术面可用

- **WHEN** `value_result = None`，`tech_result.buy_signal = BUY`
- **THEN** `combined_signal = BUY`

#### Scenario: 诚实降级忽略 MOS 低估

- **WHEN** `methodology_applicable=False`，MOS > 20%，`tech_result.buy_signal = STRONG_BUY`
- **THEN** `value_rating = UNKNOWN`，`combined_signal` 为技术面 STRONG_BUY 的转换结果（不得先按 UNDERVALUED 矩阵再融合出「价值确认」语义——实现上即 UNKNOWN 分支）

### Requirement: 诚实降级时价值评级强制 UNKNOWN

当 `value_result` 非空且 `value_result.methodology_applicable is False` 时，`SignalFusion`（及 `derive_value_rating` 的调用路径）SHALL **忽略** `margin_of_safety`，将 `value_rating` 设为 `ValueRating.UNKNOWN`。

融合后果与既有 UNKNOWN 语义一致：

- 仅有价值面：`combined_signal = WAIT`
- 价值面 + 技术面：`combined_signal` 跟随技术面 `buy_signal`（转换为 CombinedSignal），**不得**因 MOS 显示低估而升级为 BUY/STRONG_BUY

#### Scenario: 比亚迪双轨不因假低估买入

- **WHEN** `value_result` 为比亚迪诚实降级结果（`methodology_applicable=False`，即使 `margin_of_safety > 20`），且 `tech_result.buy_signal = BUY`
- **THEN** `value_rating = UNKNOWN`，`combined_signal` 等于技术面转换结果（BUY），而非矩阵中 UNDERVALUED×BUY 的加成路径以外的「价值驱动买入」；具体地 SHALL NOT 把价值面解释为 UNDERVALUED

#### Scenario: 诚实降级且无技术面 → 观望

- **WHEN** `methodology_applicable=False` 且 `tech_result is None`
- **THEN** `value_rating = UNKNOWN`，`combined_signal = WAIT`

#### Scenario: 正常价值成长仍按 MOS 评级

- **WHEN** `methodology_applicable=True` 且 MOS > 低估阈值
- **THEN** `value_rating = UNDERVALUED`（行为与诚实降级引入之前一致）

---

### Requirement: DualTrackAnalyzer.from_config 工厂方法
`DualTrackAnalyzer.from_config(config: dict) → DualTrackAnalyzer` SHALL 内部调用 `ValueAnalyzer.from_config(config)` 和 `TechAnalyzer.from_config(config)` 完成初始化，返回可用的 `DualTrackAnalyzer` 实例。

#### Scenario: 从配置字典初始化
- **WHEN** 调用 `DualTrackAnalyzer.from_config({"db_path": "data/stock_copilot.db"})`
- **THEN** 返回完整的 `DualTrackAnalyzer` 实例，内部两个子 Analyzer 均已初始化

---

### Requirement: DualTrackAnalyzer 新增离线分析方法
`DualTrackAnalyzer` SHALL 提供 `analyze_offline(code: str) -> DualTrackReport`，内部调用 `ValueAnalyzer.analyze_offline()`、`TechAnalyzer.analyze(code, offline=True)` 与 `SentimentAnalyzer.analyze_offline(code)`，不发起任何网络请求。`DualTrackReport` SHALL 新增 `sentiment_result: SentimentAnalysisResult | None` 字段。`analysis_summary` SHALL 总是包含情绪面段落：情绪面计算成功时输出三维联合解读文本（引用价值面评估、技术面趋势、情绪面等级），情绪面数据缺失时显式输出"情绪面数据缺失，本次报告仅基于价值+技术双维"，不得静默省略该段落。既有 `analyze()`（联网版）SHALL 同步新增 `sentiment_result` 计算，且不改变既有 `combined_signal`/`value_rating` 数值融合逻辑。

#### Scenario: 离线三维分析成功
- **WHEN** 本地已有 `600519` 的价值快照、K 线缓存与市场情绪快照，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `DualTrackReport`，`sentiment_result` 非空，`analysis_summary` 包含情绪面联合解读段落，且过程不触发任何网络请求

#### Scenario: 情绪面数据缺失时的显式降级
- **WHEN** 本地无市场情绪快照，但价值面与技术面快照均存在
- **THEN** `sentiment_result` SHALL 为 `None`，`analysis_summary` SHALL 显式包含"情绪面数据缺失，本次报告仅基于价值+技术双维"文案，`combined_signal`/`value_rating` 计算 SHALL 不受影响

#### Scenario: 既有 combined_signal 数值融合逻辑不变
- **WHEN** 情绪面为极度贪婪或极度恐慌等任意等级
- **THEN** `SignalFusion.fuse()` 计算得出的 `combined_signal`/`value_rating` 数值 SHALL 与本 change 之前完全一致（回归测试覆盖），情绪面仅通过 `warnings`/`analysis_summary` 呈现，不参与数值融合公式

