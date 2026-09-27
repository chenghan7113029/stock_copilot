"""DualTrackAnalyzer 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from common.exceptions import UnsupportedMarketError
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.models.report import CombinedSignal, ValueRating
from service.fundflow.models.fund_flow_result import FundFlowResult, LeverageDirection
from service.sentiment.models.sentiment_result import SentimentAnalysisResult, SentimentStatus
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def _make_value_result(mos: float = 25.0) -> ValueAnalysisResult:
    return ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype="value_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
        margin_of_safety=mos,
        price_percentile=30.0,
        assessment="低估",
        confidence="High",
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _make_tech_result(buy_signal: BuySignal = BuySignal.STRONG_BUY) -> TechAnalysisResult:
    return TechAnalysisResult(
        code="600519",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=80,
        buy_signal=buy_signal,
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _make_analyzer(
    value_result=None,
    tech_result=None,
    value_exc=None,
    tech_exc=None,
    *,
    offline: bool = False,
) -> DualTrackAnalyzer:
    value_analyzer = MagicMock()
    tech_analyzer = MagicMock()

    if offline:
        if value_exc:
            value_analyzer.analyze_offline.side_effect = value_exc
        else:
            value_analyzer.analyze_offline.return_value = value_result
        if tech_exc:
            tech_analyzer.analyze.side_effect = tech_exc
        else:
            tech_analyzer.analyze.return_value = tech_result
    else:
        if value_exc:
            value_analyzer.analyze.side_effect = value_exc
        else:
            value_analyzer.analyze.return_value = value_result
        if tech_exc:
            tech_analyzer.analyze.side_effect = tech_exc
        else:
            tech_analyzer.analyze.return_value = tech_result

    return DualTrackAnalyzer(value_analyzer, tech_analyzer)


def test_analyze_full_dual_track():
    analyzer = _make_analyzer(_make_value_result(), _make_tech_result())
    report = analyzer.analyze("600519")

    assert report.code == "600519"
    assert report.value_result is not None
    assert report.tech_result is not None
    assert report.combined_signal == CombinedSignal.STRONG_BUY
    assert report.value_rating == ValueRating.UNDERVALUED
    assert report.analysis_summary
    assert "600519" in report.analysis_summary
    assert "公允价区间" in report.analysis_summary
    assert "强势多头" in report.analysis_summary
    assert "强烈买入" in report.analysis_summary
    assert report.data_timestamp is not None


def test_analyze_value_failure_degrades():
    analyzer = _make_analyzer(
        value_exc=RuntimeError("value fetch failed"),
        tech_result=_make_tech_result(BuySignal.BUY),
    )
    report = analyzer.analyze("600519")

    assert report.value_result is None
    assert report.tech_result is not None
    assert report.combined_signal == CombinedSignal.BUY
    assert any("价值面分析失败" in w for w in report.warnings)


def test_analyze_tech_failure_degrades():
    analyzer = _make_analyzer(
        value_result=_make_value_result(25.0),
        tech_exc=RuntimeError("kline failed"),
    )
    report = analyzer.analyze("600519")

    assert report.value_result is not None
    assert report.tech_result is None
    assert report.combined_signal == CombinedSignal.BUY
    assert report.value_rating == ValueRating.UNDERVALUED
    assert any("技术面分析失败" in w for w in report.warnings)


def test_analyze_both_fail():
    analyzer = _make_analyzer(
        value_exc=RuntimeError("value failed"),
        tech_exc=RuntimeError("tech failed"),
    )
    report = analyzer.analyze("600519")

    assert report.value_result is None
    assert report.tech_result is None
    assert report.combined_signal == CombinedSignal.WAIT
    assert len(report.warnings) >= 2


def test_non_a_share_rejected():
    analyzer = _make_analyzer()
    with pytest.raises(UnsupportedMarketError):
        analyzer.analyze("AAPL")


def test_unsupported_market_from_value_propagates():
    analyzer = _make_analyzer(value_exc=UnsupportedMarketError("bad code"))
    with pytest.raises(UnsupportedMarketError):
        analyzer.analyze("600519")


@patch("service.dual_track.analyzer.ValueAnalyzer")
@patch("service.dual_track.analyzer.TechAnalyzer")
def test_from_config_factory(mock_tech_cls, mock_value_cls):
    mock_value_cls.from_config.return_value = MagicMock()
    mock_tech_cls.from_config.return_value = MagicMock()

    analyzer = DualTrackAnalyzer.from_config({"db_path": "data/stock_copilot.db"})

    mock_value_cls.from_config.assert_called_once()
    mock_tech_cls.from_config.assert_called_once()
    assert isinstance(analyzer, DualTrackAnalyzer)


def test_analyze_offline_success():
    analyzer = _make_analyzer(
        _make_value_result(), _make_tech_result(), offline=True
    )
    report = analyzer.analyze_offline("600519")

    assert report.code == "600519"
    assert report.value_result is not None
    assert report.tech_result is not None
    assert report.combined_signal == CombinedSignal.STRONG_BUY
    assert report.value_rating == ValueRating.UNDERVALUED
    analyzer._value_analyzer.analyze_offline.assert_called_once_with("600519")
    analyzer._tech_analyzer.analyze.assert_called_once_with(
        "600519", offline=True, as_of=None
    )
    analyzer._value_analyzer.analyze.assert_not_called()


def test_analyze_offline_no_value_snapshot():
    analyzer = _make_analyzer(
        value_result=None, tech_result=_make_tech_result(BuySignal.BUY), offline=True
    )
    report = analyzer.analyze_offline("600519")

    assert report.value_result is None
    assert report.tech_result is not None
    assert report.combined_signal == CombinedSignal.BUY
    assert any("价值面无本地快照" in w for w in report.warnings)


def test_analyze_offline_does_not_call_online_analyze():
    value_analyzer = MagicMock()
    tech_analyzer = MagicMock()
    value_analyzer.analyze_offline.return_value = _make_value_result()
    tech_analyzer.analyze.return_value = _make_tech_result()
    analyzer = DualTrackAnalyzer(value_analyzer, tech_analyzer)

    analyzer.analyze_offline("600519")

    value_analyzer.analyze.assert_not_called()
    tech_analyzer.analyze.assert_called_once_with("600519", offline=True, as_of=None)


def test_analyze_online_unchanged_still_calls_analyze():
    """回归：联网版 analyze() 仍走 ValueAnalyzer.analyze，不走 analyze_offline。"""
    analyzer = _make_analyzer(_make_value_result(), _make_tech_result())
    report = analyzer.analyze("600519")

    assert report.value_result is not None
    analyzer._value_analyzer.analyze.assert_called_once_with("600519")
    analyzer._value_analyzer.analyze_offline.assert_not_called()
    analyzer._tech_analyzer.analyze.assert_called_once_with("600519")


def test_analyze_offline_adds_sentiment_and_three_dimensional_interpretation():
    value = _make_value_result()
    tech = _make_tech_result()
    sentiment = SentimentAnalysisResult(
        code="600519",
        market_sentiment_status=SentimentStatus.EXTREME_FEAR,
        market_sentiment_score=10.0,
        limit_updown_ratio=0.1,
    )
    sentiment_analyzer = MagicMock()
    sentiment_analyzer.analyze_offline.return_value = sentiment

    analyzer = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value),
        MagicMock(),
        sentiment_analyzer=sentiment_analyzer,
    )
    analyzer._tech_analyzer.analyze.return_value = tech
    report = analyzer.analyze_offline("600519")

    assert report.sentiment_result is sentiment
    assert "极度恐慌" in report.analysis_summary
    assert "价值面显示低估" in report.analysis_summary
    assert report.combined_signal == CombinedSignal.STRONG_BUY


def test_analyze_offline_explains_missing_sentiment_without_affecting_fusion():
    value = _make_value_result()
    tech = _make_tech_result()
    sentiment_analyzer = MagicMock()
    sentiment_analyzer.analyze_offline.return_value = None
    analyzer = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value),
        MagicMock(),
        sentiment_analyzer=sentiment_analyzer,
    )
    analyzer._tech_analyzer.analyze.return_value = tech

    report = analyzer.analyze_offline("600519")

    assert report.sentiment_result is None
    assert "情绪面数据缺失，本次报告仅基于价值+技术双维" in report.analysis_summary
    assert report.combined_signal == CombinedSignal.STRONG_BUY


def _make_fund_flow_result() -> FundFlowResult:
    return FundFlowResult(
        code="600519",
        margin_balance_change_pct=10.0,
        short_balance_change_pct=1.0,
        main_net_inflow_5d=800.0,
        leverage_direction=LeverageDirection.ADD_LEVERAGE,
        reasons=["两融余额近 5 个交易日变化 +10.0%"],
    )


def test_analyze_offline_populates_fund_flow_result():
    value = _make_value_result()
    tech = _make_tech_result()
    fund_flow_analyzer = MagicMock()
    fund_flow_analyzer.analyze_offline.return_value = _make_fund_flow_result()
    analyzer = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value),
        MagicMock(),
        fund_flow_analyzer=fund_flow_analyzer,
    )
    analyzer._tech_analyzer.analyze.return_value = tech

    report = analyzer.analyze_offline("600519")

    assert report.fund_flow_result is not None
    assert report.fund_flow_result.main_net_inflow_5d == 800.0
    assert report.combined_signal == CombinedSignal.STRONG_BUY
    fund_flow_analyzer.analyze_offline.assert_called_once_with("600519")


def test_analyze_offline_missing_fund_flow_degrades_without_blocking():
    value = _make_value_result()
    tech = _make_tech_result()
    fund_flow_analyzer = MagicMock()
    fund_flow_analyzer.analyze_offline.return_value = None
    analyzer = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value),
        MagicMock(),
        fund_flow_analyzer=fund_flow_analyzer,
    )
    analyzer._tech_analyzer.analyze.return_value = tech

    report = analyzer.analyze_offline("600519")

    assert report.fund_flow_result is None
    assert any("资金面无本地缓存" in w for w in report.warnings)
    assert report.combined_signal == CombinedSignal.STRONG_BUY
    assert report.value_rating == ValueRating.UNDERVALUED


def test_analyze_offline_fund_flow_does_not_change_fusion_regression():
    value = _make_value_result()
    tech = _make_tech_result()

    without_fund_flow = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value), MagicMock()
    )
    without_fund_flow._tech_analyzer.analyze.return_value = tech
    baseline = without_fund_flow.analyze_offline("600519")

    fund_flow_analyzer = MagicMock()
    fund_flow_analyzer.analyze_offline.return_value = _make_fund_flow_result()
    with_fund_flow = DualTrackAnalyzer(
        MagicMock(analyze_offline=lambda _: value),
        MagicMock(),
        fund_flow_analyzer=fund_flow_analyzer,
    )
    with_fund_flow._tech_analyzer.analyze.return_value = tech
    report = with_fund_flow.analyze_offline("600519")

    assert report.fund_flow_result is not None
    assert report.combined_signal == baseline.combined_signal
    assert report.value_rating == baseline.value_rating
