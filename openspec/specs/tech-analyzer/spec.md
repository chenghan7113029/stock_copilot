# tech-analyzer Specification

## Purpose
TBD - created by archiving change add-tech-analyzer-core. Update Purpose after archive.
## Requirements
### Requirement: TechAnalyzer.analyze(code) 完整分析流程
`TechAnalyzer.analyze(code, use_realtime=False, offline=False)` SHALL 完整执行：K 线获取 → 日线指标计算 → 周线指标计算 → 筹码分布获取 → 评分 → 组装 `TechAnalysisResult`。日线分析完成后，SHALL 自动基于同一份 DataFrame 调用 `IndicatorCalculator.calculate_weekly()` 追加周线分析。随后 SHALL 调用 `ChipDistributionProvider.get_latest(code, offline=offline)` 获取最新筹码分布数据并合并进结果；筹码分布获取失败或无缓存时，相关字段保持 `None`，`warnings` 追加原因，**不**影响其余字段计算与 `buy_signal`。输入为 6 位 A 股代码字符串；返回 `TechAnalysisResult` 数据类，非 A 股代码 SHALL 抛出 `UnsupportedMarketError`。

`use_realtime=True` 时，SHALL 透传至 `KlineProvider.get_kline()`，并将返回的 `quote_mode` 赋值给 `TechAnalysisResult.quote_mode`。`offline=True` 时，SHALL 透传至 `ChipDistributionProvider.get_latest()`，确保筹码分布获取同样严格离线。

#### Scenario: 正常分析流程（含周线，EOD 模式）
- **WHEN** `analyze("600519")` 被调用且数据充足（≥ 25 日线）
- **THEN** 返回的 `TechAnalysisResult` 包含完整日线字段，且 `weekly_trend_status` 非 None，`quote_mode = "eod"`

#### Scenario: 实时模式分析
- **WHEN** `analyze("600519", use_realtime=True)` 被调用
- **THEN** 返回完整 `TechAnalysisResult`，`quote_mode` 为 `"realtime"` 或 `"eod_fallback"`

#### Scenario: 日线数据不足跳过周线
- **WHEN** `analyze("600519")` 被调用但 K 线行数 < 25
- **THEN** `TechAnalysisResult.weekly_trend_status = None`，`warnings` 含「周线数据不足」

#### Scenario: 非 A 股代码被拒绝
- **WHEN** `analyze("AAPL")` 或 `analyze("00700")` 被调用
- **THEN** 抛出 `UnsupportedMarketError`

#### Scenario: K 线获取失败
- **WHEN** `KlineProvider.get_kline()` 抛出 `KlineUnavailableError`
- **THEN** `TechAnalysisResult` 中 `buy_signal = WAIT`，`risk_factors` 包含数据获取失败原因，不抛出异常

#### Scenario: 筹码分布获取成功并合并
- **WHEN** `analyze("600519", offline=True)` 被调用且本地有筹码分布缓存
- **THEN** `TechAnalysisResult.winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70`/`chip_status` 均为非 `None` 值，`trap_ratio = 100 - winner_ratio`

#### Scenario: 筹码分布获取失败不影响其余字段
- **WHEN** `ChipDistributionProvider.get_latest()` 返回 `(None, warnings)`（无缓存或获取失败）
- **THEN** `TechAnalysisResult` 的筹码字段均为 `None`，`warnings` 追加相应说明，`trend_status`/`buy_signal`/`signal_score` 等既有字段不受影响，不抛出异常

---

### Requirement: TechAnalyzer 依赖注入与 from_config 构造
`TechAnalyzer` 的构造函数 SHALL 接受 `KlineProvider` 作为注入参数（便于单元测试 mock）。同时 SHALL 提供 `from_config(config_dict)` 类方法，从配置字典自动构造依赖链（`KlineRepo → KlineProvider → TechAnalyzer`）。

#### Scenario: 依赖注入（单测场景）
- **WHEN** 创建 `TechAnalyzer(kline_provider=mock_provider, config=config)`
- **THEN** `analyze()` 调用 mock_provider 而非真实 Baostock/AKShare 接口

#### Scenario: from_config 工厂方法
- **WHEN** 调用 `TechAnalyzer.from_config({"db_path": "data/stock_copilot.db"})`
- **THEN** 返回完整构造的 `TechAnalyzer` 实例，内部依赖链自动初始化

---

### Requirement: 综合评分系统（BullTrendScorer）
`BullTrendScorer.score()` SHALL 基于 6 维度（趋势 30 + 乖离率 20 + 量能 15 + 支撑 10 + MACD 15 + 动量(RSI+KDJ) 10）计算 0~100 分，并基于评分与趋势状态共同决定 `BuySignal`。权重通过 `ScoringParams` 配置，所有参数有默认值。

#### Scenario: 强烈买入信号
- **WHEN** 趋势为 BULL 或 STRONG_BULL 且 signal_score >= 75
- **THEN** `buy_signal = STRONG_BUY`

