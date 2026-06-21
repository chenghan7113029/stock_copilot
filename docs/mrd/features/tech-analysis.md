# 技术面分析模块 — 需求细则（MRD）

> 最后更新：2026-06-21  
> 状态：细则 v2（P0 核心实现 ✅；V1.x 扩展待建）  
> 上级文档：[product-overview.md](../product-overview.md) §5.1.2  
> 关联设计：[tech-analysis-reference.md](../../design/tech-analysis-reference.md)  
> 参考实现：`ref/daily_stock_analysis/src/stock_analyzer.py`

## 变更记录

| 日期 | Change | 摘要 |
|------|--------|------|
| 2026-06-21 | explore | 初稿：基于 `daily_stock_analysis` 探索，确立技术面指标体系、评分框架、交易风格抽象、数据层设计 |
| 2026-06-21 | decisions | **D-1 已决策**：K 线持久化 SQLite，表名 `kline`，当日实时拉取，历史命中缓存；**D-4 已决策**：KDJ J 值保留原始值，枚举判断层处理超界；**D-6 已决策**：极强趋势低评分时输出提示并保留人工判断空间；**D-7 已决策**：V1.x 支持周 K 线趋势，月 K 线暂不实现 |
| 2026-06-21 | add-tech-analyzer-core | P0 核心交付：KlineProvider + KlineRepo + IndicatorCalculator + BullTrendScorer + TechAnalyzer；Baostock/AKShare fetch_kline；27 项单测（含 ref 一致性 ±0.1%） |

---

## 1. 模块目标

**一句话：** 基于日 K 线 OHLCV 数据，计算均线、MACD、RSI、KDJ 等技术指标，输出 **趋势状态 + 买入信号评分 + 操作建议**，作为双轨分析报告的技术面输入。

**要解决的核心问题：**

- 避免在下跌通道中因价值面便宜而「接飞刀」——技术面确认趋势方向才介入；
- 识别有效买点：「不追高」（乖离率超阈值拒绝介入）、「回踩支撑再买」（均线支撑验证）；
- 提供机械化止损参考（跌破 MA20 或关键结构位）；
- 量化均线排列、MACD 金死叉、RSI/KDJ 超买超卖，去除感性判断。

**不解决的问题：**

- 盘中实时监控与推送（V1 仅支持日线 EOD 分析）；
- K 线形态识别（锤头线、吞没形态等）—— V2 扩展；
- 北向资金、机构持仓、融资融券等资金面指标 —— 情绪模块负责；
- 个股所处行业与板块热度 —— 情绪模块负责。

---

## 2. 范围与优先级

### 2.1 V1 必须实现（当前 OpenSpec 范围）

| # | 功能点 | 优先级 | 说明 |
|---|--------|--------|------|
| F-01 | Baostock K 线数据获取 | P0 | `fetch_kline(code, start, end)` → OHLCV DataFrame |
| F-02 | AKShare K 线数据获取（fallback） | P0 | Baostock 不可用时自动切换 |
| F-03 | KlineProvider 主备切换封装 | P0 | `get_kline(code, days=90)` 统一接口；内含缓存逻辑（见 F-03a） |
| F-03a | K 线 SQLite 缓存（kline 表） | P0 | 当日实时拉取；历史日期命中缓存直接返回；缓存缺失时实时拉取并回填 |
| F-04 | MA5/10/20/60 计算 | P0 | 简单移动平均 |
| F-05 | 乖离率（BIAS）计算 | P0 | 相对 MA5/10/20 的偏离百分比 |
| F-06 | MACD (12/26/9) 计算 | P0 | DIF / DEA / 柱状图 |
| F-07 | RSI (6/12/24) 计算 | P0 | Wilder's EMA 口径 |
| F-08 | KDJ (9/3/3) 计算 | P0 | 随机指标 K/D/J |
| F-09 | 量能分析（volume_ratio_5d） | P0 | 当日量 / 5 日均量；量能状态枚举 |
| F-10 | 支撑/压力位识别 | P0 | MA5/10/20 支撑 + 近 20 日高点压力 |
| F-11 | 趋势状态评估（7 级） | P0 | 基于均线排列 + 趋势强度 |
| F-12 | 综合评分系统（0-100 分） | P0 | 6 维度加权；权重可配置 |
| F-13 | 买入信号枚举（6 级） | P0 | 强烈买入 → 强烈卖出 |
| F-14 | TechAnalyzer Facade | P0 | `analyze(code) → TechAnalysisResult` |
| F-15 | TechAnalysisConfig 可配置 | P0 | 所有参数有默认值，支持外部覆盖 |

