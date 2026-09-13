## MODIFIED Requirements

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
- **布林带**（F-19，新增）：`boll_mid`/`boll_upper`/`boll_lower`（float，中/上/下轨）、`boll_bandwidth`（float，带宽）、`boll_percentile`（float | None，带宽百分位 0~100）、`boll_status`（BollingerStatus 5 级枚举）、`boll_signal`（str，状态文案）——`boll_status` 对应的单状态文案由 `TechAnalyzer.analyze()` 追加进 `signal_reasons`/`risk_factors`，但**不参与** `signal_score` 计算
- **信号**：`buy_signal`（BuySignal 枚举）、`signal_score`（int 0~100）、`signal_reasons`（list[str]）、`risk_factors`（list[str]）
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

#### Scenario: 布林带字段结构化输出且不参与打分
- **WHEN** `boll_status = BollingerStatus.SQUEEZE`
- **THEN** `signal_reasons` 包含布林带收窄文案，且 `signal_score` 计算过程不读取任何布林带字段（回归对比启用/未启用布林带文案追加时 `signal_score` 数值不变）
