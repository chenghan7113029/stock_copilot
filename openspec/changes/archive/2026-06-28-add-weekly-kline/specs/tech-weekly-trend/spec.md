## ADDED Requirements

### Requirement: 日线 OHLCV 聚合为周 K 线
`WeeklyKlineAggregator.aggregate(df_daily)` SHALL 将日线 DataFrame 按自然周（周一为起点，`pandas.Grouper(freq="W-MON", closed="left", label="left")`）聚合：open 取第一日、high 取最高、low 取最低、close 取最后日、volume 取求和。返回周线 DataFrame，列名与日线相同（`date/open/high/low/close/volume`），`date` 为本周周一日期字符串。

#### Scenario: 标准 60 日线聚合为约 12 周线
- **WHEN** 传入 60 行日线 DataFrame
- **THEN** 返回约 12~13 行周线 DataFrame，OHLCV 列完整

#### Scenario: 周线 OHLCV 语义正确
- **WHEN** 某周包含 5 个交易日
- **THEN** `open` 为周一收盘/开盘，`high` 为 5 日最高，`low` 为 5 日最低，`close` 为周五收盘，`volume` 为 5 日成交量之和

#### Scenario: 本周未完结的处理
- **WHEN** 最后一周只有 1~4 个交易日（本周仍在进行）
- **THEN** 该周仍被聚合输出，high/low/volume 为截至当日的值；不影响已完整周的计算

#### Scenario: 数据不足 25 日无法生成 5 个完整周
- **WHEN** 传入日线行数 < 25
- **THEN** 返回空 DataFrame，调用方 SHALL 跳过周线分析并写入 warnings

---

### Requirement: 周线指标计算
`IndicatorCalculator.calculate_weekly(df_daily, params)` SHALL 在周线 DataFrame 上计算：
- `weekly_ma5/10/20`（周线简单移动平均）
- `weekly_macd_dif/dea/bar`（参数 `macd_fast=5, slow=10, signal=4`，`ewm(adjust=False)`）
- `weekly_rsi_6`（Wilder's EMA，alpha=1/6，NaN 填 50）

返回 `WeeklyIndicators` 数据类（含上述字段及 `weekly_trend_status`、`weekly_ma_alignment`、`weekly_macd_signal`）。

#### Scenario: 标准周线指标计算
- **WHEN** 传入约 12 行周线 DataFrame
- **THEN** `weekly_ma5` 为最近 5 周均价，`weekly_macd_dif` 为 EMA5 - EMA10，与手动计算一致

#### Scenario: 周线 MA20 数据不足时降级
- **WHEN** 周线行数 < 20（约 60 日线）
- **THEN** `weekly_ma20` 以可用最大窗口均线替代，`WeeklyIndicators.warnings` 含「周线 MA20 数据不足」

---

### Requirement: 周线趋势状态评估（5 级）
基于周线均线排列判断 `WeeklyTrendStatus`：
- STRONG_BULL：MA5W > MA10W > MA20W 且扩散
- BULL：MA5W > MA10W > MA20W
- NEUTRAL：均线交缠或数据不足
- BEAR：MA5W < MA10W < MA20W
- STRONG_BEAR：MA5W < MA10W < MA20W 且扩散

#### Scenario: 标准多头排列周线
- **WHEN** 周线 MA5W > MA10W > MA20W
- **THEN** `weekly_trend_status = BULL`（或 STRONG_BULL 如扩散）

#### Scenario: 数据不足时 NEUTRAL
- **WHEN** 日线行数 < 25 导致无法计算周线指标
- **THEN** `weekly_trend_status = NEUTRAL`，`TechAnalysisResult.weekly_trend_status = None`

---

### Requirement: 周线空头降级过滤（BullTrendScorer）
`BullTrendScorer` 在 `_resolve_buy_signal()` 后检查 `WeeklyIndicators.weekly_trend_status`：若为 BEAR 或 STRONG_BEAR，SHALL 将 `buy_signal` 降一档（STRONG_BUY→BUY；BUY→WAIT；HOLD→WAIT；其余不变），并在 `risk_factors` 追加「周线空头，日线买点风险较高」。此行为由 `ScoringParams.weekly_filter_enabled: bool = True` 控制，设为 `False` 时跳过。

#### Scenario: 周线空头降低日线强烈买入信号
- **WHEN** 日线评分 ≥ 75（STRONG_BUY）但 `weekly_trend_status = BEAR`
- **THEN** `buy_signal` 降为 `BUY`，`risk_factors` 含周线风险提示

#### Scenario: 周线中性或多头不触发降级
- **WHEN** `weekly_trend_status = BULL` 或 NEUTRAL
- **THEN** `buy_signal` 不受周线降级影响

#### Scenario: 关闭周线过滤
- **WHEN** `ScoringParams(weekly_filter_enabled=False)` 且周线空头
- **THEN** `buy_signal` 不被降级，`risk_factors` 不含周线提示
