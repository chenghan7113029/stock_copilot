"""对抗叙事相关模型（declare 字段由后续 change 扩展）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NumberedEvidenceItem:
    index: int
    text: str

    def to_dict(self) -> dict[str, int | str]:
        return {"index": self.index, "text": self.text}


@dataclass(frozen=True)
class ConfrontationSnapshot:
    """一次 confront 的内存视图。"""

    code: str
    evidence: dict[str, Any]
    narrate_status: str
    narrative: dict[str, Any] | None = None
    confrontation_id: int | None = None
    narrate_error: str | None = None
    from_cache: bool = False
    low_confidence_warning: bool = False
