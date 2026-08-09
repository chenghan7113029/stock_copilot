## ADDED Requirements

### Requirement: 十字星（Doji）识别
`PatternRecognizer.recognize(df, params)` SHALL 检测最新一根 K 线是否为十字星：实体 `|close - open|` 占振幅 `high - low` 的比例 ≤ `params.doji_body_ratio_max`（默认 10%）。振幅为 0（一字板）时 SHALL 视为满足十字星条件。

#### Scenario: 标准十字星
- **WHEN** 最新一根 K 线 `open=10.00, close=10.02, high=10.30, low=9.70`（实体占振幅 3.3%）
- **THEN** 返回结果包含 `PatternSignal(pattern=CandlestickPattern.DOJI, ...)`

#### Scenario: 非十字星（大实体阳线）
- **WHEN** 最新一根 K 线实体占振幅超过 `doji_body_ratio_max`
- **THEN** 返回结果不包含 `DOJI` 标注

---

### Requirement: 锤头线 / 吊颈线识别（共用几何检测）
`PatternRecognizer` SHALL 检测最新一根 K 线是否满足「小实体 + 长下影线 + 短上影线」几何特征：下影线长度 ≥ 实体长度 × `params.hammer_shadow_ratio_min`（默认 2.0），上影线长度 ≤ 实体长度（或振幅的固定小比例）。满足几何特征后，SHALL 结合 `TechIndicators.trend_status` 判断上下文：若近期趋势为空头相关状态（`WEAK_BEAR`/`BEAR`/`STRONG_BEAR`），标注为 `HAMMER`（锤头线，看多反转候选）；若为多头相关状态（`WEAK_BULL`/`BULL`/`STRONG_BULL`），标注为 `HANGING_MAN`（吊颈线，看空反转候选）；趋势为 `CONSOLIDATION` 时不标注（上下文不明确）。

#### Scenario: 下跌趋势末端锤头线
- **WHEN** 最新一根 K 线满足几何特征，且 `trend_status` 为 `BEAR`
- **THEN** 返回结果包含 `PatternSignal(pattern=CandlestickPattern.HAMMER, direction="看多", ...)`

#### Scenario: 上涨趋势末端吊颈线
- **WHEN** 最新一根 K 线满足几何特征，且 `trend_status` 为 `BULL`
- **THEN** 返回结果包含 `PatternSignal(pattern=CandlestickPattern.HANGING_MAN, direction="看空", ...)`

#### Scenario: 趋势不明确时不标注
- **WHEN** 最新一根 K 线满足几何特征，但 `trend_status` 为 `CONSOLIDATION`
- **THEN** 返回结果不包含 `HAMMER` 或 `HANGING_MAN` 标注

#### Scenario: 几何特征不满足
- **WHEN** 下影线长度小于实体长度 × `hammer_shadow_ratio_min`
- **THEN** 返回结果不包含 `HAMMER`/`HANGING_MAN` 标注

---

### Requirement: 吞没形态（Engulfing）识别
`PatternRecognizer` SHALL 检测最新两根 K 线是否构成吞没形态：当日阳线（`close > open`）且实体完全覆盖前一日阴线实体（`当日 open ≤ 前日 close` 且 `当日 close ≥ 前日 open`）时标注 `BULLISH_ENGULFING`（看涨吞没）；当日阴线且实体完全覆盖前一日阳线实体时标注 `BEARISH_ENGULFING`（看跌吞没）。

#### Scenario: 看涨吞没
- **WHEN** 前一日 `open=10.5, close=10.0`（阴线），当日 `open=9.9, close=10.7`（阳线，实体覆盖前日）
- **THEN** 返回结果包含 `PatternSignal(pattern=CandlestickPattern.BULLISH_ENGULFING, direction="看多", ...)`

#### Scenario: 看跌吞没
- **WHEN** 前一日 `open=10.0, close=10.5`（阳线），当日 `open=10.6, close=9.8`（阴线，实体覆盖前日）
- **THEN** 返回结果包含 `PatternSignal(pattern=CandlestickPattern.BEARISH_ENGULFING, direction="看空", ...)`

#### Scenario: 实体未完全覆盖
- **WHEN** 当日阳线实体范围未完全覆盖前一日阴线实体
- **THEN** 返回结果不包含 `BULLISH_ENGULFING` 标注

---

### Requirement: 形态识别结果独立于打分体系
`PatternRecognizer.recognize()` 的返回值 `list[PatternSignal]` SHALL 仅赋值给 `TechAnalysisResult.candlestick_patterns`，不经过 `ScoringEngine.score()`，不写入 `signal_reasons`/`risk_factors`，不影响 `signal_score`/`buy_signal` 的计算结果。

#### Scenario: 有形态命中但打分不受影响
- **WHEN** 同一份 K 线数据在启用与不启用形态识别两种路径下分别调用 `TechAnalyzer.analyze()`
- **THEN** 两次调用返回的 `signal_score`、`buy_signal`、`signal_reasons`、`risk_factors` 完全一致，仅 `candlestick_patterns` 字段有差异

#### Scenario: 无形态命中
- **WHEN** 最新 K 线不满足任何已实现形态的判定条件
- **THEN** `candlestick_patterns` 为空列表 `[]`，不抛出异常，不影响其余字段
