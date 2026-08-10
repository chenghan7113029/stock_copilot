"""Formatter 单元测试。"""

from __future__ import annotations

import json
from datetime import datetime

from apps.formatters import format_dual_report, format_tech_report, format_value_report
from service.tech.models.tech_result import (
    BuySignal,
    ChipStatus,
    TechAnalysisResult,
    TrendStatus,
)
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange, ValuationResult


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
    assert "# 技术面分析报告 600519" in text
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
    assert "综合评分:** 0" in text or "综合评分: 0" in text


def test_format_tech_report_renders_chip_section_only_when_available():
    result = TechAnalysisResult(
        code="600519",
        winner_ratio=42.5,
        trap_ratio=57.5,
        avg_cost=12.34,
        concentration_90=8.2,
        concentration_70=4.1,
        chip_status=ChipStatus.HIGHLY_CONCENTRATED,
    )

    text = format_tech_report(result)
    payload = json.loads(format_tech_report(result, as_json=True))

    assert "## 筹码分布" in text
    assert "获利比例 42.5%" in text
    assert payload["chip_status"] == "高度控盘"
    assert "## 筹码分布" not in format_tech_report(TechAnalysisResult(code="600519"))


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
    assert "# 价值面分析报告 600519" in text
    assert "估值" in text
    assert "安全边际" in text
    assert "当前价格处于历史估值区间中性（分位 50%）" in text
    assert "价格分位:" not in text


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


def test_format_value_report_hides_anchor_price_unless_explicitly_requested():
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

    hidden = format_value_report(result, anchor_high=(2000.0, 250))
    shown = format_value_report(result, show_anchor_price=True, anchor_high=(2000.0, 250))

    assert "历史最高价" not in hidden
    assert "历史最高价: 2000.00（基于本地缓存 250 条交易日数据）" in shown
    assert "仅供参考，不建议作为决策心理锚点" in shown


def test_format_value_report_value_trap_alert_text_and_json():
    alert = "🚨 疑似价值陷阱（High Risk）：财务健康。"
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
        warnings=["Value Trap Detector: risk=High"],
        value_trap_alert=alert,
    )

    text = format_value_report(result)
    payload = json.loads(format_value_report(result, as_json=True))

    assert alert in text
    assert text.index(alert) < text.index("评估")
    assert "## 警告" in text
    assert payload["value_trap_alert"] == alert


def test_format_value_report_scenario_dcf_section():
    scenario = ValuationResult(
        method="Scenario DCF",
        fair_value=110.0,
        current_price=100.0,
        premium_discount=10.0,
        assessment="现价介于悲观与基准情景之间",
        details={
            "output_type": "scenario",
            "price_position": "between_bear_base",
            "scenarios": {
                "bear": {"label": "悲观", "fair_value": 80.0, "growth_rate_1_5": 6.0},
                "base": {"label": "基准", "fair_value": 110.0, "growth_rate_1_5": 12.0},
                "bull": {"label": "乐观", "fair_value": 150.0, "growth_rate_1_5": 18.0},
            },
        },
        applicability="Applicable",
    )
    result = ValueAnalysisResult(
        code="002594",
        name="比亚迪",
        current_price=100.0,
        prototype="growth_manufacturing",
        method_keys_used=["scenario_dcf"],
        fair_value_range=ValuationRange(low=80, base=110, high=150),
        margin_of_safety=9.0,
        price_percentile=40.0,
        assessment="现价介于悲观与基准情景之间",
        confidence="Medium",
        method_results={"scenario_dcf": scenario},
        methodology_applicable=True,
    )

    text = format_value_report(result)
    assert "## 浅情景 DCF" in text
    assert "悲观" in text and "基准" in text and "乐观" in text
    assert "现价落位" in text
    assert "方法暂不适用" not in text
    assert "对照用" not in text


def test_format_value_report_cyclical_section():
    fcf = ValuationResult(
        method="Cyclical FCF",
        fair_value=12.0,
        current_price=10.0,
        premium_discount=20.0,
        assessment="周期位置：周期中段；相对周期调整公允略便宜",
        details={
            "output_type": "cyclical",
            "cycle_position": "mid",
            "cycle_position_label": "周期中段",
            "fcf_yield": 8.5,
            "fair_fcf_yield": 7.0,
        },
        applicability="Applicable",
    )
    result = ValueAnalysisResult(
        code="002027",
        name="分众传媒",
        current_price=10.0,
        prototype="cashflow_ad_cycle",
        method_keys_used=["cyclical_fcf"],
        fair_value_range=ValuationRange(low=8, base=12, high=16),
        margin_of_safety=16.0,
        price_percentile=40.0,
        assessment="周期位置：周期中段；相对周期调整公允略便宜",
        confidence="Medium",
        method_results={"cyclical_fcf": fcf},
        methodology_applicable=True,
    )

    text = format_value_report(result)
    assert "## 周期调整估值" in text
    assert "周期位置" in text
    assert "Cyclical FCF" in text
    assert "方法暂不适用" not in text


