## Why

日线技术指标只能反映短中期动量，无法判断更大级别的趋势是否支撑介入。实战中常见「日线看多但周线死叉」导致的假信号。MRD F-20（D-7 已决策）要求在 V1.x 引入周 K 线趋势分析，作为日线信号的宏观滤波器。

## What Changes

- 新增 `WeeklyKlineAggregator`：将日线 OHLCV DataFrame 按自然周（周一为起点）聚合为周 K 线（OHLCV + 成交量汇总）
- `IndicatorCalculator` 新增 `calculate_weekly(df_daily)` 方法：在周线 DataFrame 上计算 MA5W/10W/20W、MACD(5/10/4)、RSI(6W)，输出 `WeeklyIndicators` 数据类
- 新增 `WeeklyTrendStatus` 枚举（5 级：STRONG_BULL / BULL / NEUTRAL / BEAR / STRONG_BEAR）及判断逻辑
- `TechAnalysisResult` 新增 `weekly_trend` 分组：`weekly_trend_status`、`weekly_ma_alignment`、`weekly_macd_signal`、`weekly_rsi_12`
- `TechAnalyzer.analyze()` 在现有日线计算完成后，自动基于同一份 `df` 追加周线分析（无需额外 API 调用）
- `BullTrendScorer` 新增可选「多空周线过滤」：当 `weekly_trend_status` 为 BEAR/STRONG_BEAR 时，`buy_signal` 降级一档（默认启用，可通过 `ScoringParams.weekly_filter_enabled=False` 关闭）

## Capabilities

### New Capabilities

- `tech-weekly-trend`：周 K 线趋势分析能力 — 日线聚合为周线；计算周线均线/MACD/RSI；输出 `WeeklyTrendStatus`；作为日线信号的宏观过滤层

### Modified Capabilities

- `tech-indicator-calculator`：新增 `calculate_weekly()` 方法和 `WeeklyIndicators` 数据类
- `tech-analyzer`：`TechAnalysisResult` 扩展 `weekly_trend` 分组字段；`BullTrendScorer` 新增周线降级逻辑

## Impact

- `src/service/tech/calculator.py`：新增 `WeeklyKlineAggregator` 类和 `calculate_weekly()` 方法
- `src/service/tech/models/tech_result.py`：新增 `WeeklyTrendStatus` 枚举及 `TechAnalysisResult` 周线字段
- `src/service/tech/config.py`：`ScoringParams` 新增 `weekly_filter_enabled: bool = True`
- `src/service/tech/scorer.py`：`BullTrendScorer` 读取 `weekly_trend_status` 进行降级判断
- `src/service/tech/analyzer.py`：调用 `calculate_weekly()` 并填充结果
- `test/service/tech/test_calculator.py`：补充周线聚合与指标计算测试
- `test/service/tech/test_analyzer.py`：补充周线降级信号测试
- `docs/mrd/features/tech-analysis.md`：F-20 状态更新
