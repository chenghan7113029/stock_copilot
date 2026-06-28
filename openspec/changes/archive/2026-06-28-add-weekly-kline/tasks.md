## 1. 数据模型扩展

- [x] 1.1 修改 `src/service/tech/models/tech_result.py`：
  - 新增 `WeeklyTrendStatus` 枚举（STRONG_BULL / BULL / NEUTRAL / BEAR / STRONG_BEAR）
  - `TechAnalysisResult` 新增字段：`weekly_trend_status: WeeklyTrendStatus | None = None`、`weekly_ma_alignment: str = ""`、`weekly_macd_signal: str = ""`、`weekly_rsi_6: float | None = None`、`weekly_ma5/10/20: float | None = None`
- [x] 1.2 修改 `src/service/tech/config.py`：
  - `IndicatorParams` 新增 `weekly_macd_fast: int = 5`、`weekly_macd_slow: int = 10`、`weekly_macd_signal: int = 4`
  - `ScoringParams` 新增 `weekly_filter_enabled: bool = True`

## 2. WeeklyIndicators 与聚合器

- [x] 2.1 修改 `src/service/tech/calculator.py`：
  - 新增 `WeeklyIndicators` dataclass（`weekly_trend_status`, `weekly_ma5/10/20`, `weekly_macd_dif/dea/bar`, `weekly_rsi_6`, `weekly_ma_alignment`, `weekly_macd_signal`, `warnings`）
  - 新增 `WeeklyKlineAggregator` 类，`aggregate(df_daily) -> pd.DataFrame`：按自然周（`W-MON`）聚合 OHLCV；日线 < 25 行时返回空 DataFrame
- [x] 2.2 修改 `src/service/tech/calculator.py`：
  - `IndicatorCalculator` 新增 `calculate_weekly(df_daily, params) -> WeeklyIndicators` 方法：调用聚合器 → 计算周线 MA/MACD/RSI → 判断 `WeeklyTrendStatus` → 返回 `WeeklyIndicators`
  - MA20W 不足时以最大可用窗口替代，warnings 注明
  - 数据不足时返回带默认枚举值的 `WeeklyIndicators`，warnings 含「周线数据不足」

## 3. 评分引擎扩展

- [x] 3.1 修改 `src/service/tech/scorer.py`：
  - `BullTrendScorer.score()` 接收可选 `weekly_indicators: WeeklyIndicators | None = None`
  - 在 `_resolve_buy_signal()` 后检查：若 `weekly_filter_enabled=True` 且 `weekly_trend_status` 为 BEAR/STRONG_BEAR，则 buy_signal 降一档，risk_factors 追加「周线空头，日线买点风险较高」
  - `weekly_filter_enabled=False` 时跳过

## 4. TechAnalyzer 集成

- [x] 4.1 修改 `src/service/tech/analyzer.py`：
  - `analyze()` 内部在日线 `calculate()` 后调用 `calculate_weekly(df, indicator_params)`
  - 将 `WeeklyIndicators` 结果填充到 `TechAnalysisResult` 的 `weekly_*` 字段
  - 传递 `weekly_indicators` 给 `scorer.score()`

## 5. 单元测试

- [x] 5.1 修改 `test/service/tech/test_calculator.py`：
  - 新增 `test_weekly_aggregation_60_days()`：验证 60 日线聚合为约 12 周线，OHLCV 字段正确
  - 新增 `test_weekly_aggregation_insufficient_data()`：< 25 日线返回空 DataFrame
  - 新增 `test_weekly_indicators_bull_trend()`：周线多头排列 → WeeklyTrendStatus.BULL
  - 新增 `test_weekly_rsi_computed()`：周线 RSI 值非零非 NaN
- [x] 5.2 修改 `test/service/tech/test_analyzer.py`：
  - 新增 `test_weekly_trend_included_in_result()`：mock 数据 ≥ 25 行 → result.weekly_trend_status 非 None
  - 新增 `test_weekly_bear_downgrades_buy_signal()`：周线空头 → STRONG_BUY 降为 BUY
  - 新增 `test_weekly_filter_disabled()`：ScoringParams(weekly_filter_enabled=False) → 不降级
- [x] 5.3 运行 `py -m pytest test/service/tech/ -v` 确认全部通过
- [x] 5.4 运行 `py -m ruff check src/service/tech/` 确认无 lint 错误

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/tech-analysis.md`：F-20 状态改为 ✅，变更记录新增 `add-weekly-kline` 条目；§4.2/§4.3 补充 `weekly_*` 字段与 `WeeklyTrendStatus` 枚举；§7.1 文件清单更新
