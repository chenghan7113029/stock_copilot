"""Persona 压力测试：同一 numbered evidence 上的三固定 lens。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.llm.client import LLMClient
from common.llm.models import NarrateResult
from common.llm.narrator import NarrateCache, narrate
from service.dual_track.evidence_bucketer import EvidenceBuckets

PERSONA_IDS: tuple[str, ...] = (
    "value_quality",
    "trend_momentum",
    "risk_governor",
)

PERSONA_LABELS: dict[str, str] = {
    "value_quality": "价值质量",
    "trend_momentum": "趋势动量",
    "risk_governor": "风控官",
}

_DISCLAIMER = (
    "persona 为思维透镜，不构成买卖建议。"
    "三种 lens 冲突时，应回到 declare 明确立场。"
)

PERSONA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "lens_summary",
        "emphasized_refs",
        "blind_spots",
        "questions_for_self",
        "disclaimer",
        "confidence",
    ],
    "properties": {
        "lens_summary": {
            "type": "string",
            "description": "该 persona lens 下的核心解读",
        },
        "emphasized_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["side", "index"],
                "properties": {
                    "side": {"type": "string", "enum": ["bull", "bear"]},
                    "index": {"type": "integer", "minimum": 1},
                },
            },
        },
        "blind_spots": {
            "type": "array",
            "items": {"type": "string"},
            "description": "本 lens 刻意弱化或忽略的证据面",
        },
        "questions_for_self": {
            "type": "array",
            "items": {"type": "string"},
            "description": "向决策者提出的自省问题",
        },
        "disclaimer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

_PERSONA_INTENTS: dict[str, str] = {
    "value_quality": (
        "你是价值质量投资者 lens：关注护城河、现金流、安全边际；"
        "质疑短期趋势噪音；显式指出被忽略的动量证据。"
    ),
    "trend_momentum": (
        "你是趋势动量投资者 lens：关注趋势与信号动能；"
        "质疑「便宜但无动能」；显式指出被忽略的价值面证据。"
    ),
    "risk_governor": (
        "你是风控官 lens：关注价值陷阱、最坏情形、止损与仓位底线；"
        "对多空两边证据都保持怀疑。"
    ),
}


def _instruction_for(persona_id: str) -> str:
    intent = _PERSONA_INTENTS[persona_id]
    return (
        f"{intent}"
        "请仅基于给定 evidence 中的 numbered bull_evidence / bear_evidence 输出 JSON。"
        "emphasized_refs 必须引用合法 side+index；"
        "不得引入 evidence 之外的任何新数字、新百分比或新事实；"
        "不确定时写「证据未覆盖，不作断言」。"
        "disclaimer 字段必须原样输出："
        f"{_DISCLAIMER}"
    )


def validate_emphasized_refs(
    output: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    """校验 emphasized_refs 的 side/index 均在 numbered evidence 范围内。"""
    bull_max = len(evidence.get("bull_evidence") or [])
    bear_max = len(evidence.get("bear_evidence") or [])
    refs = output.get("emphasized_refs")
    if not isinstance(refs, list):
        return False
    for ref in refs:
        if not isinstance(ref, dict):
            return False
        side = ref.get("side")
        index = ref.get("index")
        if not isinstance(index, int):
            return False
        if side == "bull":
            if index < 1 or index > bull_max:
                return False
        elif side == "bear":
            if index < 1 or index > bear_max:
                return False
        else:
            return False
    return True


def pending_persona_stress() -> dict[str, Any]:
    """Level 0：三 persona 待 narrate 占位。"""
    return {
        "personas": [
            {"id": pid, "status": "pending", "output": None, "error": None}
            for pid in PERSONA_IDS
        ],
        "disclaimer": _DISCLAIMER,
    }


@dataclass(frozen=True)
class PersonaStressOutcome:
    """三 persona 压力测试聚合结果。"""

    payload: dict[str, Any]
    evidence_payload: dict[str, Any]


class PersonaStressNarrator:
    """对固定 persona 分别 narrate；单 persona 失败不阻塞其余。"""

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

    def stress(
        self,
        evidence: dict[str, Any],
        *,
        config: dict[str, Any] | None = None,
        client: LLMClient | None = None,
        cache: NarrateCache | None = None,
        force_refresh: bool = False,
        persona_ids: tuple[str, ...] | None = None,
    ) -> PersonaStressOutcome:
        ids = persona_ids or PERSONA_IDS
        personas: list[dict[str, Any]] = []
        for persona_id in ids:
            if persona_id not in _PERSONA_INTENTS:
                personas.append(
                    {
                        "id": persona_id,
                        "status": "failed",
                        "output": None,
                        "error": f"未知 persona: {persona_id}",
                    }
                )
                continue
            entry = self._narrate_one(
                persona_id,
                evidence,
                config=config,
                client=client,
                cache=cache,
                force_refresh=force_refresh,
            )
            personas.append(entry)
        return PersonaStressOutcome(
            payload={"personas": personas, "disclaimer": _DISCLAIMER},
            evidence_payload=evidence,
        )

    def _narrate_one(
        self,
        persona_id: str,
        evidence: dict[str, Any],
        *,
        config: dict[str, Any] | None,
        client: LLMClient | None,
        cache: NarrateCache | None,
        force_refresh: bool,
    ) -> dict[str, Any]:
        instruction = _instruction_for(persona_id)
        # 分 persona cache：instruction 不同 → compute_cache_key 自然隔离
        result = narrate(
            evidence,
            PERSONA_OUTPUT_SCHEMA,
            instruction,
            config=config,
            client=client,
            cache=cache,
            force_refresh=force_refresh,
        )
        output, error = self._accept_or_retry(
            result,
            evidence,
            instruction=instruction,
            config=config,
            client=client,
            cache=cache,
        )
        if output is not None:
            if not output.get("disclaimer"):
                output = {**output, "disclaimer": _DISCLAIMER}
            return {
                "id": persona_id,
                "status": "ok",
                "output": output,
                "error": None,
            }
        return {
            "id": persona_id,
            "status": "failed",
            "output": None,
            "error": error or "persona narrate 失败",
        }

    def _accept_or_retry(
        self,
        result: NarrateResult,
        evidence: dict[str, Any],
        *,
        instruction: str,
        config: dict[str, Any] | None,
        client: LLMClient | None,
        cache: NarrateCache | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if result.ok and isinstance(result.data, dict):
            if validate_emphasized_refs(result.data, evidence):
                return result.data, None
            # 非法 ref：强制重试一次
            retry = narrate(
                evidence,
                PERSONA_OUTPUT_SCHEMA,
                instruction,
                config=config,
                client=client,
                cache=cache,
                force_refresh=True,
            )
            if retry.ok and isinstance(retry.data, dict):
                if validate_emphasized_refs(retry.data, evidence):
                    return retry.data, None
                return None, "emphasized_refs 越界，post-validator 失败"
            return None, retry.error or "emphasized_refs 校验失败后重试失败"
        return None, result.error or "LLM 叙事失败"
