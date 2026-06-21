"""技术面分析配置参数。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IndicatorParams:
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60])

    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    rsi_short: int = 6
    rsi_mid: int = 12
    rsi_long: int = 24
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    kdj_period: int = 9
    kdj_smooth_k: int = 3
    kdj_smooth_d: int = 3
    kdj_overbought: float = 80.0
    kdj_oversold: float = 20.0

    volume_shrink_ratio: float = 0.7
    volume_heavy_ratio: float = 1.5
    ma_support_tolerance: float = 0.02


@dataclass
class ScoringParams:
    trend_weight: int = 30
    bias_weight: int = 20
    volume_weight: int = 15
    support_weight: int = 10
    macd_weight: int = 15
    rsi_weight: int = 6
    kdj_weight: int = 4

    bias_threshold: float = 5.0
    strong_trend_bias_multiplier: float = 1.5

    strong_buy_threshold: int = 75
    buy_threshold: int = 60
    hold_threshold: int = 45
    wait_threshold: int = 30


@dataclass
class TechAnalysisConfig:
    indicator_params: IndicatorParams = field(default_factory=IndicatorParams)
    scoring_params: ScoringParams = field(default_factory=ScoringParams)
    kline_days: int = 90