### 2.2 V1.x 扩展（已识别，待规划）

| # | 功能点 | 说明 |
|---|--------|------|
| F-16 | 实时行情融合 | 当日开盘后用实时价格补充 K 线末端，使 MA 计算不滞后一天 |
| F-17 | 筹码分布 | 获利比例、套牢盘比例（AKShare `stock_cyq_em`） |
| F-18 | K 线形态识别 | 锤头线、吞没、十字星等经典形态 |
| F-19 | 布林带（Bollinger Bands） | 均值 ± N×σ，判断波动率收缩/扩张 |
| F-20 | 周 K 线趋势分析 | 基于周 K 线（5 日聚合）计算 MA/MACD/RSI，输出更大级别趋势判断；与日线趋势联合解读 |

### 2.3 V2 及以后（明确不在当前范围）

- 盘中技术分析（分钟级 K 线）
- 北向资金 / 机构席位技术信号
- 期权隐含波动率技术指标

---

## 3. 交易风格与评分系统

### 3.1 核心交易理念（V1 默认风格：Bull Trend Strategy）

技术面分析基于以下交易哲学（可通过配置覆盖参数，未来通过替换 `ScoringEngine` 实现风格切换）：

1. **严进策略**：不追高，每笔交易优先保证胜率而非捕捉最大涨幅；
2. **趋势交易**：MA5 > MA10 > MA20 多头排列是前提条件，顺势而为；
3. **效率优先**：筹码结构良好（缩量回调）的回踩机会优于放量追涨；
4. **买点偏好**：在 MA5/MA10 附近回踩、不破支撑时介入。

### 3.2 评分维度（总分 100 分）

| 维度 | 权重 | 评分逻辑摘要 |
|------|------|------------|
| 趋势排列 | 30 分 | 强势多头 30 分 → 多头 26 → 弱势多头 18 → 盘整 12 → 弱势空头 8 → 空头 4 → 强势空头 0 |
| 乖离率 | 20 分 | 价格在 MA5 附近最高分；超过 `bias_threshold`（默认 5%）扣至 4 分，严禁追高 |
| 量能 | 15 分 | 缩量回调 15 > 放量上涨 12 > 量能正常 10 > 缩量上涨 6 > 放量下跌 0 |
| 支撑 | 10 分 | MA5 支撑 +5；MA10 支撑 +5 |
| MACD | 15 分 | 零轴上金叉 15 > 金叉 12 > 上穿零轴 10 > 多头 8 > 空头 2 > 零轴下穿/死叉 0 |
| 动量（RSI+KDJ） | 10 分 | RSI 分项 6 分 + KDJ 分项 4 分，超买扣分，超卖加分 |

> **关键约束 1**：强势空头排列下（趋势强度 <25），最终 `buy_signal` 强制降为 SELL 或 STRONG_SELL，无视评分。
>
> **关键约束 2（D-6 决策）**：若趋势状态为 STRONG_BULL（趋势强度 ≥ 90）但综合评分 < 45（例如量价严重背离、乖离率极高），系统**不自动升级信号**，保留低评分结论，同时在 `risk_factors` 中写入「趋势强劲但其他维度信号疲弱，建议人工复核量价背离情况」，供使用者自行判断是否介入。

### 3.3 买入信号阈值（可配置）

| 信号 | 条件 |
|------|------|
| 强烈买入 | 评分 ≥ 75 **且** 趋势为 STRONG_BULL 或 BULL |
| 买入 | 评分 ≥ 60 **且** 趋势为 STRONG_BULL/BULL/WEAK_BULL |
| 持有 | 评分 ≥ 45 |
| 观望 | 评分 ≥ 30 |
| 卖出 | 趋势非空头，评分 < 30 |
| 强烈卖出 | 趋势为 BEAR 或 STRONG_BEAR |

---

## 4. 数据模型与输出契约

### 4.1 输入：K 线数据帧（来自 KlineProvider）

```
DataFrame 标准列名：
  date   (str/datetime)  - 交易日期
  open   (float)         - 开盘价
  high   (float)         - 最高价
  low    (float)         - 最低价
  close  (float)         - 收盘价
  volume (float)         - 成交量

要求：至少 26 个交易日（MACD 慢线最小要求）；推荐 90 天窗口（约 60 个交易日）以支持 MA60。
```

