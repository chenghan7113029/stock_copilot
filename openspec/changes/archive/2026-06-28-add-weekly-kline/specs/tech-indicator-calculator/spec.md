## ADDED Requirements

### Requirement: WeeklyIndicators 数据类
`WeeklyIndicators` SHALL 为 Python dataclass，包含：`weekly_trend_status`（`WeeklyTrendStatus` 枚举）、`weekly_ma5/10/20`（float）、`weekly_macd_dif/dea/bar`（float）、`weekly_rsi_6`（float）、`weekly_ma_alignment`（str，均线排列描述）、`weekly_macd_signal`（str）、`warnings`（list[str]）。所有数值字段默认 0.0，枚举字段默认 NEUTRAL。

#### Scenario: 默认值无异常
- **WHEN** 创建 `WeeklyIndicators()` 不传参
- **THEN** 所有字段有合理默认值，不抛出异常

---

### Requirement: IndicatorCalculator.calculate_weekly() 方法
`IndicatorCalculator.calculate_weekly(df_daily, params)` SHALL 内部调用 `WeeklyKlineAggregator.aggregate(df_daily)` 后，在周线 DataFrame 上计算 MA/MACD/RSI，组装并返回 `WeeklyIndicators`。`params` 使用 `IndicatorParams.weekly_macd_fast/slow/signal` 字段（默认 5/10/4）。

#### Scenario: 完整计算路径
- **WHEN** 传入 60 行日线 DataFrame 和默认 IndicatorParams
- **THEN** 返回 `WeeklyIndicators` 其中 `weekly_ma5/10/20` 均非 0，`weekly_trend_status` 非 NEUTRAL（在有明确趋势的数据下）

#### Scenario: 日线数据不足跳过周线
- **WHEN** 传入日线行数 < 25
- **THEN** 返回 `WeeklyIndicators` 含默认枚举值，`warnings` 含「周线数据不足，周线趋势分析未启用」

## MODIFIED Requirements

### Requirement: MA（移动平均线）计算
`IndicatorCalculator` SHALL 计算 MA5、MA10、MA20、MA60（简单移动平均），及当前价相对各均线的乖离率（`bias_ma5/10/20`）。数据不足 60 日时 MA60 SHALL 用 MA20 替代。`IndicatorParams` 新增 `weekly_macd_fast: int = 5`、`weekly_macd_slow: int = 10`、`weekly_macd_signal: int = 4`，用于周线 MACD 计算。

#### Scenario: 标准多头排列数据
- **WHEN** 传入至少 60 日 OHLCV 数据（收盘价持续上涨趋势）
- **THEN** MA5 > MA10 > MA20 > MA60，乖离率与各均线数值通过 pandas rolling mean 可重现

#### Scenario: MA60 数据不足
- **WHEN** 传入数据行数 < 60
- **THEN** MA60 字段等于 MA20 值，结果中包含「MA60 数据不足，以 MA20 替代」警告
