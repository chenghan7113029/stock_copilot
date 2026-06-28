"""技术面指标计算单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from service.tech.calculator import IndicatorCalculator, WeeklyKlineAggregator
from service.tech.config import IndicatorParams, ScoringParams
from service.tech.models.tech_result import (
    KDJStatus,
    TrendStatus,
    VolumeStatus,
    WeeklyTrendStatus,
)
from service.tech.scorer import BullTrendScorer


def _make_uptrend_df(n: int = 60, seed: int = 42) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = [10.0 + i * 0.05 for i in range(n)]
    closes_arr = np.array(closes)
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": closes_arr,
            "high": closes_arr * 1.01,
            "low": closes_arr * 0.99,
            "close": closes_arr,
            "volume": np.full(n, 2_000_000.0),
        }
    )


def test_ma_values_match_rolling_mean():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    expected_ma5 = df["close"].rolling(5).mean().iloc[-1]
    assert indicators.ma5 == pytest.approx(expected_ma5, rel=1e-6)
    assert indicators.ma10 == pytest.approx(df["close"].rolling(10).mean().iloc[-1], rel=1e-6)
    assert indicators.ma20 == pytest.approx(df["close"].rolling(20).mean().iloc[-1], rel=1e-6)


def test_ma60_fallback_when_insufficient_data():
    df = _make_uptrend_df(30)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.ma60 == pytest.approx(indicators.ma20, rel=1e-6)
    assert any("MA60" in w for w in indicators.warnings)


def test_macd_computed():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.macd_dif != 0.0
    assert indicators.macd_dea != 0.0
    assert indicators.macd_bar != 0.0


def test_rsi_computed():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert 0 <= indicators.rsi_12 <= 100


def test_kdj_computed():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.kdj_k != 0.0
    assert indicators.kdj_d != 0.0


def test_kdj_j_extreme_overbought():
    df = _make_uptrend_df(60)
    df.loc[df.index[-1], "close"] = df["close"].max() * 1.5
    df.loc[df.index[-1], "high"] = df["close"].max() * 1.6
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    scorer = BullTrendScorer()
    signal = scorer.score(indicators, ScoringParams())
    if indicators.kdj_j > 100:
        assert indicators.kdj_status == KDJStatus.OVERBOUGHT
        assert any("J 值超界" in r for r in signal.risk_factors)


def test_shrink_volume_down():
    df = _make_uptrend_df(60)
    df.loc[df.index[-1], "volume"] = df["volume"].iloc[-6:-1].mean() * 0.5
    df.loc[df.index[-1], "close"] = df["close"].iloc[-2] * 0.99
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN


def test_heavy_volume_down():
    df = _make_uptrend_df(60)
    df.loc[df.index[-1], "volume"] = df["volume"].iloc[-6:-1].mean() * 2.0
    df.loc[df.index[-1], "close"] = df["close"].iloc[-2] * 0.97
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN


def test_support_ma5():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    work = calc._calculate_mas(df.copy(), IndicatorParams())
    ma5 = work["MA5"].iloc[-1]
    work.loc[work.index[-1], "close"] = ma5 * 1.005
    indicators = calc.calculate(work, "600519")

    assert indicators.support_ma5 is True


def test_bull_trend_detected():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.trend_status in (TrendStatus.BULL, TrendStatus.STRONG_BULL, TrendStatus.WEAK_BULL)


def test_weekly_aggregation_60_days():
    df = _make_uptrend_df(60)
    weekly = WeeklyKlineAggregator.aggregate(df)

    assert 10 <= len(weekly) <= 14
    assert weekly["open"].iloc[0] == pytest.approx(df["open"].iloc[0], rel=1e-6)
    assert weekly["close"].iloc[-1] == pytest.approx(df["close"].iloc[-1], rel=1e-6)
    assert weekly["high"].max() == pytest.approx(df["high"].max(), rel=1e-6)
    assert weekly["low"].min() == pytest.approx(df["low"].min(), rel=1e-6)
    assert weekly["volume"].sum() == pytest.approx(df["volume"].sum(), rel=1e-6)


def test_weekly_aggregation_insufficient_data():
    df = _make_uptrend_df(20)
    weekly = WeeklyKlineAggregator.aggregate(df)

    assert weekly.empty


def test_weekly_indicators_bull_trend():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    weekly = calc.calculate_weekly(df, IndicatorParams())

    assert weekly.weekly_trend_status in (
        WeeklyTrendStatus.BULL,
        WeeklyTrendStatus.STRONG_BULL,
    )
    assert weekly.weekly_ma5 > weekly.weekly_ma10 > weekly.weekly_ma20


def test_weekly_rsi_computed():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    weekly = calc.calculate_weekly(df, IndicatorParams())

    assert weekly.weekly_rsi_6 != 0.0
    assert not np.isnan(weekly.weekly_rsi_6)