### 4.2 输出：TechAnalysisResult

```python
@dataclass
class TechAnalysisResult:
    code: str

    # 趋势
    trend_status: TrendStatus        # 7 级枚举
    ma_alignment: str                # 均线排列描述文字
    trend_strength: float            # 0–100

    # 均线数据
    current_price: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float

    # 乖离率
    bias_ma5: float                  # (close - MA5) / MA5 × 100%
    bias_ma10: float
    bias_ma20: float

    # 量能
    volume_status: VolumeStatus      # 5 级枚举
    volume_ratio_5d: float           # 当日量 / 5 日均量
    volume_trend: str                # 量能趋势描述

    # 支撑/压力
    support_ma5: bool
    support_ma10: bool
    support_levels: list[float]
    resistance_levels: list[float]

    # MACD
    macd_dif: float
    macd_dea: float
    macd_bar: float
    macd_status: MACDStatus          # 7 级枚举
    macd_signal: str

    # RSI
    rsi_6: float
    rsi_12: float
    rsi_24: float
    rsi_status: RSIStatus            # 5 级枚举
    rsi_signal: str

    # KDJ（新增）
    kdj_k: float
    kdj_d: float
    kdj_j: float
    kdj_status: KDJStatus            # 5 级枚举
    kdj_signal: str

    # 综合信号
    buy_signal: BuySignal            # 6 级枚举
    signal_score: int                # 0–100
    signal_reasons: list[str]        # 看多理由
    risk_factors: list[str]          # 风险提示
```

### 4.3 状态枚举定义

| 枚举类 | 取值 |
|--------|------|
| `TrendStatus` | STRONG_BULL / BULL / WEAK_BULL / CONSOLIDATION / WEAK_BEAR / BEAR / STRONG_BEAR |
| `VolumeStatus` | HEAVY_VOLUME_UP / HEAVY_VOLUME_DOWN / SHRINK_VOLUME_UP / SHRINK_VOLUME_DOWN / NORMAL |
| `MACDStatus` | GOLDEN_CROSS_ZERO / GOLDEN_CROSS / BULLISH / CROSSING_UP / CROSSING_DOWN / BEARISH / DEATH_CROSS |
| `RSIStatus` | OVERBOUGHT / STRONG_BUY / NEUTRAL / WEAK / OVERSOLD |
| `KDJStatus` | OVERBOUGHT / GOLDEN_CROSS / NEUTRAL / DEATH_CROSS / OVERSOLD |
| `BuySignal` | STRONG_BUY / BUY / HOLD / WAIT / SELL / STRONG_SELL |

---

## 5. 配置模型

### 5.1 TechAnalysisConfig 结构

```python
@dataclass
class IndicatorParams:
    # 均线
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60])

    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # RSI
    rsi_short: int = 6
    rsi_mid: int = 12
    rsi_long: int = 24
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # KDJ
    kdj_period: int = 9       # 随机指标计算周期
    kdj_smooth_k: int = 3     # K 值平滑系数（3 表示 1/3 权重）
    kdj_smooth_d: int = 3     # D 值平滑系数
    kdj_overbought: float = 80.0
    kdj_oversold: float = 20.0

    # 量能
    volume_shrink_ratio: float = 0.7   # 缩量阈值（当日量/5日均量）
    volume_heavy_ratio: float = 1.5    # 放量阈值
    ma_support_tolerance: float = 0.02 # MA 支撑容忍度（2%）


@dataclass
class ScoringParams:
    # 维度权重（总和 = 100）
    trend_weight: int = 30
    bias_weight: int = 20
    volume_weight: int = 15
    support_weight: int = 10
    macd_weight: int = 15
    rsi_weight: int = 6           # 动量维度 RSI 分项（最大 6 分）
    kdj_weight: int = 4           # 动量维度 KDJ 分项（最大 4 分）

    # 乖离率阈值
    bias_threshold: float = 5.0   # 超过此值严禁追高
    strong_trend_bias_multiplier: float = 1.5  # 强势趋势时放宽阈值倍数

    # 买入信号阈值
    strong_buy_threshold: int = 75
    buy_threshold: int = 60
    hold_threshold: int = 45
    wait_threshold: int = 30


@dataclass
class TechAnalysisConfig:
    indicator_params: IndicatorParams = field(default_factory=IndicatorParams)
    scoring_params: ScoringParams = field(default_factory=ScoringParams)
    kline_days: int = 90          # 获取 K 线的天数窗口
```

