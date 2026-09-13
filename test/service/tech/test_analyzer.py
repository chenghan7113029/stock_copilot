"""TechAnalyzer 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from service.tech.analyzer import TechAnalyzer
from service.tech.config import ScoringParams, TechAnalysisConfig
from service.tech.models.tech_result import (
    BollingerStatus,
    BuySignal,
    ChipStatus,
    TechAnalysisResult,
    TrendStatus,
    WeeklyTrendStatus,
)
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
    provider.get_kline.assert_called_once_with(
        "600519", days=90, use_realtime=False, offline=False, as_of=None
    )


def test_analyze_use_realtime_sets_quote_mode():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "realtime")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519", use_realtime=True)

    assert result.quote_mode == "realtime"
    provider.get_kline.assert_called_once_with(
        "600519", days=90, use_realtime=True, offline=False, as_of=None
    )


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


def test_analyze_merges_chip_data_without_changing_score():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    chip_provider = MagicMock()
    chip_provider.get_latest.return_value = (
        {
            "winner_ratio": 35.0,
            "avg_cost": 12.34,
            "concentration_90": 8.2,
            "concentration_70": 4.1,
        },
        [],
    )

    with_chip = TechAnalyzer(kline_provider=provider, chip_provider=chip_provider).analyze("600519", offline=True)
    without_chip = TechAnalyzer(kline_provider=provider).analyze("600519", offline=True)

    assert with_chip.winner_ratio == 35.0
    assert with_chip.trap_ratio == 65.0
    assert with_chip.chip_status is ChipStatus.HIGHLY_CONCENTRATED
    assert with_chip.signal_score == without_chip.signal_score
    chip_provider.get_latest.assert_called_once_with("600519", offline=True)


def test_analyze_keeps_technical_result_when_chip_unavailable():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    chip_provider = MagicMock()
    chip_provider.get_latest.return_value = (None, ["筹码分布数据不可用: network down"])

    result = TechAnalyzer(kline_provider=provider, chip_provider=chip_provider).analyze("600519")

    assert result.winner_ratio is None
    assert result.chip_status is None
    assert result.signal_score >= 0
    assert any("筹码分布数据不可用" in warning for warning in result.warnings)


def _kline_with_bullish_engulfing(n: int = 60) -> pd.DataFrame:
    """构造末两日为看涨吞没的充足 K 线。"""
    df = _sample_kline(n)
    df.loc[df.index[-2], ["open", "high", "low", "close"]] = [10.5, 10.6, 9.9, 10.0]
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [9.9, 10.8, 9.8, 10.7]
    return df


def test_analyze_candlestick_patterns_do_not_affect_scoring(monkeypatch):
    from service.tech import analyzer as analyzer_mod
    from service.tech.models.tech_result import CandlestickPattern

    provider = MagicMock()
    provider.get_kline.return_value = (_kline_with_bullish_engulfing(), [], "eod")
    analyzer = TechAnalyzer(kline_provider=provider)

    with_patterns = analyzer.analyze("600519")
    assert with_patterns.candlestick_patterns
    assert any(
        s.pattern == CandlestickPattern.BULLISH_ENGULFING
        for s in with_patterns.candlestick_patterns
    )

    monkeypatch.setattr(
        analyzer_mod.PatternRecognizer,
        "recognize",
        staticmethod(lambda *args, **kwargs: []),
    )
    without_patterns = analyzer.analyze("600519")

    assert without_patterns.candlestick_patterns == []
    assert with_patterns.signal_score == without_patterns.signal_score
    assert with_patterns.buy_signal == without_patterns.buy_signal
    assert with_patterns.signal_reasons == without_patterns.signal_reasons
    assert with_patterns.risk_factors == without_patterns.risk_factors


def test_analyze_candlestick_patterns_empty_when_no_match():
    provider = MagicMock()
    # 大实体阳线，无十字星/锤头/吞没
    df = _sample_kline(60)
    df.loc[df.index[-2], ["open", "high", "low", "close"]] = [10.0, 10.2, 9.9, 10.1]
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [10.0, 10.5, 9.95, 10.45]
    provider.get_kline.return_value = (df, [], "eod")
    analyzer = TechAnalyzer(kline_provider=provider)

    result = analyzer.analyze("600519")

    assert result.candlestick_patterns == []


class _BollStatusCalculator:
    """包装真实计算器，仅覆盖 boll_status/boll_signal 供文案回归。"""

    def __init__(self, status: BollingerStatus, signal: str) -> None:
        from service.tech.calculator import IndicatorCalculator

        self._inner = IndicatorCalculator()
        self._status = status
        self._signal = signal

    def calculate(self, *args, **kwargs):
        indicators = self._inner.calculate(*args, **kwargs)
        indicators.boll_status = self._status
        indicators.boll_signal = self._signal
        return indicators

    def calculate_weekly(self, *args, **kwargs):
        return self._inner.calculate_weekly(*args, **kwargs)


@pytest.mark.parametrize(
    ("status", "signal", "in_reasons", "in_risks"),
    [
        (BollingerStatus.SQUEEZE, "布林带收窄，波动率处于近期低位", True, False),
        (BollingerStatus.EXPANSION, "布林带扩张，波动率处于近期高位", True, False),
        (BollingerStatus.UPPER_BREAKOUT, "收盘价突破布林带上轨", True, False),
        (BollingerStatus.LOWER_BREAKOUT, "收盘价跌破布林带下轨", False, True),
    ],
)
def test_analyze_appends_bollinger_notes_by_status(status, signal, in_reasons, in_risks):
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")
    analyzer = TechAnalyzer(
        kline_provider=provider,
        calculator=_BollStatusCalculator(status, signal),
    )
    result = analyzer.analyze("600519")

    if in_reasons:
        assert any(signal in r for r in result.signal_reasons)
    else:
        assert all(signal not in r for r in result.signal_reasons)
    if in_risks:
        assert any(signal in r for r in result.risk_factors)
    else:
        assert all(signal not in r for r in result.risk_factors)


def test_analyze_bollinger_notes_do_not_change_score():
    provider = MagicMock()
    provider.get_kline.return_value = (_sample_kline(), [], "eod")

    squeeze = TechAnalyzer(
        kline_provider=provider,
        calculator=_BollStatusCalculator(
            BollingerStatus.SQUEEZE, "布林带收窄，波动率处于近期低位"
        ),
    ).analyze("600519")
    normal = TechAnalyzer(
        kline_provider=provider,
        calculator=_BollStatusCalculator(BollingerStatus.NORMAL, "布林带正常"),
    ).analyze("600519")

    assert squeeze.signal_score == normal.signal_score
    assert squeeze.buy_signal == normal.buy_signal
    assert any("布林带收窄" in r for r in squeeze.signal_reasons)
    assert all("布林带收窄" not in r for r in normal.signal_reasons)
