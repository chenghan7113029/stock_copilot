"""TechAnalyzer 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from service.tech.analyzer import TechAnalyzer
from service.tech.config import ScoringParams, TechAnalysisConfig
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus, WeeklyTrendStatus
from service.tech.scorer import BullTrendScorer


def _sample_kline(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = [10.0]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1 + rng.normal(0.003, 0.01)))
    closes_arr = np.array(closes)
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": closes_arr,
            "high": closes_arr * 1.01,
            "low": closes_arr * 0.99,
            "close": closes_arr,
            "volume": rng.integers(1_000_000, 5_000_000, size=n).astype(float),
        }
    )


def test_analyze_returns_complete_result():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519")

    assert isinstance(result, TechAnalysisResult)
    assert result.code == "600519"
    assert result.current_price > 0
    assert result.signal_score >= 0
    assert result.buy_signal is not None
    assert result.trend_status is not None


def test_non_a_share_rejected():
    provider = MagicMock()
    analyzer = TechAnalyzer(kline_provider=provider)

    with pytest.raises(UnsupportedMarketError):
        analyzer.analyze("AAPL")


def test_kline_failure_degrades():
    provider = MagicMock()
    provider.get_kline.side_effect = KlineUnavailableError("all sources failed")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519")

    assert result.buy_signal == BuySignal.WAIT
    assert any("K 线" in r for r in result.risk_factors)


def test_strong_bull_low_score_manual_review_hint():
    from service.tech.calculator import TechIndicators
    from service.tech.models.tech_result import MACDStatus, RSIStatus, VolumeStatus

    indicators = TechIndicators(
        code="600519",
        df=pd.DataFrame(),
        trend_status=TrendStatus.STRONG_BULL,
        trend_strength=90,
        bias_ma5=12.0,
        volume_status=VolumeStatus.HEAVY_VOLUME_DOWN,
        macd_status=MACDStatus.DEATH_CROSS,
        rsi_status=RSIStatus.OVERBOUGHT,
    )
    scorer = BullTrendScorer()
    signal = scorer.score(indicators, ScoringParams())

    assert signal.signal_score < 45
    assert any("人工复核" in r for r in signal.risk_factors)


def test_bear_trend_forces_strong_sell():
    from service.tech.calculator import TechIndicators

    indicators = TechIndicators(
        code="600519",
        df=pd.DataFrame(),
        trend_status=TrendStatus.STRONG_BEAR,
        trend_strength=10,
    )
    scorer = BullTrendScorer()
    signal = scorer.score(indicators, ScoringParams())

    assert signal.buy_signal == BuySignal.STRONG_SELL


def test_from_config_factory():
    analyzer = TechAnalyzer.from_config({"db": {"url": "sqlite:///:memory:"}})
    assert isinstance(analyzer, TechAnalyzer)


def test_custom_scoring_params():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    config = TechAnalysisConfig(scoring_params=ScoringParams(bias_threshold=3.0))
    analyzer = TechAnalyzer(kline_provider=provider, config=config)

    result = analyzer.analyze("600519")
    assert result.code == "600519"


def test_weekly_trend_included_in_result():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(60), [], "eod")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519")

    assert result.weekly_trend_status is not None
    assert result.weekly_ma_alignment != ""
    assert result.weekly_ma5 is not None and result.weekly_ma5 > 0


def test_weekly_bear_downgrades_buy_signal():
    from service.tech.calculator import TechIndicators, WeeklyIndicators
    from service.tech.models.tech_result import KDJStatus, MACDStatus, RSIStatus, VolumeStatus

    indicators = TechIndicators(
        code="600519",
        df=pd.DataFrame(),
        trend_status=TrendStatus.STRONG_BULL,
        trend_strength=90,
        bias_ma5=0.5,
        volume_status=VolumeStatus.SHRINK_VOLUME_DOWN,
        support_ma5=True,
        support_ma10=True,
        macd_status=MACDStatus.GOLDEN_CROSS_ZERO,
        rsi_status=RSIStatus.STRONG_BUY,
        kdj_status=KDJStatus.GOLDEN_CROSS,
    )
    weekly = WeeklyIndicators(weekly_trend_status=WeeklyTrendStatus.BEAR)
    scorer = BullTrendScorer()

    without_filter = scorer.score(indicators, ScoringParams(weekly_filter_enabled=False), weekly)
    with_filter = scorer.score(indicators, ScoringParams(), weekly)

    assert without_filter.buy_signal == BuySignal.STRONG_BUY
    assert with_filter.buy_signal == BuySignal.BUY
    assert any("周线空头" in r for r in with_filter.risk_factors)


def test_weekly_filter_disabled():
    from service.tech.calculator import TechIndicators, WeeklyIndicators
    from service.tech.models.tech_result import KDJStatus, MACDStatus, RSIStatus, VolumeStatus

    indicators = TechIndicators(
        code="600519",
        df=pd.DataFrame(),
        trend_status=TrendStatus.STRONG_BULL,
        trend_strength=90,
        bias_ma5=0.5,
        volume_status=VolumeStatus.SHRINK_VOLUME_DOWN,
        support_ma5=True,
        support_ma10=True,
        macd_status=MACDStatus.GOLDEN_CROSS_ZERO,
        rsi_status=RSIStatus.STRONG_BUY,
        kdj_status=KDJStatus.GOLDEN_CROSS,
    )
    weekly = WeeklyIndicators(weekly_trend_status=WeeklyTrendStatus.STRONG_BEAR)
    scorer = BullTrendScorer()
    params = ScoringParams(weekly_filter_enabled=False)

    signal = scorer.score(indicators, params, weekly)

    assert signal.buy_signal == BuySignal.STRONG_BUY
    assert not any("周线空头" in r for r in signal.risk_factors)


def test_analyze_default_quote_mode_eod():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519")

    assert result.quote_mode == "eod"
    provider.get_kline.assert_called_once_with("600519", days=90, use_realtime=False, offline=False)


def test_analyze_use_realtime_sets_quote_mode():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "realtime")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519", use_realtime=True)

    assert result.quote_mode == "realtime"
    provider.get_kline.assert_called_once_with("600519", days=90, use_realtime=True, offline=False)


def test_analyze_realtime_fallback_quote_mode():
    provider = MagicMock()
    provider.get_kline.return_value = (
        _sample_kline(),
        ["实时报价获取失败，已降级为 EOD: network down"],
        "eod_fallback",
    )
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519", use_realtime=True)

    assert result.quote_mode == "eod_fallback"
    assert any("实时报价" in w for w in result.warnings)
