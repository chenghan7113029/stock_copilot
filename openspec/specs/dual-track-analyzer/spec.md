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
`SignalFusion.fuse(value_result, tech_result) → CombinedSignal` SHALL 基于 `ValueRating`（由 `value_result.margin_of_safety` 派生）× `tech_result.buy_signal` 的 3×6 矩阵输出 `CombinedSignal`：

| ValueRating \ BuySignal | STRONG_BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
|---|---|---|---|---|---|---|
| UNDERVALUED | STRONG_BUY | BUY | BUY | WAIT | WAIT | SELL |
| FAIR | BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
| OVERVALUED | HOLD | WAIT | SELL | SELL | STRONG_SELL | STRONG_SELL |

当 `value_result = None` 时，SHALL 直接返回 `tech_result.buy_signal`（转换为 `CombinedSignal`）。当 `tech_result = None` 时，SHALL 基于 `ValueRating` 单独输出（UNDERVALUED→BUY，FAIR→HOLD，OVERVALUED→WAIT）。两者均 None 时返回 WAIT。

#### Scenario: 低估 + 强烈买入 → 强烈买入
- **WHEN** MOS > 20% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = STRONG_BUY`

#### Scenario: 高估 + 强烈买入 → 持有（抑制技术追高）
- **WHEN** MOS < -10% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = HOLD`

#### Scenario: 低估 + 技术空头 → 观望（等技术面企稳）
- **WHEN** MOS > 20% 且 `tech_result.buy_signal = STRONG_SELL`
- **THEN** `combined_signal = SELL`

#### Scenario: 仅技术面可用
- **WHEN** `value_result = None`，`tech_result.buy_signal = BUY`
- **THEN** `combined_signal = BUY`

---

### Requirement: DualTrackAnalyzer.from_config 工厂方法
`DualTrackAnalyzer.from_config(config: dict) → DualTrackAnalyzer` SHALL 内部调用 `ValueAnalyzer.from_config(config)` 和 `TechAnalyzer.from_config(config)` 完成初始化，返回可用的 `DualTrackAnalyzer` 实例。

#### Scenario: 从配置字典初始化
- **WHEN** 调用 `DualTrackAnalyzer.from_config({"db_path": "data/stock_copilot.db"})`
- **THEN** 返回完整的 `DualTrackAnalyzer` 实例，内部两个子 Analyzer 均已初始化
