"""Confrontation 用户立场声明模型与 JSON schema。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STANCE_VALUES = frozenset({"adopt_bull", "adopt_bear", "partial", "abstain"})
SIDE_VALUES = frozenset({"bull", "bear", "none"})
FORBIDDEN_DECLARE_KEYS = frozenset({"order", "signal", "action_buy"})

DECLARATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "stance",
        "adopted_side",
        "rejected_side",
        "adopted_evidence_refs",
        "rejected_evidence_refs",
        "rejection_rationale",
        "confidence",
    ],
    "properties": {
        "stance": {"type": "string", "enum": sorted(STANCE_VALUES)},
        "adopted_side": {"type": "string", "enum": sorted(SIDE_VALUES)},
        "rejected_side": {"type": "string", "enum": sorted(SIDE_VALUES)},
        "adopted_evidence_refs": {
            "type": "object",
            "properties": {
                "bull": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                "bear": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            },
            "required": ["bull", "bear"],
        },
        "rejected_evidence_refs": {
            "type": "object",
            "properties": {
                "bull": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                "bear": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            },
            "required": ["bull", "bear"],
        },
        "rejection_rationale": {"type": "string"},
        "residual_uncertainty": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


@dataclass
class SideEvidenceRefs:
    bull: list[int] = field(default_factory=list)
    bear: list[int] = field(default_factory=list)

    def any(self) -> bool:
        return bool(self.bull or self.bear)

    def as_dict(self) -> dict[str, list[int]]:
        return {"bull": list(self.bull), "bear": list(self.bear)}


@dataclass
class ConfrontationDeclaration:
    stance: str
    adopted_side: str
    rejected_side: str
    adopted_evidence_refs: SideEvidenceRefs
    rejected_evidence_refs: SideEvidenceRefs
    rejection_rationale: str
    confidence: float
    residual_uncertainty: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["adopted_evidence_refs"] = self.adopted_evidence_refs.as_dict()
        payload["rejected_evidence_refs"] = self.rejected_evidence_refs.as_dict()
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ConfrontationDeclaration:
        adopted = raw.get("adopted_evidence_refs") or {}
        rejected = raw.get("rejected_evidence_refs") or {}
        return cls(
            stance=str(raw.get("stance", "")),
            adopted_side=str(raw.get("adopted_side", "")),
            rejected_side=str(raw.get("rejected_side", "")),
            adopted_evidence_refs=SideEvidenceRefs(
                bull=_as_int_list(adopted.get("bull")),
                bear=_as_int_list(adopted.get("bear")),
            ),
            rejected_evidence_refs=SideEvidenceRefs(
                bull=_as_int_list(rejected.get("bull")),
                bear=_as_int_list(rejected.get("bear")),
            ),
            rejection_rationale=str(raw.get("rejection_rationale") or ""),
            residual_uncertainty=str(raw.get("residual_uncertainty") or ""),
            confidence=float(raw.get("confidence", -1)),
        )


def _as_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out
