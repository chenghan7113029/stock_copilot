# tech-indicator-calculator Specification

## Purpose
TBD - created by archiving change add-tech-analyzer-core. Update Purpose after archive.

## Requirements

### Requirement: MA（移动平均线）计算
`IndicatorCalculator` SHALL 计算 MA5、MA10、MA20、MA60（简单移动平均），及当前价相对各均线的乖离率（`bias_ma5/10/20`）。数据不足 60 日时 MA60 SHALL 用 MA20 替代。

#### Scenario: 标准多头排列数据
- **WHEN** 传入至少 60 日 OHLCV 数据（收盘价持续上涨趋势）
- **THEN** MA5 > MA10 > MA20 > MA60，乖离率与各均线数值通过 pandas rolling mean 可重现

#### Scenario: MA60 数据不足
- **WHEN** 传入数据行数 < 60
- **THEN** MA60 字段等于 MA20 值，结果中包含「MA60 数据不足，以 MA20 替代」警告

---

### Requirement: MACD（12/26/9）计算
`IndicatorCalculator` SHALL 计算 DIF（EMA12 - EMA26）、DEA（DIF 的 EMA9）、MACD 柱（(DIF-DEA)×2），使用 `ewm(span=N, adjust=False)` 口径（与主流 K 线软件一致）。

#### Scenario: 固定数据验证 MACD 数值
- **WHEN** 传入 60 日固定收盘价序列（已知答案）
- **THEN** 计算结果 DIF / DEA / MACD 柱与参考值偏差 < 1e-4

#### Scenario: 数据不足 26 日
- **WHEN** 传入数据行数 < 26（慢线最小要求）
- **THEN** MACD 相关字段返回 `None`，`macd_status` 为 BULLISH（中性默认值）

---

### Requirement: RSI（6/12/24）计算
`IndicatorCalculator` SHALL 计算三档周期的 RSI，使用 Wilder's EMA 口径（`ewm(alpha=1/period, adjust=False)`）。以 RSI(12) 为主要评分依据。

#### Scenario: 固定数据验证 RSI 数值
- **WHEN** 传入 60 日固定收盘价序列
- **THEN** RSI(6)、RSI(12)、RSI(24) 与 Wilder's EMA 公式参考值偏差 < 1e-4

#### Scenario: NaN 填充
- **WHEN** 计算初始几日存在 NaN（历史数据不足一个周期）
- **THEN** NaN 值 SHALL 填充为 50（中性默认值）

---

### Requirement: KDJ（9/3/3）随机指标计算
`IndicatorCalculator` SHALL 计算 K、D、J 值，使用标准公式：RSV 基于 9 日最高/最低价，K 和 D 均以 1/3 权重指数平滑，J = 3K - 2D。J 值 SHALL 保留原始值（不 clip 到 [0,100]）。

#### Scenario: 固定数据验证 KDJ 数值
- **WHEN** 传入 30 日固定 OHLCV 序列
- **THEN** K、D、J 值与标准公式参考值偏差 < 1e-4

#### Scenario: J 值超界处理
- **WHEN** 计算结果 J > 100 或 J < 0
- **THEN** J 值保留原始数值（如 J = 115.2），`kdj_status` 叠加 OVERBOUGHT（J>100）或 OVERSOLD（J<0），`risk_factors` 追加「KDJ J 值超界：{j:.1f}」

---

### Requirement: 量能分析
`IndicatorCalculator` SHALL 计算 `volume_ratio_5d`（当日成交量 / 前 5 日均量），并基于量比与价格涨跌方向判断 `VolumeStatus` 枚举（HEAVY_VOLUME_UP/DOWN/SHRINK_VOLUME_UP/DOWN/NORMAL）。

#### Scenario: 缩量回调识别
- **WHEN** 当日成交量 / 5 日均量 < 0.7 且当日价格下跌
- **THEN** `volume_status = SHRINK_VOLUME_DOWN`，`volume_trend` 包含「缩量回调，洗盘特征明显」

#### Scenario: 放量下跌识别
- **WHEN** 当日成交量 / 5 日均量 > 1.5 且当日价格下跌
- **THEN** `volume_status = HEAVY_VOLUME_DOWN`，`volume_trend` 包含「放量下跌，注意风险」

---

### Requirement: 支撑/压力位识别
`IndicatorCalculator` SHALL 判断 MA5 和 MA10 是否构成有效支撑（价格在均线上方且距离 ≤ 2%），并收集近 20 日高点作为压力位。

#### Scenario: MA5 支撑有效
- **WHEN** 当前价 >= MA5 且 |当前价 - MA5| / MA5 <= 0.02
- **THEN** `support_ma5 = True`，MA5 值加入 `support_levels`

#### Scenario: 价格跌破所有均线
- **WHEN** 当前价 < MA5 < MA10 < MA20
- **THEN** `support_ma5 = False`，`support_ma10 = False`，`support_levels` 为空列表
