"""DualTrackAnalyzer 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from common.exceptions import UnsupportedMarketError
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.models.report import CombinedSignal, ValueRating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def _make_value_result(mos: float = 0.25) -> ValueAnalysisResult:
    return ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype="value_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
        margin_of_safety=mos,
        price_percentile=0.3,
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
) -> DualTrackAnalyzer:
    value_analyzer = MagicMock()
    tech_analyzer = MagicMock()

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
        value_result=_make_value_result(0.25),
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
