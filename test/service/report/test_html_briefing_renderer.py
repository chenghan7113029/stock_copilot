"""HtmlBriefingRenderer 单元测试。"""

from __future__ import annotations

from service.report.html_briefing_renderer import HtmlBriefingRenderer
from service.report.models.briefing_view import BriefingView, SectionStatus


def _sample_view(**overrides) -> BriefingView:
    view = BriefingView(
        code="600519",
        name="贵州茅台",
        combined_signal="强烈买入",
        value_rating="低估",
        conflict_summary="综合信号强烈买入",
        data_timestamp="2026-06-21T00:00:00+00:00",
        confrontation_id=12,
        current_price=1500.0,
        fair_low=1800.0,
        fair_base=2000.0,
        fair_high=2200.0,
        margin_of_safety=25.0,
        value_assessment="低估",
        value_prototype="value_growth",
        value_confidence="High",
        tech_score=80,
        tech_trend="强势多头",
        tech_signal="强烈买入",
        sentiment_score=55.0,
        sentiment_status="中性",
        bull_evidence=[{"index": 1, "text": "低估且安全边际充足"}],
        bear_evidence=[{"index": 1, "text": "估值波动风险"}],
        narrative={
            "bull_thesis": "多方认为低估",
            "bear_thesis": "空方关注风险",
            "bull_rebuttals": [{"target_index": 1, "text": "风险已计价"}],
            "bear_rebuttals": [{"target_index": 1, "text": "安全边际不够"}],
            "disclaimer": "叙事免责",
        },
        persona_stress={
            "personas": [
                {
                    "id": "value_quality",
                    "status": "ok",
                    "output": {"lens_summary": "质量可接受"},
                }
            ],
            "disclaimer": "透镜免责",
        },
        value_method_rows=[
            {"key": "dcf", "fair_value": 2000.0, "label": "Undervalued", "applicable": "Applicable"}
        ],
        tech_reasons=["MA 金叉", "布林带收窄"],
        boll_mid=1600.0,
        boll_upper=1700.0,
        boll_lower=1500.0,
        boll_bandwidth=0.12,
        boll_percentile=40.0,
        boll_status="正常",
        price_series=[
            {"date": f"2026-06-{i:02d}", "close": 1480.0 + i}
            for i in range(1, 11)
        ],
        price_high=1490.0,
        price_low=1481.0,
        candlestick_patterns=[
            {
                "pattern": "hammer",
                "direction": "bullish",
                "trade_date": "2026-06-20",
                "description": "锤头",
            }
        ],
        checklist_summary="",
        declare_summary="",
        section_statuses={
            "value": SectionStatus(status="ok"),
            "tech": SectionStatus(status="ok"),
            "sentiment": SectionStatus(status="ok"),
            "evidence": SectionStatus(status="ok"),
            "narrative": SectionStatus(status="ok"),
            "persona": SectionStatus(status="ok"),
            "price_context": SectionStatus(status="ok"),
            "checklist": SectionStatus(
                status="missing", hint="尚未提交 Checklist。可运行：checklist submit 600519"
            ),
            "declare": SectionStatus(
                status="missing", hint="尚未 declare。可读完证据后运行：confront declare 12"
            ),
        },
    )
    for key, value in overrides.items():
        setattr(view, key, value)
    return view


def test_renderer_contains_html_sections_and_viz():
    html = HtmlBriefingRenderer().render(_sample_view())
    assert "<html" in html.lower()
    assert "深度复盘" in html
    assert "600519" in html
    assert "贵州茅台" in html
    assert "三维快扫" in html
    assert "价格情境" in html
    assert "price-svg" in html
    assert "fair-line" in html
    assert "evidence-cols" in html
    assert "col-bull" in html
    assert "col-bear" in html
    assert "冲突与立场" in html
    assert "价值面深潜" in html
    assert "技术面深潜" in html
    assert "决策痕迹" in html
    assert "range-viz" in html
    assert "bar-fill" in html
    assert "evidence-bars" in html
    assert "tip-q" in html
    assert "现金流贴现" in html or "DCF" in html
    assert "checklist submit" in html
    assert "confront declare" in html
    assert "max-width: 1240px" in html
    assert "<style>" in html
    assert "cdn." not in html.lower()
    assert "chart.js" not in html.lower()


def test_renderer_failed_callout_visible():
    view = _sample_view()
    view.narrative = None
    view.section_statuses["narrative"] = SectionStatus(
        status="failed",
        hint="互驳叙事失败：LLM down。可重试：report confront 600519 --narrate",
    )
    html = HtmlBriefingRenderer().render(view)
    assert "callout error" in html
    assert "LLM down" in html
    assert "report confront" in html