---

## 6. 数据依赖

### 6.1 K 线数据（新增需求）

| 数据项 | 来源 | 接口 | 备注 |
|--------|------|------|------|
| 日 K 线 OHLCV | Baostock（主） | `bs.query_history_k_data_plus` | 前复权；免 token |
| 日 K 线 OHLCV | AKShare（备） | `ak.stock_zh_a_hist` | Baostock 失败时自动切换 |

> **与现有 data_provider 的关系**：现有 `BaostockFetcher`/`AKShareFetcher` 仅处理财报数据，K 线获取需在两个 fetcher 中**各新增一个 `fetch_kline()` 方法**，同时新建独立的 `KlineProvider` 管理主备切换（不走现有 `SourceManager`，因为 K 线是时序数据，逻辑不同于逐字段合并）。

### 6.2 K 线缓存策略（D-1 决策）

**方案：SQLite 本地缓存，按交易日精确命中**

```
kline 表结构（SQLite）：
  code        TEXT    -- 股票代码（6位）
  trade_date  TEXT    -- 交易日期（YYYY-MM-DD）
  open        REAL
  high        REAL
  low         REAL
  close       REAL
  volume      REAL
  PRIMARY KEY (code, trade_date)
```

**读取逻辑（KlineProvider 内部）**：

```
get_kline(code, days=90):
  1. 计算所需日期范围 [start_date, end_date]
  2. 从 kline 表查询已有的 trade_date 集合（cached_dates）
  3. 计算应有的交易日集合（expected_dates）：
     - 直接用 [start_date, end_date] 区间向 Baostock 请求时
       返回的日期即为真实交易日，无需维护独立交易日历
  4. 识别需要拉取的日期：
     - 当日（today）：始终实时拉取（价格可能盘中更新）
     - 历史日期：gap_dates = expected_dates - cached_dates
       （包含：程序多日未运行导致的中间空白 + 首次请求）
  5. 若 gap_dates 非空：
     - 以区间方式批量拉取 gap_dates（一次 API 调用覆盖整段缺失）
     - 写入 kline 表（仅历史数据，当日不写）
  6. 从 kline 表重新查询完整区间，合并当日实时数据
  7. 返回按 trade_date 排序的完整 OHLCV DataFrame
```

**空洞检测举例**：

```
场景：程序上次运行在 6/16（周一），今日 6/21（周六，但分析昨日收盘）
  DB 中已有：6/12, 6/13, 6/16
  今日请求 90 天窗口，end_date = 6/20（最近交易日）
  Baostock 返回的历史数据揭示真实交易日：6/12~6/20 共 7 天
  gap_dates = {6/17, 6/18, 6/19, 6/20}（4天空洞）
  → 批量拉取 6/17~6/20，写入 DB，合并后返回完整序列
```

> **关键约束**：
> - 只有历史数据（日期 < 当日）才写入缓存；当日数据每次实时拉取，不缓存（防止盘中数据污染）；
> - 空洞检测基于「请求时按区间拉取」自然覆盖，无需维护独立的 A 股交易日历表；
> - 若 Baostock 拉取失败且缺口 > 5 个交易日，在 `warnings` 中注明「K 线数据存在缺口，指标计算可能不准确」。

### 6.3 不需要的数据（V1 明确排除）

| 数据项 | 排除原因 |
|--------|---------|
| 实时行情（盘中价格） | V1 仅做 EOD 分析，用最新收盘价足够 |
| 筹码分布 | V1 不实现，V1.x 扩展 |
| 北向资金 / 龙虎榜 | 属于情绪模块 |
| 分钟级 K 线 | V2 盘中分析时引入 |

---

## 7. 模块架构（代码层）