def test_format_value_report_honesty_degrade_text_and_json():
    result = ValueAnalysisResult(
        code="002027",
        name="分众传媒",
        current_price=10.0,
        prototype="cashflow_ad_cycle",
        method_keys_used=["cyclical_fcf"],
        fair_value_range=ValuationRange(low=8, base=10, high=12),
        margin_of_safety=25.0,
        price_percentile=40.0,
        assessment="方法暂不适用",
        confidence="Low",
        warnings=[
            "检测到「现金流+广告周期」特征，缺周期位置或周期调整估值无法计算；"
            "通用方法得出的低估/高估不应用于买卖决策，当前结果参考性有限，不能作为买卖依据"
        ],
        methodology_applicable=False,
    )

    text = format_value_report(result)
    payload = json.loads(format_value_report(result, as_json=True))

    assert "方法暂不适用" in text
    assert "诚实降级" in text
    assert "对照用" in text
    assert "低估" not in text.split("评估")[1].split("\n")[0]
    assert payload["methodology_applicable"] is False
    assert payload["assessment"] == "方法暂不适用"


def test_format_value_report_omits_empty_value_trap_alert():
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

    assert "⚠⚠⚠" not in format_value_report(result)


def test_format_value_report_dcf_epv_semantic_hints():
    result = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1400.0,
        prototype="value_growth",
        method_keys_used=["dcf", "epv"],
        fair_value_range=ValuationRange(low=900, base=1400, high=1950),
        margin_of_safety=10.0,
        price_percentile=50.0,
        assessment="合理",
        confidence="Medium",
        method_results={
            "dcf": ValuationResult(
                method="DCF (10-Year)",
                fair_value=1950.0,
                current_price=1400.0,
                premium_discount=-28.2,
                assessment="低估",
                details={"growth_1_5": 8.0, "discount_rate": 5.4},
                applicability="Applicable",
            ),
            "epv": ValuationResult(
                method="EPV (Zero Growth)",
                fair_value=989.0,
                current_price=1400.0,
                premium_discount=41.6,
                assessment="高估",
                details={"implied_pe": 15.0},
                applicability="Applicable",
            ),
        },
    )
    text = format_value_report(result, as_json=False)
    assert "含增长假设" in text
    assert "g₁=8.0% 5年" in text
    assert "零增长地板价" in text


def test_format_tech_report_embeds_indicator_notes():
    text = format_tech_report(
        TechAnalysisResult(code="600519", buy_signal=BuySignal.HOLD, signal_score=50)
    )
    assert "指标说明" in text
    assert "RSI" in text


def test_format_value_mos_not_double_scaled():
    result = ValueAnalysisResult(
        code="002027",
        name="分众传媒",
        current_price=5.62,
        prototype="high_dividend",
        method_keys_used=[],
        fair_value_range=ValuationRange(low=3.0, base=5.58, high=8.0),
        margin_of_safety=-0.8,
        price_percentile=45.0,
        assessment="合理",
        confidence="Medium",
    )
    text = format_value_report(result)
    assert "安全边际: -0.8%" in text
    assert "-80%" not in text


def test_format_value_report_includes_method_cards():
    result = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1400.0,
        prototype="value_growth",
        method_keys_used=["ddm"],
        fair_value_range=ValuationRange(low=900, base=1400, high=1950),
        margin_of_safety=10.0,
        price_percentile=50.0,
        assessment="合理",
        confidence="Medium",
        method_results={
            "ddm": ValuationResult(
                method="DDM",
                fair_value=1950.0,
                current_price=1400.0,
                premium_discount=-28.2,
                assessment="Undervalued",
                details={
                    "formula": "P = D / (r - g)",
                    "dividend": 1.2,
                    "required_return": 8.0,
                    "growth_rate": 3.0,
                },
                applicability="Applicable",
            ),
        },
    )
    text = format_value_report(result)
    assert "估值方法详解" in text
    assert "P = D / (r - g)" in text
    assert "低估" in text


def test_format_dual_embeds_explanations_text_only():
    value = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=100.0,
        prototype="value_growth",
        method_keys_used=["ddm"],
        fair_value_range=None,
        margin_of_safety=-0.8,
        price_percentile=None,
        assessment="合理",
        confidence="Medium",
        method_results={
            "value_trap": ValuationResult(
                method="Value Trap Detector",
                fair_value=100.0,
                current_price=100.0,
                premium_discount=0.0,
                assessment="Medium Value Trap Risk",
                details={
                    "overall_risk": "Medium",
                    "financial_health": "Low",
                    "financial_health_note": "ok",
                    "business_deterioration": "Medium",
                    "business_deterioration_note": "x",
                    "moat_erosion": "Low",
                    "moat_erosion_note": "y",
                    "ai_vulnerability": "Medium",
                    "ai_vulnerability_note": "manual",
                    "dividend_sustainability": "Low",
                    "dividend_sustainability_note": "z",
                },
                applicability="Applicable",
            )
        },
    )
    tech = TechAnalysisResult(code="600519", signal_score=60)
    text = format_dual_report(
        "600519",
        ["bull"],
        ["bear"],
        analysis_summary="安全边际: -0.8%",
        value_result=value,
        tech_result=tech,
    )
    payload = format_dual_report(
        "600519",
        ["bull"],
        ["bear"],
        as_json=True,
        value_result=value,
        tech_result=tech,
    )
    assert "价值面讲解" in text
    assert "技术面讲解" in text
    assert "价值陷阱" in text
    assert "指标说明" in text
    assert "bull_evidence" in payload
    assert "价值面讲解" not in payload
