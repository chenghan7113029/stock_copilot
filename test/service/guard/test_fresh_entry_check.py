"""FreshEntryCheck 单元测试。"""

from unittest.mock import MagicMock

import pytest

from service.dual_track.models.report import DualTrackReport
from service.guard.fresh_entry_check import FreshEntryCheck, LocalDataMissingError
from service.tech.models.tech_result import TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def _report() -> DualTrackReport:
    return DualTrackReport(
        code="600519",
        value_result=ValueAnalysisResult(
            code="600519",
            name="贵州茅台",
            current_price=1500.0,
            prototype="quality_growth",
            method_keys_used=[],
            fair_value_range=ValuationRange(low=1400.0, base=1600.0, high=1800.0),
            margin_of_safety=6.25,
            price_percentile=40.0,
            assessment="合理",
            confidence="High",
        ),
        tech_result=TechAnalysisResult(
            code="600519",
            current_price=1500.0,
            trend_status=TrendStatus.BULL,
            signal_score=72,
        ),
    )


def test_build_hides_position_cost_and_margin_when_position_exists():
    dual = MagicMock()
    dual.analyze_offline.return_value = _report()
    position_repo = MagicMock()
    position_repo.get_by_code.return_value = MagicMock(cost_price=1200.0, shares=100)

    view = FreshEntryCheck(dual, position_repo).build("600519")

    assert view.has_position is True
    assert "已隐藏" in view.reminder_text
    assert "1500.00" in view.framing_question
    assert "cost_price" not in repr(view)
    assert "安全边际" not in view.value_summary
    assert "6.25" not in repr(view)


def test_build_without_position_returns_standard_analysis_reminder():
    dual = MagicMock()
    dual.analyze_offline.return_value = _report()
    position_repo = MagicMock()
    position_repo.get_by_code.return_value = None

    view = FreshEntryCheck(dual, position_repo).build("600519")

    assert view.has_position is False
    assert view.reminder_text == "未检测到本地持仓记录，以下为标准三维分析"
    assert "价值面" in view.value_summary
    assert "技术面" in view.tech_summary


@pytest.mark.parametrize(
    "report",
    [
        DualTrackReport(code="600519"),
        DualTrackReport(
            code="600519",
            value_result=ValueAnalysisResult(
                code="600519",
                name="贵州茅台",
                current_price=1500.0,
                prototype="quality_growth",
                method_keys_used=[],
                fair_value_range=None,
                margin_of_safety=None,
                price_percentile=None,
                assessment="未知",
                confidence="Low",
            ),
        ),
    ],
)
def test_build_rejects_missing_local_value_or_kline_data(report):
    dual = MagicMock()
    dual.analyze_offline.return_value = report

    with pytest.raises(LocalDataMissingError, match="未找到 600519 的本地数据"):
        FreshEntryCheck(dual, MagicMock()).build("600519")
