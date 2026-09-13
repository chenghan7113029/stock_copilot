# tech-bollinger-bands Specification

## Purpose
TBD - created by archiving change add-bollinger-bands. Update Purpose after archive.
## Requirements
### Requirement: BollingerStatus 状态判断
`BollingerStatus`（5 级枚举：`SQUEEZE`「收窄」/ `EXPANSION`「扩张」/ `UPPER_BREAKOUT`「上轨突破」/ `LOWER_BREAKOUT`「下轨突破」/ `NORMAL`「正常」）SHALL 按以下优先级判断：收盘价 > 上轨 → `UPPER_BREAKOUT`；收盘价 < 下轨 → `LOWER_BREAKOUT`；否则若带宽百分位 `boll_percentile <= boll_squeeze_percentile`（默认 20）→ `SQUEEZE`；若 `boll_percentile >= boll_expansion_percentile`（默认 80）→ `EXPANSION`；其余 → `NORMAL`。

#### Scenario: 上轨突破优先于收缩判断
- **WHEN** 收盘价高于布林带上轨，且同时带宽百分位 <= `boll_squeeze_percentile`
- **THEN** `boll_status = BollingerStatus.UPPER_BREAKOUT`（突破优先级高于收缩）

#### Scenario: 波动率收缩
- **WHEN** 收盘价在上下轨之间，且带宽百分位 <= `boll_squeeze_percentile`
- **THEN** `boll_status = BollingerStatus.SQUEEZE`

#### Scenario: 波动率扩张
- **WHEN** 收盘价在上下轨之间，且带宽百分位 >= `boll_expansion_percentile`
- **THEN** `boll_status = BollingerStatus.EXPANSION`

#### Scenario: 正常状态
- **WHEN** 收盘价在上下轨之间，且带宽百分位介于 `boll_squeeze_percentile` 与 `boll_expansion_percentile` 之间
- **THEN** `boll_status = BollingerStatus.NORMAL`

---

### Requirement: 布林带单状态文案不参与打分
`TechAnalyzer.analyze()` 依据 `boll_status` 追加的文案 SHALL 直接写入 `TechAnalysisResult.signal_reasons`/`risk_factors`，**不经过** `ScoringEngine.score()`；`signal_score`/`buy_signal` 的计算 SHALL 与是否存在布林带文案无关。

#### Scenario: 上轨突破追加提示但不改变评分
- **WHEN** `boll_status = UPPER_BREAKOUT`
- **THEN** `signal_reasons` 或 `risk_factors` 包含布林带突破相关文案，但 `signal_score` 与"关闭布林带文案追加逻辑"时的计算结果完全一致

#### Scenario: 收窄状态追加提示
- **WHEN** `boll_status = SQUEEZE`
- **THEN** `signal_reasons` 包含"布林带收窄，波动率处于近期低位"类描述

