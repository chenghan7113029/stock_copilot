"""技术面指标计算单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from service.tech.calculator import IndicatorCalculator, WeeklyKlineAggregator
from service.tech.config import IndicatorParams, ScoringParams
from service.tech.models.tech_result import (
    BollingerStatus,
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


def test_bollinger_mid_equals_ma20_and_bands_match_std():
    df = _make_uptrend_df(60)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519")

    assert indicators.boll_mid == pytest.approx(indicators.ma20, abs=1e-6)
    std20 = float(df["close"].rolling(20).std().iloc[-1])
    assert indicators.boll_upper - indicators.boll_mid == pytest.approx(2.0 * std20, abs=1e-6)
    assert indicators.boll_mid - indicators.boll_lower == pytest.approx(2.0 * std20, abs=1e-6)
    assert indicators.boll_percentile is not None
    assert 0.0 <= indicators.boll_percentile <= 100.0


def test_bollinger_custom_period_does_not_reuse_ma20():
    df = _make_uptrend_df(60)
    params = IndicatorParams(boll_period=10)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519", params)

    expected_mid = float(df["close"].rolling(10).mean().iloc[-1])
    assert indicators.boll_mid == pytest.approx(expected_mid, abs=1e-6)
    assert indicators.boll_mid != pytest.approx(indicators.ma20, abs=1e-6)


def test_bollinger_insufficient_period_degrades():
    df = _make_uptrend_df(25)
    params = IndicatorParams(boll_period=30)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519", params)

    assert indicators.boll_signal == "数据不足"
    assert any("布林带数据不足" in w for w in indicators.warnings)
    assert indicators.boll_percentile is None


def test_bollinger_bandwidth_lookback_short_warns():
    df = _make_uptrend_df(45)
    params = IndicatorParams(boll_period=20, boll_bandwidth_lookback=40)
    calc = IndicatorCalculator()
    indicators = calc.calculate(df, "600519", params)

    assert indicators.boll_percentile is not None
    assert any("布林带带宽历史样本不足" in w for w in indicators.warnings)


def test_bollinger_status_squeeze():
    """带宽百分位处于低位且价格在轨内 → SQUEEZE。"""
    from service.tech.calculator import TechIndicators

    calc = IndicatorCalculator()
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    # 构造带宽序列：早期高、近期低，末值最低
    bandwidths = np.linspace(0.2, 0.02, n)
    mids = np.full(n, 10.0)
    work = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": mids,
            "BOLL_MID": mids,
            "BOLL_UPPER": mids + 1.0,
            "BOLL_LOWER": mids - 1.0,
            "BOLL_BANDWIDTH": bandwidths,
        }
    )
    result = TechIndicators(code="600519", df=work, current_price=10.0)
    params = IndicatorParams(
        boll_period=20,
        boll_squeeze_percentile=20.0,
        boll_expansion_percentile=80.0,
        boll_bandwidth_lookback=40,
    )
    calc._analyze_bollinger(work, result, params)
    assert result.boll_status == BollingerStatus.SQUEEZE
    assert "收窄" in result.boll_signal


def test_bollinger_status_expansion():
    from service.tech.calculator import TechIndicators

    calc = IndicatorCalculator()
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    bandwidths = np.linspace(0.02, 0.2, n)  # 末值最高
    mids = np.full(n, 10.0)
    work = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": mids,
            "BOLL_MID": mids,
            "BOLL_UPPER": mids + 1.0,
            "BOLL_LOWER": mids - 1.0,
            "BOLL_BANDWIDTH": bandwidths,
        }
    )
    result = TechIndicators(code="600519", df=work, current_price=10.0)
    params = IndicatorParams(
        boll_period=20,
        boll_squeeze_percentile=20.0,
        boll_expansion_percentile=80.0,
        boll_bandwidth_lookback=40,
    )
    calc._analyze_bollinger(work, result, params)
    assert result.boll_status == BollingerStatus.EXPANSION
    assert "扩张" in result.boll_signal


def test_bollinger_status_upper_breakout_priority_over_squeeze():
    """收盘突破上轨时，即使带宽百分位很低也优先 UPPER_BREAKOUT。"""
    from service.tech.calculator import TechIndicators

    calc = IndicatorCalculator()
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    bandwidths = np.linspace(0.2, 0.02, n)  # 末值低 → 本会判收窄
    mids = np.full(n, 10.0)
    work = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": np.full(n, 12.0),
            "BOLL_MID": mids,
            "BOLL_UPPER": mids + 1.0,
            "BOLL_LOWER": mids - 1.0,
            "BOLL_BANDWIDTH": bandwidths,
        }
    )
    result = TechIndicators(code="600519", df=work, current_price=12.0)
    params = IndicatorParams(
        boll_period=20,
        boll_squeeze_percentile=100.0,
        boll_expansion_percentile=80.0,
        boll_bandwidth_lookback=40,
    )
    calc._analyze_bollinger(work, result, params)
    assert result.boll_status == BollingerStatus.UPPER_BREAKOUT
    assert "上轨" in result.boll_signal


def test_bollinger_status_lower_breakout():
    from service.tech.calculator import TechIndicators

    calc = IndicatorCalculator()
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    bandwidths = np.linspace(0.05, 0.1, n)
    mids = np.full(n, 10.0)
    work = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": np.full(n, 8.0),
            "BOLL_MID": mids,
            "BOLL_UPPER": mids + 1.0,
            "BOLL_LOWER": mids - 1.0,
            "BOLL_BANDWIDTH": bandwidths,
        }
    )
    result = TechIndicators(code="600519", df=work, current_price=8.0)
    calc._analyze_bollinger(work, result, IndicatorParams(boll_period=20))
    assert result.boll_status == BollingerStatus.LOWER_BREAKOUT


def test_bollinger_status_normal():
    from service.tech.calculator import TechIndicators

    calc = IndicatorCalculator()
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    # 末值居中百分位
    bandwidths = np.concatenate([np.linspace(0.02, 0.2, n - 1), [0.11]])
    mids = np.full(n, 10.0)
    work = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": mids,
            "BOLL_MID": mids,
            "BOLL_UPPER": mids + 1.0,
            "BOLL_LOWER": mids - 1.0,
            "BOLL_BANDWIDTH": bandwidths,
        }
    )
    result = TechIndicators(code="600519", df=work, current_price=10.0)
    params = IndicatorParams(
        boll_period=20,
        boll_squeeze_percentile=20.0,
        boll_expansion_percentile=80.0,
        boll_bandwidth_lookback=40,
    )
    calc._analyze_bollinger(work, result, params)
    assert result.boll_status == BollingerStatus.NORMAL

