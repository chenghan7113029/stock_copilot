"""comprehensive_narrator 单元测试（mock narrate）。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from common.llm.models import NarrateResult
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.report.comprehensive_narrator import (
    COMPREHENSIVE_REPORT_INSTRUCTION,
    COMPREHENSIVE_REPORT_SCHEMA,
    narrate_comprehensive_report,
)
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def _report() -> DualTrackReport:
    return DualTrackReport(
        code="600519",
        value_result=ValueAnalysisResult(
            code="600519",
            name="贵州茅台",
            current_price=1500.0,
            prototype="value_growth",
            method_keys_used=[],
            fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
            margin_of_safety=25.0,
            price_percentile=0.3,
            assessment="低估",
            confidence="High",
            data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
        ),
        tech_result=TechAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            signal_score=70,
            buy_signal=BuySignal.BUY,
            signal_reasons=["多头排列"],
            risk_factors=[],
        ),
        combined_signal=CombinedSignal.BUY,
        value_rating=ValueRating.UNDERVALUED,
    )


@patch("service.report.comprehensive_narrator.narrate")
def test_narrate_success(mock_narrate):
    mock_narrate.return_value = NarrateResult(
        ok=True,
        data={
            "summary": "低估且技术面偏多",
            "key_points": ["安全边际充足"],
            "risks": ["注意回调"],
            "confidence": 0.9,
        },
        confidence=0.9,
        grounded=True,
    )
    result = narrate_comprehensive_report(_report(), config={})
    assert result.ok is True
    assert result.data is not None
    assert "summary" in result.data
    call_kwargs = mock_narrate.call_args
    evidence = call_kwargs.args[0]
    schema = call_kwargs.args[1]
    instruction = call_kwargs.args[2]
    assert "value" in evidence
    assert schema == COMPREHENSIVE_REPORT_SCHEMA
    assert "不得引入" in instruction or "不得引入" in COMPREHENSIVE_REPORT_INSTRUCTION
    assert instruction == COMPREHENSIVE_REPORT_INSTRUCTION


@patch("service.report.comprehensive_narrator.narrate")
def test_llm_not_configured(mock_narrate):
    mock_narrate.return_value = NarrateResult(ok=False, error="LLM 未配置")
    result = narrate_comprehensive_report(_report())
    assert result.ok is False
    assert "LLM 未配置" in (result.error or "")


@patch("service.report.comprehensive_narrator.narrate")
def test_grounded_failure(mock_narrate):
    mock_narrate.return_value = NarrateResult(
        ok=False,
        grounded=False,
        error="grounded 校验失败: 输出含 evidence 之外的数值",
    )
    result = narrate_comprehensive_report(_report())
    assert result.ok is False
    assert result.grounded is False
