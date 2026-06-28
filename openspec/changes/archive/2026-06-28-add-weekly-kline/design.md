## Context

`IndicatorCalculator` 当前只处理日线 OHLCV，输出 `TechIndicators`（日线快照）。周 K 线是日线数据的派生产物，无需额外 API 调用——直接对已有日线 DataFrame 按自然周聚合即可。聚合后的周线行数约为日线的 1/5，计算成本极低。

现有流程：`KlineProvider.get_kline(days=90)` → 约 60 根日线 → `IndicatorCalculator.calculate()` → `TechIndicators`。周线聚合接入点为 `TechAnalyzer.analyze()` 内部，日线计算完成后追加一步。

## Goals / Non-Goals

**Goals:**
- 基于日线 DataFrame 聚合周 K 线（无额外 API）
- 计算周线 MA5W/10W/20W、MACD(5/10/4)（周线参数）、RSI(6W)
- 输出 `WeeklyTrendStatus`（5 级）并存入 `TechAnalysisResult.weekly_trend_*` 字段
- `BullTrendScorer` 新增可关闭的「周线空头过滤」降级逻辑
- 日线窗口不变（90天），周线由此派生（约 18 周，满足 MA20W 最低要求）

**Non-Goals:**
- 独立的周线 API 拉取（Baostock 有接口，但本次不引入）
- 月 K 线（D-7 已决策暂不实现）
- 周线缓存入 SQLite（派生数据，每次内存计算）
- 周线 KDJ（信号粒度对周线意义不大）

## Decisions

### D-1：聚合周期定义
**决策**：以自然周（`pandas.Grouper(freq="W-MON", closed="left", label="left")`）聚合，OHLC 取 first/max/min/last，volume 取 sum。  
**备选**：以交易日滚动窗口聚合（每 5 根日线）。  
**理由**：自然周与主流 K 线软件显示一致，用户认知无摩擦。

### D-2：周线数据类
**决策**：新增 `WeeklyIndicators` dataclass（字段：`weekly_trend_status`、`weekly_ma5/10/20`、`weekly_macd_dif/dea/bar`、`weekly_rsi_6`、`weekly_ma_alignment`、`weekly_macd_signal`），与 `TechIndicators` 并列，不继承。  
**理由**：字段集不同（无 KDJ/量能/支撑），分离避免混淆。

### D-3：周线 MACD 参数
**决策**：使用 (5, 10, 4)（对应日线 12/26/9 的周线等效缩放）。  
**备选**：仍用 (12, 26, 9)（周线数据偏少，快慢线过于缓慢）。  
**理由**：18周数据下 (5, 10, 4) 有效信号更多；参数写入 `IndicatorParams.weekly_macd_fast/slow/signal`，可配置。

### D-4：周线降级规则
**决策**：`BullTrendScorer` 在 `_resolve_buy_signal()` 后检查：若 `weekly_trend_status` 为 BEAR/STRONG_BEAR，则 `buy_signal` 降一档（STRONG_BUY→BUY，BUY→WAIT，其余不变）；由 `ScoringParams.weekly_filter_enabled: bool = True` 控制。  
**理由**：周线空头是大级别下跌，日线买点风险极高；降级而非强制 SELL，保留用户判断空间。  
**备选**：强制 SELL（过于激进，周线震荡时误伤）。

### D-5：日线数据不足时的处理
**决策**：若日线行数 < 25（不足以构成至少 5 个完整周），`WeeklyIndicators.weekly_trend_status = NEUTRAL`，`TechAnalysisResult.weekly_trend_status = None`，`warnings` 追加「周线数据不足，周线趋势分析未启用」。  
**理由**：90 天窗口通常足够（约 60 日线 → 12 周线），但防御性处理必要。

## Risks / Trade-offs

- **[90天窗口不足 MA20W]** MA20W 需 20 周 = 100 个交易日，90 天窗口仅约 60 日线 → 12 周线，MA20W 将降级为 MA12W → Mitigation：MA20W 不足时用可用最大窗口替代，`warnings` 注明
- **[聚合边界行为]** 本周未完结的周 K 线（本周仍在进行）数据不完整（high/low/volume 为截至当日） → Mitigation：标记最后一周为「进行中」，不影响已完整周的指标计算
- **[参数增加配置复杂度]** `IndicatorParams` 新增 3 个字段 → Mitigation：均有默认值，外部不感知
