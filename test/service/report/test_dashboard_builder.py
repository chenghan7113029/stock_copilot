"""DashboardBuilder 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from service.dual_track.evidence_bucketer import EvidenceBuckets
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.report.dashboard_builder import DashboardBuilder, LocalDataMissingError
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
        margin_of_safety=0.25,
        price_percentile=0.3,
        assessment="低估",
        confidence="High",
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _tech(*, no_cache: bool = False) -> TechAnalysisResult:
    if no_cache:
        return TechAnalysisResult(
            code="600519",
            warnings=["无缓存数据"],
            risk_factors=["无缓存数据，请先运行 sync"],
        )
    return TechAnalysisResult(
        code="600519",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=80,
        buy_signal=BuySignal.STRONG_BUY,
        current_price=1500.0,
        signal_reasons=["MA5 上穿 MA20"],
        risk_factors=[],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _report(
    value=None,
    tech=None,
    *,
    value_rating: ValueRating | None = ValueRating.UNDERVALUED,
) -> DualTrackReport:
    return DualTrackReport(
        code="600519",
        value_result=value,
        tech_result=tech,
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=value_rating,
        analysis_summary="股票代码: 600519 | 综合信号: 强烈买入",
        warnings=[],
    )


def _builder(report: DualTrackReport, *, bull: int = 5, bear: int = 3) -> DashboardBuilder:
    dual = MagicMock()
    dual.analyze_offline.return_value = report
    bucketer = MagicMock()
    bucketer.bucket.return_value = EvidenceBuckets(
        bull_evidence=[f"b{i}" for i in range(bull)],
        bear_evidence=[f"e{i}" for i in range(bear)],
    )
    return DashboardBuilder(
        MagicMock(),
        MagicMock(),
        dual_analyzer=dual,
        bucketer=bucketer,
    )


def test_build_both_present():
    view = _builder(_report(_value(), _tech())).build("600519")
    assert view.code == "600519"
    assert "低估" in view.value_section
    assert "强烈买入" in view.tech_section or "强势多头" in view.tech_section
    assert "多方 5 条" in view.combined_summary
    assert "空方 3 条" in view.combined_summary
    assert "PO-06" in view.sentiment_section
    assert "待建" in view.sentiment_section
    assert "PO-04" in view.checklist_section
    assert "待建" in view.checklist_section


def test_build_value_missing_tech_ok():
    view = _builder(
        _report(None, _tech(), value_rating=None), bull=2, bear=2
    ).build("600519")
    assert "无本地快照" in view.value_section
    assert "强势多头" in view.tech_section
    assert "PO-06" in view.sentiment_section


def test_build_tech_missing_value_ok():
    view = _builder(_report(_value(), _tech(no_cache=True))).build("600519")
    assert "低估" in view.value_section
    assert "无本地快照" in view.tech_section


def test_build_both_missing_raises():
    builder = _builder(_report(None, _tech(no_cache=True), value_rating=None))
    with pytest.raises(LocalDataMissingError) as exc:
        builder.build("600519")
    assert "未找到 600519 的本地数据" in str(exc.value)
