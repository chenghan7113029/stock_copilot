"""Formatter 单元测试。"""

from __future__ import annotations

import json
from datetime import datetime

from apps.formatters import format_tech_report, format_value_report
from service.tech.models.tech_result import (
    BuySignal,
    TechAnalysisResult,
    TrendStatus,
)
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange


def test_format_tech_report_text():
    result = TechAnalysisResult(
        code="600519",
        buy_signal=BuySignal.HOLD,
        signal_score=65,
        trend_status=TrendStatus.BULL,
        ma_alignment="多头排列",
        kline_last_date="2025-06-28",
        quote_mode="eod",
    )
    text = format_tech_report(result, as_json=False)
    assert "=== 技术面分析报告 600519 ===" in text
    assert "综合评分" in text
    assert "周线" not in text or "K线末行: 2025-06-28" in text


def test_format_tech_report_json():
    result = TechAnalysisResult(code="600519", signal_score=65)
    payload = json.loads(format_tech_report(result, as_json=True))
    assert payload["code"] == "600519"
    assert payload["signal_score"] == 65


def test_format_tech_report_none_score_safe():
    result = TechAnalysisResult(code="600519", signal_score=0)
    text = format_tech_report(result, as_json=False)
    assert "N/A" not in text or "综合评分: 0" in text


def test_format_value_report_text():
    result = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1800.0,
        prototype="quality_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=1600, base=1800, high=2000),
        margin_of_safety=10.0,
        price_percentile=50.0,
        assessment="合理",
        confidence="Medium",
        data_timestamp=datetime(2025, 6, 28, 9, 15),
    )
    text = format_value_report(result, as_json=False)
    assert "=== 价值面分析报告 600519 ===" in text
    assert "估值" in text
    assert "安全边际" in text


def test_format_value_report_json():
    result = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1800.0,
        prototype="quality_growth",
        method_keys_used=[],
        fair_value_range=None,
        margin_of_safety=None,
        price_percentile=None,
        assessment="合理",
        confidence="Medium",
    )
    payload = json.loads(format_value_report(result, as_json=True))
    assert payload["code"] == "600519"
    assert payload["assessment"] == "合理"
