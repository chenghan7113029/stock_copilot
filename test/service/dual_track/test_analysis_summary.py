"""build_analysis_summary 应包含股票名称（若有）。"""

from __future__ import annotations

from datetime import datetime, timezone

from service.dual_track.analyzer import build_analysis_summary
from service.dual_track.models.report import ValueRating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult


def test_build_analysis_summary_includes_name():
    value = ValueAnalysisResult(
        code="002027",
        name="分众传媒",
        current_price=5.62,
        prototype="high_dividend",
        method_keys_used=[],
        fair_value_range=None,
        margin_of_safety=None,
        price_percentile=None,
        assessment="合理",
        confidence="Medium",
        data_timestamp=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    tech = TechAnalysisResult(
        code="002027",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=62,
        buy_signal=BuySignal.BUY,
    )
    text = build_analysis_summary(
        "002027", value, tech, "观望", ValueRating.OVERVALUED
    )
    assert "股票代码: 002027" in text
    assert "名称: 分众传媒" in text


def test_build_analysis_summary_without_name():
    text = build_analysis_summary("600519", None, None, "观望", None)
    assert text.startswith("股票代码: 600519")
    assert "名称:" not in text
