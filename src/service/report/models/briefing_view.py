"""周末深度复盘 Briefing Pack 展示态模型（只组装、不重算）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SectionStatus:
    """可选章节状态：ok / missing / failed。"""

    status: str  # ok | missing | failed
    hint: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status, "hint": self.hint}


@dataclass
class BriefingView:
    """单票 HTML Briefing 的结构化产物。"""

    code: str
    name: str = ""
    combined_signal: str = ""
    value_rating: str = ""
    conflict_summary: str = ""
    data_timestamp: str = ""
    confrontation_id: int | None = None

    # 三维快扫（标量，供可视化）
    current_price: float | None = None
    fair_low: float | None = None
    fair_base: float | None = None
    fair_high: float | None = None
    margin_of_safety: float | None = None
    value_assessment: str = ""
    value_prototype: str = ""
    value_confidence: str = ""

    tech_score: int | None = None
    tech_trend: str = ""
    tech_signal: str = ""
    tech_price: float | None = None

    sentiment_score: float | None = None
    sentiment_status: str = ""
    sentiment_note: str = ""

    # 冲突与立场
    bull_evidence: list[dict[str, Any]] = field(default_factory=list)
    bear_evidence: list[dict[str, Any]] = field(default_factory=list)
    narrative: dict[str, Any] | None = None
    persona_stress: dict[str, Any] | None = None

    # 深潜摘要（结构化短列表，非全文重算）
    value_method_rows: list[dict[str, Any]] = field(default_factory=list)
    value_warnings: list[str] = field(default_factory=list)
    tech_reasons: list[str] = field(default_factory=list)
    tech_risks: list[str] = field(default_factory=list)
    boll_mid: float | None = None
    boll_upper: float | None = None
    boll_lower: float | None = None
    boll_bandwidth: float | None = None
    boll_percentile: float | None = None
    boll_status: str = ""
    candlestick_patterns: list[dict[str, Any]] = field(default_factory=list)

    # 决策痕迹
    checklist_summary: str = ""
    declare_summary: str = ""

    section_statuses: dict[str, SectionStatus] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    disclaimer: str = (
        "本报告仅供学习与决策参考，不构成投资建议。"
        "AI 叙事请对照上方原始证据列表核实。"
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["section_statuses"] = {
            key: status.to_dict() if isinstance(status, SectionStatus) else status
            for key, status in self.section_statuses.items()
        }
        return payload
