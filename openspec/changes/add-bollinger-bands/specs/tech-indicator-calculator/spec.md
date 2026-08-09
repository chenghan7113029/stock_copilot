## ADDED Requirements

### Requirement: 布林带（Bollinger Bands）计算
`IndicatorCalculator` SHALL 计算布林带中轨（`boll_period` 日收盘价简单移动平均，默认 20）、上轨（中轨 + `boll_std_mult` × N 日收盘价标准差，默认 2.0）、下轨（中轨 − `boll_std_mult` × 标准差）、带宽（`(上轨-下轨)/中轨`）。`boll_period == 20` 时 SHALL 复用已计算的 `MA20` 列作为中轨，避免重复计算；`boll_period` 为其他值时 SHALL 独立计算对应周期的移动平均。

#### Scenario: 标准参数下布林带计算
- **WHEN** 传入至少 20 日 OHLCV 数据，使用默认参数（`boll_period=20, boll_std_mult=2.0`）
- **THEN** `boll_mid` 等于 `MA20`，`boll_upper - boll_mid` 与 `boll_mid - boll_lower` 均等于 `2.0 × 20日收盘价标准差`，与 pandas `rolling(20).std()` 参考值偏差 < 1e-6

#### Scenario: 自定义周期不复用 MA20
- **WHEN** `boll_period=10`（非 20）
- **THEN** `boll_mid` 等于独立计算的 10 日移动平均，不等于 `MA20`

#### Scenario: 数据不足 boll_period 日
- **WHEN** 传入数据行数 < `boll_period`
- **THEN** 布林带相关字段返回默认值（0.0 或 None），`warnings` 包含「布林带数据不足」说明，不抛出异常

---

### Requirement: 布林带带宽百分位计算
`IndicatorCalculator` SHALL 基于 `boll_bandwidth_lookback`（默认 40）个交易日的历史带宽序列，计算当前带宽在该窗口内的百分位排名 `boll_percentile`（0~100，值越低代表当前带宽相对越窄）。可用带宽历史样本数少于 `boll_bandwidth_lookback` 时，SHALL 使用实际可用样本数计算百分位，并在 `warnings` 中说明「布林带带宽历史样本不足，百分位基于 {n} 个交易日计算」。

#### Scenario: 样本充足
- **WHEN** 可用带宽历史样本数 ≥ `boll_bandwidth_lookback`
- **THEN** `boll_percentile` 基于完整 `boll_bandwidth_lookback` 窗口计算，值域为 [0, 100]

#### Scenario: 样本不足时降级但不中断
- **WHEN** 可用带宽历史样本数 < `boll_bandwidth_lookback`（如仅有 25 个交易日可用）
- **THEN** `boll_percentile` 基于实际可用样本数计算，`warnings` 包含样本不足说明，不抛出异常、不返回 None
