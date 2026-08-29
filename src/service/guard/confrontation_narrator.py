"""红蓝对抗 Level 1：numbered evidence → grounded 互驳叙事。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.llm.client import LLMClient
from common.llm.models import NarrateResult
from common.llm.narrator import NarrateCache, narrate
from service.dual_track.evidence_bucketer import EvidenceBuckets

CONFRONTATION_NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "bull_thesis",
        "bear_thesis",
        "bull_rebuttals",
        "bear_rebuttals",
        "disclaimer",
        "confidence",
    ],
    "properties": {
        "bull_thesis": {
            "type": "string",
            "description": "多方论述，仅基于 bull_evidence",
        },
        "bear_thesis": {
            "type": "string",
            "description": "空方论述，仅基于 bear_evidence",
        },
        "bull_rebuttals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target_side", "target_index", "text"],
                "properties": {
                    "target_side": {"type": "string", "enum": ["bear"]},
                    "target_index": {"type": "integer", "minimum": 1},
                    "text": {"type": "string"},
                },
            },
        },
        "bear_rebuttals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target_side", "target_index", "text"],
                "properties": {
                    "target_side": {"type": "string", "enum": ["bull"]},
                    "target_index": {"type": "integer", "minimum": 1},
                    "text": {"type": "string"},
                },
            },
        },
        "disclaimer": {
            "type": "string",
            "description": "固定免责声明",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
    },
}

_DISCLAIMER = "叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实。不构成买卖建议。"

CONFRONTATION_NARRATIVE_INSTRUCTION = (
    "请基于给定 evidence 中的 numbered bull_evidence / bear_evidence 生成红蓝互驳叙事。"
    "bull_thesis 只能使用 bull_evidence；bear_thesis 只能使用 bear_evidence。"
    "bull_rebuttals 必须反驳空方证据（target_side=bear，target_index 为合法序号）；"
    "bear_rebuttals 必须反驳多方证据（target_side=bull）。"
    "每条反驳须明确引用对方证据序号。"
    "disclaimer 字段必须原样输出："
    f"{_DISCLAIMER}"
    "不得引入 evidence 之外的任何新数字、新百分比或新事实；"
    "不确定时写「证据未覆盖，不作断言」。"
)


@dataclass(frozen=True)
class ConfrontationNarrateOutcome:
    """Level 1 叙事结果 + 落库用 narrative dict。"""

    result: NarrateResult
    narrative: dict[str, Any] | None
    evidence_payload: dict[str, Any]


class ConfrontationNarrator:
    """封装 evidence 打包、schema、grounded narrate 与缓存键。"""

    def build_evidence(
        self,
        buckets: EvidenceBuckets,
        *,
        code: str,
        analysis_summary: str = "",
    ) -> dict[str, Any]:
        numbered = buckets.numbered()
        return {
            "code": code,
            "analysis_summary": analysis_summary,
            "bull_evidence": numbered["bull_evidence"],
            "bear_evidence": numbered["bear_evidence"],
        }

    def narrate(
        self,
        buckets: EvidenceBuckets,
        *,
        code: str,
        analysis_summary: str = "",
        config: dict[str, Any] | None = None,
        client: LLMClient | None = None,
        cache: NarrateCache | None = None,
        force_refresh: bool = False,
    ) -> ConfrontationNarrateOutcome:
        evidence = self.build_evidence(
            buckets, code=code, analysis_summary=analysis_summary
        )
        result = narrate(
            evidence,
            CONFRONTATION_NARRATIVE_SCHEMA,
            CONFRONTATION_NARRATIVE_INSTRUCTION,
            config=config,
            client=client,
            cache=cache,
            force_refresh=force_refresh,
        )
        narrative = result.data if result.ok and isinstance(result.data, dict) else None
        if narrative is not None and not narrative.get("disclaimer"):
            narrative = {**narrative, "disclaimer": _DISCLAIMER}
        return ConfrontationNarrateOutcome(
            result=result,
            narrative=narrative,
            evidence_payload=evidence,
        )
