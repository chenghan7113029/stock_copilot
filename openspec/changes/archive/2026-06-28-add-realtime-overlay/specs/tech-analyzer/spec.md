## MODIFIED Requirements

### Requirement: TechAnalyzer.analyze(code) 完整分析流程
`TechAnalyzer.analyze(code, use_realtime=False)` SHALL 完整执行：K 线获取 → 指标计算 → 评分 → 组装 `TechAnalysisResult`。输入为 6 位 A 股代码字符串；返回 `TechAnalysisResult` 数据类，非 A 股代码 SHALL 抛出 `UnsupportedMarketError`。

`use_realtime=True` 时，SHALL 透传至 `KlineProvider.get_kline()`，并将返回的 `quote_mode` 赋值给 `TechAnalysisResult.quote_mode`。

#### Scenario: 正常分析流程（EOD 模式）
- **WHEN** `analyze("600519")` 被调用（默认 use_realtime=False）
- **THEN** 返回完整 `TechAnalysisResult`，`quote_mode = "eod"`

#### Scenario: 实时模式分析
- **WHEN** `analyze("600519", use_realtime=True)` 被调用
- **THEN** 返回完整 `TechAnalysisResult`，`quote_mode` 为 `"realtime"` 或 `"eod_fallback"`

#### Scenario: 非 A 股代码被拒绝
- **WHEN** `analyze("AAPL")` 或 `analyze("00700")` 被调用
- **THEN** 抛出 `UnsupportedMarketError`

#### Scenario: K 线获取失败
- **WHEN** `KlineProvider.get_kline()` 抛出 `KlineUnavailableError`
- **THEN** `TechAnalysisResult` 中 `buy_signal = WAIT`，`risk_factors` 包含数据获取失败原因，不抛出异常

---

## ADDED Requirements

### Requirement: TechAnalysisResult.quote_mode 字段
`TechAnalysisResult` SHALL 包含 `quote_mode: str` 字段，取值为 `"eod"`（默认，收盘价）、`"realtime"`（当日实时价叠加成功）或 `"eod_fallback"`（实时叠加请求但降级为 EOD）。

#### Scenario: 默认 quote_mode 为 eod
- **WHEN** 正常 EOD 分析完成
- **THEN** `result.quote_mode == "eod"`

#### Scenario: 实时叠加失败时标注 fallback
- **WHEN** `use_realtime=True` 但实时报价获取失败
- **THEN** `result.quote_mode == "eod_fallback"`，`result.warnings` 含失败原因
