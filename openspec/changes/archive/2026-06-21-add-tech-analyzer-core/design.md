## Context

stock_copilot 当前已完成价值面分析的全量实现（23 种估值方法、编排层 Facade、数据提供者），但缺少技术面这一轨。参考实现 `ref/daily_stock_analysis/src/stock_analyzer.py` 提供了完整的 `StockTrendAnalyzer`（MA/MACD/RSI/评分），可作为核心指标计算和评分逻辑的直接参考。

技术面分析需要**日 K 线 OHLCV 时序数据**，与价值面使用的财报截面数据（一次拉取多字段）完全不同，需要独立的数据获取与缓存体系。

约束：
- 现有 `BaostockFetcher`/`AKShareFetcher` 只处理财报数据，需各自增加 K 线方法；
- 现有 `SourceManager` 是「多来源逐字段合并」模式，不适用于时序数据，K 线层需独立设计；
- K 线数据量大（90天 × N 只股票），程序可能不每天运行，需缓存与空洞检测；
- 所有计算必须与 ref 实现数值对齐（验收标准：固定输入下 MA/MACD/RSI/KDJ 数值与 ref 一致）。

## Goals / Non-Goals

**Goals:**
- 实现完整技术面分析链路：K 线获取 → 指标计算 → 评分 → `TechAnalysisResult`；
- K 线本地 SQLite 缓存，含空洞检测与自动回填；
- 所有配置（指标参数、评分权重、阈值）可在 `TechAnalysisConfig` 中覆盖；
- 交易风格通过 `ScoringEngine` Protocol 抽象，V1 仅实现 `BullTrendScorer`；
- 单元测试覆盖指标计算（固定数据验证）和 Facade（mock KlineProvider）。

**Non-Goals:**
- 实时行情融合（V1.x）；
- 周 K 线趋势分析（V1.x，F-20）；
- 筹码分布（V1.x）；
- K 线形态识别、布林带（V2）；
- 与 `ValueAnalyzer` 合并为双轨 Facade（下一个 Change）。

## Decisions

### D-1：KlineProvider 独立于 SourceManager

**决策**：`KlineProvider` 不走现有 `SourceManager`，独立实现主备切换逻辑。

**理由**：`SourceManager` 是「多来源逐字段合并」模式（适合财报数据），而 K 线是时序数据——只要拿到完整 OHLCV 序列即可，不需要字段级别的多源合并。独立的 `KlineProvider` 更简洁，职责更清晰。

**备选方案**：扩展 `SourceManager` 支持时序数据模式 → 增加现有模块复杂度，拒绝。

---

### D-2：K 线缓存策略（空洞检测）

**决策**：SQLite `kline` 表（`code + trade_date` 联合主键），每次请求时对比「已缓存日期集合」与「API 返回的实际交易日集合」，自动识别并回填缺失历史；当日数据实时拉取，不写缓存。

**关键设计**：无需维护独立的 A 股交易日历。空洞识别依赖 Baostock API 返回的实际日期——向 API 请求完整区间，返回的日期即为真实交易日（节假日自动跳过），然后做集合差即可。

**处理缺口警告**：若拉取失败且缺口 > 5 个交易日，在 `TechAnalysisResult.warnings` 中追加提示，不阻塞计算。

```
kline 表：
  PRIMARY KEY (code, trade_date)
  code         TEXT   -- 6 位 A 股代码
  trade_date   TEXT   -- YYYY-MM-DD
  open/high/low/close  REAL
  volume       REAL
```

---

### D-3：KDJ J 值不裁剪

**决策**：J 值保留原始值（可超出 [0, 100]）；状态枚举层显式处理超界：J > 100 叠加 OVERBOUGHT，J < 0 叠加 OVERSOLD，并追加到 `risk_factors`。

**理由**：J 值超界本身是信号（极端超买/超卖），裁剪会丢失信息；枚举判断层可以完整处理。

---

### D-4：评分权重与交易风格抽象层级

**决策**：V1 用「配置化参数」（`ScoringParams` dataclass）+ `ScoringEngine` Protocol，不实现多风格运行时切换。

**理由**：调权重走配置文件即可覆盖 80% 的定制需求；完整的策略模式是过度设计，等真正有第二种风格时再引入。

```python
class ScoringEngine(Protocol):
    def score(self, indicators: TechIndicators, params: ScoringParams) -> TechSignal: ...

class BullTrendScorer:   # V1 唯一实现
    def score(self, indicators: TechIndicators, params: ScoringParams) -> TechSignal: ...
```

---

### D-5：模块结构镜像 service/value/

**决策**：`service/tech/` 分层结构对称于 `service/value/`。

```
service/tech/
  config.py        — TechAnalysisConfig（IndicatorParams + ScoringParams）
  calculator.py    — IndicatorCalculator（纯计算，无 IO）
  scorer.py        — ScoringEngine Protocol + BullTrendScorer
  analyzer.py      — TechAnalyzer Facade
  models/
    tech_result.py — TechAnalysisResult + 所有枚举
```

`data_provider/kline_provider.py` 与 `dao/kline_repo.py` 独立于 service 层，按依赖方向约束注入。

---

### D-6：指标计算精度口径

**决策**：RSI 使用 Wilder's EMA（`ewm(alpha=1/period, adjust=False)`）；MACD EMA 使用标准指数加权（`ewm(span=N, adjust=False)`）；两者均与 ref 实现一致。

**理由**：Wilder's EMA 口径与主流 K 线图软件（通达信、同花顺）一致，用户体验更好；`adjust=False` 确保结果可重现。

---

### D-7：极强趋势低评分时的处理

**决策**：不自动升级信号；在 `risk_factors` 追加「趋势强劲但其他维度信号疲弱，建议人工复核量价背离情况」，保留低评分结论，交由使用者判断。

**触发条件**：`trend_status == STRONG_BULL（trend_strength >= 90）且 signal_score < 45`。

## Risks / Trade-offs

| 风险 | 缓解策略 |
|------|---------|
| Baostock 偶发连接失败 | 自动 fallback 到 AKShare；两者均失败时抛 `KlineUnavailableError`，`TechAnalyzer` 捕获后在 result 中标注 data 缺失原因 |
| K 线缓存表与股票代码未对齐（如 6 位 vs 带交易所前缀） | `KlineRepo` 内部统一用 6 位纯数字存储，`KlineProvider` 负责在写入前标准化 code |
| MA60 数据不足（历史 <60 天）| 用 MA20 替代，`risk_factors` 注明；不影响 MA5/10/20 的准确性 |
| 历史 K 线数据大量空洞（首次运行或长期未运行） | 批量区间拉取（一次 API 调用），正常情况下 90 天 = 约 60 个交易日，延迟可接受；缺口 >5 日且拉取失败时 warnings 提示 |
| 指标数值与主流软件存在细微差异 | 使用 Wilder's EMA 口径（与通达信一致）；单元测试用固定序列数值回归 |