```
src/
├─ dao/
│   └─ kline_repo.py           ← 新建：KlineRepo（SQLite kline 表 CRUD）
│
├─ data_provider/
│   ├─ baostock/fetcher.py     ← 新增 fetch_kline(code, start, end) → DataFrame
│   ├─ akshare/fetcher.py      ← 新增 fetch_kline(code, start, end) → DataFrame
│   └─ kline_provider.py       ← 新建：KlineProvider（主备切换 + 缓存读写）
│
└─ service/tech/
    ├─ __init__.py              ← 导出公共接口
    ├─ config.py                ← TechAnalysisConfig, IndicatorParams, ScoringParams
    ├─ calculator.py            ← IndicatorCalculator（纯 pandas，无 IO）
    ├─ scorer.py                ← ScoringEngine（BullTrendScorer 实现）
    ├─ analyzer.py              ← TechAnalyzer Facade（依赖注入 KlineProvider）
    └─ models/
        ├─ __init__.py
        └─ tech_result.py       ← TechAnalysisResult + 所有状态枚举

test/service/tech/
    ├─ test_calculator.py       ← 固定 OHLCV → 验证 MA/MACD/RSI/KDJ 数值
    ├─ test_kline_provider.py   ← mock DAO + fetcher，验证缓存命中/gap 检测/回填逻辑
    └─ test_analyzer.py         ← mock KlineProvider → 验证 analyze 输出契约
```

### 7.1 调用流程

```
TechAnalyzer.analyze(code)
    │
    ├─ 1. KlineProvider.get_kline(code, days=90)
    │       ├─ KlineRepo.query_range(code, start, end)  ← 查询已缓存日期集合
    │       ├─ 空洞检测：gap_dates = 区间内应有日期 - 已缓存日期
    │       │   （含：程序多日未运行导致的历史空白）
    │       ├─ 当日：始终实时拉取（不走缓存）
    │       ├─ gap_dates 非空：
    │       │     try BaostockFetcher.fetch_kline(gap 区间)
    │       │     fallback: AKShareFetcher.fetch_kline()
    │       │     KlineRepo.upsert(回填历史)  ← 仅历史，当日不写
    │       └─ gap > 5 日且拉取失败 → warnings 追加数据缺口提示
    │
    ├─ 2. IndicatorCalculator.calculate(df, indicator_params)
    │       → TechIndicators(ma, macd, rsi, kdj, volume, bias, support)
    │
    ├─ 3. ScoringEngine.score(indicators, scoring_params)
    │       → TechSignal(score, buy_signal, reasons, risks)
    │           └─ 若 STRONG_BULL + score < 45：risk_factors 追加人工复核提示
    │
    └─ 4. 组装 TechAnalysisResult
```

---

## 8. 交易风格可扩展性设计

V1 实现 `BullTrendScorer`（多头趋势 + 严进策略）作为 `ScoringEngine` 的唯一实现。
架构预留替换能力：

```python
class ScoringEngine(Protocol):
    """交易风格评分协议。未来不同交易风格替换此接口即可。"""
    def score(
        self,
        indicators: TechIndicators,
        params: ScoringParams,
    ) -> TechSignal: ...

# V1 实现
class BullTrendScorer:
    """严进多头趋势风格：不追高 + 回踩支撑 + 量能验证。"""
    def score(self, indicators: TechIndicators, params: ScoringParams) -> TechSignal:
        ...

# 未来可添加
# class BreakoutScorer: ...       # 放量突破风格
# class MeanReversionScorer: ... # 均值回归风格
```

**当前阶段（V1）不实现多风格切换**，只要接口正确，后续需要时替换零改动。

---

## 9. 设计决策记录（Design Decisions）

| # | 问题 | 状态 | 决策 |
|---|------|------|------|
| D-1 | K 线数据是否持久化到 DB | ✅ 已决策 | 持久化到 SQLite `kline` 表；当日实时拉取；历史数据启用空洞检测——每次请求时自动识别区间内缺失的交易日（含程序多日未运行导致的历史断档），批量拉取并回填；当日数据收盘前不写入缓存；缺口 >5 日且拉取失败时在 `warnings` 中提示数据不完整 |
| D-2 | 前复权 vs 后复权 | ✅ 已决策 | 前复权（`adjustflag=2`）；与主流 K 线图一致，无异议 |
| D-3 | MA60 数据不足时的 fallback | ✅ 已决策 | 数据 <60 日时用 MA20 替代 MA60，并在 `risk_factors` 注明「MA60 数据不足，以 MA20 替代」 |
| D-4 | KDJ J 值超界如何处理 | ✅ 已决策 | 保留原始值（不 clip）；枚举判断层显式处理：`J > 100` 视为极端超买叠加 OVERBOUGHT，`J < 0` 视为极端超卖叠加 OVERSOLD；`risk_factors` 中注明「KDJ J 值超界：{j:.1f}」 |
| D-5 | 强势趋势乖离率宽松策略 | ✅ 已决策 | `trend_strength ≥ 70 且 STRONG_BULL` 时，`bias_threshold × 1.5` 生效；来自 ref 实现 |
| D-6 | `signal_score` 低但趋势极强时如何处理 | ✅ 已决策 | 不自动升级信号；保留低分结论；在 `risk_factors` 追加「趋势强劲但其他维度信号疲弱，建议人工复核量价背离情况」；最终买卖决策由使用者判断 |
| D-7 | 是否支持周/月 K 线分析 | ✅ 已决策 | V1 仅日线；V1.x 新增周 K 线趋势分析（F-20）；月 K 线级别过大、对短中线操作参考有限，暂不实现 |