#### Scenario: 强势空头强制降级
- **WHEN** 趋势为 BEAR 或 STRONG_BEAR
- **THEN** `buy_signal = STRONG_SELL`，无视评分数值

#### Scenario: 极强趋势低评分提示
- **WHEN** `trend_status = STRONG_BULL`（trend_strength >= 90）且 signal_score < 45
- **THEN** `risk_factors` 包含「趋势强劲但其他维度信号疲弱，建议人工复核量价背离情况」

#### Scenario: 评分权重可配置
- **WHEN** 传入 `ScoringParams(trend_weight=40, macd_weight=5)` 等自定义参数
- **THEN** 评分按新权重计算（不使用默认值）

---

### Requirement: TechAnalysisResult 输出契约
`TechAnalysisResult` SHALL 为 Python dataclass，包含以下分组字段（所有数值字段在数据充足时不为 None）：

- **基础**：`code`（str）、`current_price`（float）
- **趋势**：`trend_status`（TrendStatus 枚举）、`ma_alignment`（str）、`trend_strength`（float 0~100）
- **均线**：`ma5/10/20/60`（float）、`bias_ma5/10/20`（float，百分比）
- **量能**：`volume_status`（VolumeStatus 枚举）、`volume_ratio_5d`（float）、`volume_trend`（str）
- **支撑**：`support_ma5/ma10`（bool）、`support_levels`（list[float]）、`resistance_levels`（list[float]）
- **MACD**：`macd_dif/dea/bar`（float）、`macd_status`（MACDStatus 枚举）、`macd_signal`（str）
- **RSI**：`rsi_6/12/24`（float）、`rsi_status`（RSIStatus 枚举）、`rsi_signal`（str）
- **KDJ**：`kdj_k/d/j`（float）、`kdj_status`（KDJStatus 枚举）、`kdj_signal`（str）
- **筹码分布**（F-17，新增）：`winner_ratio`（float | None，获利比例 %）、`trap_ratio`（float | None，套牢比例 %，代码派生 `100 - winner_ratio`）、`avg_cost`（float | None，平均成本）、`concentration_90`（float | None）、`concentration_70`（float | None）、`chip_status`（ChipStatus | None，4 级枚举）——数据不可用时全部为 `None`，不抛异常
- **信号**：`buy_signal`（BuySignal 枚举）、`signal_score`（int 0~100）、`signal_reasons`（list[str]）、`risk_factors`（list[str]）——筹码分布相关文案追加进本组，**不参与** `signal_score` 计算（V1 范围）
- **周线**（F-20）：`weekly_trend_status`（WeeklyTrendStatus | None）、`weekly_ma_alignment`（str）、`weekly_macd_signal`（str）、`weekly_rsi_6`（float | None）、`weekly_ma5/10/20`（float | None）
- **价格时效**（F-16）：`quote_mode`（str，`"eod"` / `"realtime"` / `"eod_fallback"`）
- **元数据**：`warnings`（list[str]）、`data_timestamp`（datetime | None）

#### Scenario: 完整输出包含所有分组
- **WHEN** 对有效股票调用 `analyze()`，数据充足
- **THEN** 返回的 `TechAnalysisResult` 所有分组字段均有有意义的值，枚举字段非 None，数值字段非 0.0（除非计算结果确为零）

#### Scenario: 数据不足时降级输出
- **WHEN** K 线数据行数 < 26（不足以计算 MACD）
- **THEN** MACD 相关字段为 None 或默认枚举值，`warnings` 包含数据不足说明，不抛出异常

#### Scenario: 完整周线字段
- **WHEN** 日线行数 ≥ 25 且周线指标计算成功
- **THEN** `weekly_trend_status` 为有效枚举值（非 None），`weekly_ma5/10/20` 均非 0

#### Scenario: 周线字段为 None 时不影响日线输出
- **WHEN** 周线计算跳过（数据不足）
- **THEN** 日线所有字段正常，`weekly_*` 字段为 None 或默认字符串

#### Scenario: 筹码字段结构化输出且不参与打分
- **WHEN** 筹码分布数据可用，`concentration_90 = 8.2`
- **THEN** `chip_status = ChipStatus.HIGHLY_CONCENTRATED`，`signal_score` 计算过程不读取任何筹码字段（回归对比启用/未启用筹码分布时 `signal_score` 数值不变）

### Requirement: TechAnalysisConfig 可配置
`TechAnalysisConfig` SHALL 包含 `IndicatorParams`（指标计算参数）和 `ScoringParams`（评分权重与阈值），所有参数 SHALL 有合理默认值，支持部分覆盖（传入只覆盖指定字段，其余保持默认）。

#### Scenario: 使用默认配置
- **WHEN** 创建 `TechAnalysisConfig()` 不传任何参数
- **THEN** MACD 参数为 12/26/9，RSI 为 6/12/24，KDJ 为 9/3/3，评分权重总和为 100

#### Scenario: 覆盖部分参数
- **WHEN** 创建 `TechAnalysisConfig(scoring_params=ScoringParams(bias_threshold=3.0))`
- **THEN** 乖离率阈值使用 3.0%，其余参数保持默认值

