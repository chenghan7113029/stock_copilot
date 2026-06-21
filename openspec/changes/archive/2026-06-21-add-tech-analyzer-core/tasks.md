## 1. 数据模型与配置层

- [x] 1.1 创建 `src/service/tech/models/` 目录及 `__init__.py`
- [x] 1.2 创建 `src/service/tech/models/tech_result.py`：实现 `TrendStatus`、`VolumeStatus`、`MACDStatus`、`RSIStatus`、`KDJStatus`、`BuySignal` 六个枚举；实现 `TechAnalysisResult` dataclass（含所有分组字段：均线/乖离率/量能/支撑/MACD/RSI/KDJ/信号/元数据）
- [x] 1.3 创建 `src/service/tech/config.py`：实现 `IndicatorParams` dataclass（MA 周期、MACD 12/26/9、RSI 6/12/24、KDJ 9/3/3、量能阈值 0.7/1.5、支撑容忍度 2%）；实现 `ScoringParams` dataclass（6 维度权重总和 100、乖离率阈值 5.0%、买入信号阈值 75/60/45/30）；实现 `TechAnalysisConfig` dataclass 组合两者

## 2. K 线 DAO 层

- [x] 2.1 创建 `src/dao/kline_repo.py`：实现 `KlineRepo` 类；建表逻辑（`kline` 表，`code + trade_date` 联合主键，字段：open/high/low/close/volume REAL）；`query_range(code, start_date, end_date) → list[dict]`；`upsert_batch(records: list[dict]) → None`

## 3. K 线数据获取层

- [x] 3.1 修改 `src/data_provider/baostock/fetcher.py`：新增 `fetch_kline(code, start_date, end_date) → pd.DataFrame` 方法，调用 `bs.query_history_k_data_plus`，字段 `date,open,high,low,close,volume`，前复权（`adjustflag="2"`），返回标准 OHLCV DataFrame（date 为 str，其余为 float）
- [x] 3.2 修改 `src/data_provider/akshare/fetcher.py`：新增 `fetch_kline(code, start_date, end_date) → pd.DataFrame` 方法，调用 `ak.stock_zh_a_hist`（前复权），对齐返回列名与 Baostock 一致
- [x] 3.3 创建 `src/data_provider/kline_provider.py`：实现 `KlineProvider` 类；`get_kline(code, days=90) → pd.DataFrame` 实现完整逻辑：① 计算区间 → ② 查缓存 → ③ 空洞检测（API 返回日期集合与缓存集合差集）→ ④ 批量拉取缺失（Baostock 主，AKShare 备）→ ⑤ 回填历史到 DB（当日不写）→ ⑥ 合并返回；缺口 > 5 日且失败时追加 warnings；两者均失败抛 `KlineUnavailableError`

## 4. 指标计算层

- [x] 4.1 创建 `src/service/tech/calculator.py`：实现 `IndicatorCalculator` 类（纯 pandas，无 IO）；`calculate(df, params: IndicatorParams) → TechIndicators`（中间数据类）
- [x] 4.2 实现 `_calculate_mas(df)` → MA5/10/20/60（不足 60 日时 MA60=MA20）及 bias_ma5/10/20
- [x] 4.3 实现 `_calculate_macd(df, params)` → DIF/DEA/MACD 柱（`ewm(span=N, adjust=False)`）
- [x] 4.4 实现 `_calculate_rsi(df, params)` → RSI(6/12/24)（Wilder's EMA：`ewm(alpha=1/period, adjust=False)`，NaN 填充 50）
- [x] 4.5 实现 `_calculate_kdj(df, params)` → K/D/J（RSV 基于 N 日高低价，K/D 各以 1/3 权重平滑，J 保留原始值不裁剪）
- [x] 4.6 实现 `_analyze_volume(df, params)` → volume_ratio_5d 与 VolumeStatus 判断
- [x] 4.7 实现 `_analyze_support_resistance(df, result, params)` → support_ma5/ma10（价格在均线 2% 以内且不低于均线）、support_levels、resistance_levels（近 20 日高点）

## 5. 趋势与评分层

