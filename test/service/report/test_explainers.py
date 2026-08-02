# -*- coding: utf-8 -*-
"""report explainers unit tests."""

from __future__ import annotations

from service.report.explainers import (
    assessment_to_zh,
    format_mos_percent_points,
    render_tech_explanations,
    render_value_method_card,
    render_value_trap_explainer,
)
from service.tech.models.tech_result import TechAnalysisResult
from service.value.valuation.base import ValuationResult


def test_format_mos_percent_points_no_double_scale():
    assert format_mos_percent_points(-0.8) == "-0.8%"
    assert format_mos_percent_points(7.14) == "7.1%"
    assert "-80" not in format_mos_percent_points(-0.8)
    assert format_mos_percent_points(None) == "N/A"


def test_assessment_to_zh():
    assert assessment_to_zh("Undervalued") == "\u4f4e\u4f30"  # ??
    assert assessment_to_zh("Overvalued") == "\u9ad8\u4f30"  # ??
    assert "\u4ef7\u503c\u9677\u9631" in assessment_to_zh("Medium Value Trap Risk")


def test_render_tech_explanations_includes_rsi():
    text = "\n".join(render_tech_explanations(TechAnalysisResult(code="600519")))
    assert "RSI" in text
    assert "MACD" in text
    assert "\u6307\u6807\u8bf4\u660e" in text


def test_render_value_method_card_uses_details_without_inventing():
    mr = ValuationResult(
        method="DDM",
        fair_value=10.0,
        current_price=5.0,
        premium_discount=100.0,
        assessment="Undervalued",
        details={
            "formula": "P = D / (r - g)",
            "dividend": 0.5,
            "required_return": 8.0,
            "growth_rate": 3.0,
        },
        applicability="Applicable",
    )
    card = "\n".join(render_value_method_card("ddm", mr))
    assert "P = D / (r - g)" in card
    assert "\u80a1\u606f" in card
    assert "0.5" in card
    assert ("\u4ef7\u503c\u5feb\u7167" in card) or ("\u8d22\u62a5" in card)
    assert "\u4f4e\u4f30" in card  # ??


def test_render_value_method_card_missing_formula():
    mr = ValuationResult(
        method="X",
        fair_value=1.0,
        current_price=1.0,
        premium_discount=0.0,
        assessment="Fair",
        details={},
        applicability="Applicable",
    )
    card = "\n".join(render_value_method_card("unknown_method", mr))
    assert "details" in card


def test_render_value_trap_explainer_dimensions():
    details = {
        "overall_risk": "Medium",
        "financial_health": "Low",
        "financial_health_note": "ok",
        "business_deterioration": "Medium",
        "business_deterioration_note": "margin down",
        "moat_erosion": "Low",
        "moat_erosion_note": "stable",
        "ai_vulnerability": "Medium",
        "ai_vulnerability_note": "manual",
        "dividend_sustainability": "Low",
        "dividend_sustainability_note": "ok",
    }
    text = "\n".join(render_value_trap_explainer(details))
    assert "\u4ef7\u503c\u9677\u9631" in text
    assert "\u8d22\u52a1\u5065\u5eb7" in text
    assert "\u4e1a\u52a1\u6076\u5316" in text
    assert "\u4e2d\u7b49" in text
