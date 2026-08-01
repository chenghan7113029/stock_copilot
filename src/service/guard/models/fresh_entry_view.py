"""无仓位视角的入场检查输出模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreshEntryView:
    code: str
    current_price: float
    value_summary: str
    tech_summary: str
    framing_question: str
    has_position: bool
    reminder_text: str