- [x] 5.1 创建 `src/service/tech/scorer.py`：定义 `ScoringEngine` Protocol（`score(indicators, params) → TechSignal`）；实现 `BullTrendScorer` 类
- [x] 5.2 实现趋势状态判断（`_analyze_trend`）：基于 MA5/10/20 排列 + 前 5 日扩散度变化，输出 TrendStatus（7 级）+ trend_strength（0~100）
- [x] 5.3 实现 MACD 状态判断（`_analyze_macd`）：金叉/死叉/零轴穿越/多空头 7 级枚举
- [x] 5.4 实现 RSI 状态判断（`_analyze_rsi`）：5 级枚举（超买/强势/中性/弱势/超卖），以 RSI(12) 为主
- [x] 5.5 实现 KDJ 状态判断（`_analyze_kdj`）：5 级枚举；J > 100 叠加 OVERBOUGHT，J < 0 叠加 OVERSOLD，追加 risk_factors 提示
- [x] 5.6 实现综合评分（`_generate_signal`）：6 维度加权（趋势 30 + 乖离率 20 + 量能 15 + 支撑 10 + MACD 15 + 动量 10）；极强趋势低评分时追加人工复核提示；BuySignal 由评分 + 趋势状态共同决定（空头强制 STRONG_SELL）

## 6. Facade 层

- [x] 6.1 创建 `src/service/tech/analyzer.py`：实现 `TechAnalyzer` 类；构造函数接受 `KlineProvider` 依赖注入；实现 `analyze(code) → TechAnalysisResult`（含非 A 股拒绝 `UnsupportedMarketError`、K 线失败降级处理）
- [x] 6.2 实现 `TechAnalyzer.from_config(config_dict)` 类方法：自动构造 `KlineRepo → KlineProvider → TechAnalyzer` 依赖链
- [x] 6.3 创建 `src/service/tech/__init__.py`：导出 `TechAnalyzer`、`TechAnalysisResult`、`TechAnalysisConfig`、`TrendStatus`、`BuySignal`

## 7. 单元测试

- [x] 7.1 创建 `test/service/tech/test_calculator.py`：
  - 固定 60 日 OHLCV 序列 → 验证 MA5/10/20 数值与 pandas rolling mean 一致
  - 固定序列 → 验证 MACD DIF/DEA 偏差 < 1e-4
  - 固定序列 → 验证 RSI(12) 偏差 < 1e-4（Wilder's EMA）
  - 固定序列 → 验证 KDJ K/D/J 偏差 < 1e-4
  - J 值超界场景：J > 100 触发 OVERBOUGHT，risk_factors 含超界提示
  - MA60 数据不足时使用 MA20 替代
  - 缩量回调 / 放量下跌 VolumeStatus 识别
  - MA5 支撑有效 / 价格跌破均线 support 识别
- [x] 7.2 创建 `test/service/tech/test_kline_provider.py`：
  - mock KlineRepo（空缓存）+ mock fetcher → 验证首次请求拉取并回填
  - mock KlineRepo（部分缓存命中）→ 验证仅拉取缺失日期
  - mock KlineRepo（有空洞）→ 验证空洞检测并批量回填
  - 当日数据不写入缓存（verify upsert 不含当日日期）
  - Baostock 失败 → fallback AKShare
  - 两者均失败 → 抛出 KlineUnavailableError
  - 空洞 > 5 日且失败 → warnings 含缺口提示
- [x] 7.3 创建 `test/service/tech/test_analyzer.py`：
  - mock KlineProvider 返回正常数据 → 验证完整 TechAnalysisResult 字段非 None
  - 非 A 股代码 → UnsupportedMarketError
  - KlineProvider 失败 → 降级结果（buy_signal=WAIT，risk_factors 含失败原因）
  - STRONG_BULL + score < 45 → risk_factors 含人工复核提示
  - 空头趋势 → buy_signal = STRONG_SELL（无视评分）
  - from_config 工厂方法可用（传入 db_path）
  - 自定义 ScoringParams 生效（覆盖 bias_threshold）
- [x] 7.4 创建 `test/service/tech/test_consistency_with_ref.py`：
  - 4 组 synthetic OHLCV fixture vs ref `StockTrendAnalyzer`
  - 共有数值因子相对误差 ≤ ±0.1%；枚举/布尔完全一致
  - `LegacyRefScorer` 的 `signal_score` 与 ref 完全一致（KDJ 不参与 ref 比对）
- [x] 7.5 运行 `python -m pytest test/service/tech/ -v` 确认全部通过；运行 `python -m ruff check src/service/tech/ src/data_provider/kline_provider.py src/dao/kline_repo.py` 确认无 lint 错误

## 8. 文档更新

- [x] 8.1 更新 `docs/mrd/features/tech-analysis.md`：将「实现现状」中 `❌` 项改为 `✅`；变更记录中新增本 Change 条目