---

## 10. 功能缺口与路线图

### 10.1 当前状态

```
技术面模块实现现状（2026-06-21）
═══════════════════════════════════
✅ 参考实现分析（ref/daily_stock_analysis）
✅ MRD & 方法论参考文档
✅ K 线数据获取能力（Baostock 主 + AKShare 备 + SQLite 缓存/空洞回填）
✅ 指标计算层（MA/MACD/RSI/KDJ/量能/支撑）
✅ 评分引擎（BullTrendScorer，6 维度 100 分制）
✅ TechAnalyzer Facade
✅ 单元测试（27 项，含 ref 一致性 4 项 ±0.1%）
```

### 10.2 优先级路线图

| 优先级 | Change 名称（建议） | 内容 | 依赖 |
|--------|---------------------|------|------|
| P0 | `add-tech-analyzer-core` | F-01~F-03a（含 kline 缓存）+ F-04~F-15 全量实现 | 无 |
| P1 | `add-realtime-overlay` | 实时行情融合（F-16）：当日盘中价格叠加 K 线末端 | P0 |
| P1 | `add-weekly-kline` | 周 K 线趋势分析（F-20）：5 日聚合 + 周线 MA/MACD/RSI | P0 |
| P2 | `add-chip-distribution` | 筹码分布（F-17）：获利/套牢比例 | P0 |
| V2 | `add-pattern-recognition` | K 线形态识别（F-18）：锤头、吞没等 | P0 |
| V2 | `add-bollinger-bands` | 布林带（F-19）：波动率收缩/扩张 | P0 |

### 10.3 与双轨分析的集成点

技术面 P0 完成后，下一个目标是将价值面（已完成）和技术面（待建）合并为统一的双轨分析 Facade：

```
DualTrackAnalyzer.analyze(code)
    ├─ ValueAnalyzer.analyze(code)   → ValueAnalysisResult
    ├─ TechAnalyzer.analyze(code)    → TechAnalysisResult
    └─ 组装 DualTrackReport {value, tech, combined_signal}
```

对应 product-overview §5.3「多维立体看板」与 LLM 综合报告的上层需求。

---

## 11. 验收标准

| 情形 | 标准 | 测试位置 |
|------|------|----------|
| 相同 OHLCV fixture vs ref `StockTrendAnalyzer` | 共有数值因子相对误差 ≤ ±0.1% | `test/service/tech/test_consistency_with_ref.py` |
| ref 共有枚举（趋势/量能/MACD/RSI/买入信号） | 与 ref 完全一致 | 同上 |
| ref 共有评分（LegacyRefScorer，RSI 动量 10 分） | `signal_score` 与 ref 完全一致 | 同上 |
| KDJ 指标 | stock_copilot 扩展项，ref 无对应，单独单测 | `test/service/tech/test_calculator.py` |
| BullTrendScorer（含 KDJ 动量 4 分） | 允许与 ref 总分不同，属预期扩展 | 生产默认路径 |

> **LegacyRefScorer**：仅用于 ref 一致性验收，生产默认使用 `BullTrendScorer`（RSI 6 + KDJ 4）。

---

## 12. 参考文献

- `ref/daily_stock_analysis/src/stock_analyzer.py` — 完整 `StockTrendAnalyzer` 实现（MA/MACD/RSI/评分）
- `ref/daily_stock_analysis/strategies/*.yaml` — 策略 YAML 定义（bull_trend、chan_theory 等）
- `ref/daily_stock_analysis/src/core/pipeline.py` — 完整技术面分析流水线
- `docs/design/tech-analysis-reference.md` — 各指标详细计算方法与应用场景
- `docs/mrd/features/value-analysis.md` — 价值面 MRD（技术面模块的对称参考）
