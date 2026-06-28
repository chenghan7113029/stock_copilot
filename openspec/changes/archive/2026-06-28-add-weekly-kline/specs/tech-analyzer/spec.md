## MODIFIED Requirements

### Requirement: TechAnalyzer.analyze(code) 完整分析流程
`TechAnalyzer.analyze(code)` SHALL 完整执行：K 线获取 → 日线指标计算 → 周线指标计算 → 评分 → 组装 `TechAnalysisResult`。日线分析完成后，SHALL 自动基于同一份 DataFrame 调用 `IndicatorCalculator.calculate_weekly()` 追加周线分析。非 A 股代码 SHALL 抛出 `UnsupportedMarketError`。

#### Scenario: 正常分析流程（含周线）
- **WHEN** `analyze("600519")` 被调用且数据充足（≥ 25 日线）
- **THEN** 返回的 `TechAnalysisResult` 包含完整日线字段，且 `weekly_trend_status` 非 None，`weekly_ma_alignment` 非空字符串

#### Scenario: 日线数据不足跳过周线
- **WHEN** `analyze("600519")` 被调用但 K 线行数 < 25
- **THEN** `TechAnalysisResult.weekly_trend_status = None`，`warnings` 含「周线数据不足」

#### Scenario: K 线获取失败
- **WHEN** `KlineProvider.get_kline()` 抛出 `KlineUnavailableError`
- **THEN** `buy_signal = WAIT`，`risk_factors` 包含失败原因，不抛出异常

---

## ADDED Requirements

### Requirement: TechAnalysisResult 周线字段分组
`TechAnalysisResult` SHALL 新增以下字段（数据不足时为 None）：`weekly_trend_status`（`WeeklyTrendStatus | None`）、`weekly_ma_alignment`（str）、`weekly_macd_signal`（str）、`weekly_rsi_6`（float | None）、`weekly_ma5/10/20`（float | None）。

#### Scenario: 完整周线字段
- **WHEN** 日线行数 ≥ 25 且周线指标计算成功
- **THEN** `weekly_trend_status` 为有效枚举值（非 None），`weekly_ma5/10/20` 均非 0

#### Scenario: 周线字段为 None 时不影响日线输出
- **WHEN** 周线计算跳过（数据不足）
- **THEN** 日线所有字段正常，`weekly_*` 字段为 None 或默认字符串
