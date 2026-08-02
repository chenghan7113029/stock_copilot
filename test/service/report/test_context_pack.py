"""build_dual_track_evidence 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.report.context_pack import build_dual_track_evidence
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def _value() -> ValueAnalysisResult:
    return ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype="value_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
        margin_of_safety=25.0,
        price_percentile=0.3,
        assessment="低估",
        confidence="High",
        warnings=["数据质量警告不应进入 evidence"],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _tech() -> TechAnalysisResult:
    return TechAnalysisResult(
        code="600519",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=80,
        buy_signal=BuySignal.STRONG_BUY,
        signal_reasons=["MA5 上穿 MA20"],
        risk_factors=["RSI 偏高"],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def test_both_dimensions_present():
    report = DualTrackReport(
        code="600519",
        value_result=_value(),
        tech_result=_tech(),
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=ValueRating.UNDERVALUED,
    )
    evidence = build_dual_track_evidence(report)
    assert "value" in evidence
    assert "tech" in evidence
    assert evidence["value"]["fair_value_range"]["base"] == 2000
    assert evidence["value"]["assessment"] == "低估"
    assert evidence["tech"]["signal_score"] == 80
    assert evidence["fusion"]["combined_signal"] == CombinedSignal.STRONG_BUY.value
    assert "warnings" not in evidence
    assert "warnings" not in evidence.get("value", {})


def test_value_missing_skips_value_block():
    report = DualTrackReport(
        code="600519",
        value_result=None,
        tech_result=_tech(),
        combined_signal=CombinedSignal.BUY,
        value_rating=None,
    )
    evidence = build_dual_track_evidence(report)
    assert "value" not in evidence
    assert "tech" in evidence
    assert evidence["fusion"]["value_rating"] is None


def test_enums_serialized_to_value():
    report = DualTrackReport(
        code="600519",
        value_result=_value(),
        tech_result=_tech(),
        combined_signal=CombinedSignal.HOLD,
        value_rating=ValueRating.FAIR,
    )
    evidence = build_dual_track_evidence(report)
    assert evidence["tech"]["trend_status"] == TrendStatus.STRONG_BULL.value
    assert evidence["tech"]["buy_signal"] == BuySignal.STRONG_BUY.value
    assert evidence["fusion"]["combined_signal"] == "持有"
    assert evidence["fusion"]["value_rating"] == "合理"
    assert isinstance(evidence["tech"]["trend_status"], str)
