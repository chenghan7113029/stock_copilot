"""看板展示态数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DashboardView:
    """单票多维看板的展示态产物（与 CLI 解耦）。"""

    code: str
    value_section: str = ""
    tech_section: str = ""
    sentiment_section: str = ""
    checklist_section: str = ""
    combined_summary: str = ""
    warnings: list[str] = field(default_factory=list)
