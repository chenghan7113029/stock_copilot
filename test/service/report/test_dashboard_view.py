"""DashboardView 单元测试。"""

from __future__ import annotations

from service.report.models.dashboard_view import DashboardView


def test_dashboard_view_defaults():
    view = DashboardView(code="600519")
    assert view.code == "600519"
    assert view.value_section == ""
    assert view.tech_section == ""
    assert view.sentiment_section == ""
    assert view.checklist_section == ""
    assert view.combined_summary == ""
    assert view.warnings == []


def test_dashboard_view_field_types():
    view = DashboardView(
        code="600519",
        value_section="价值面摘要",
        tech_section="技术面摘要",
        sentiment_section="情绪面待建（见 PO-06）",
        checklist_section="Checklist 待建（见 PO-04）",
        combined_summary="综合信号: 买入",
        warnings=["warn-1"],
    )
    assert isinstance(view.value_section, str)
    assert isinstance(view.warnings, list)
    assert view.warnings == ["warn-1"]
