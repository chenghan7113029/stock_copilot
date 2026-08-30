"""PersonaStressNarrator 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from common.llm.models import NarrateResult
from service.dual_track.evidence_bucketer import EvidenceBuckets
from service.guard.persona_stress_narrator import (
    PERSONA_IDS,
    PersonaStressNarrator,
    pending_persona_stress,
    validate_emphasized_refs,
)


def _ok_persona_data(*, index: int = 1) -> dict:
    return {
        "lens_summary": "解读",
        "emphasized_refs": [{"side": "bull", "index": index}],
        "blind_spots": ["忽略动量"],
        "questions_for_self": ["我是否只看一面？"],
        "disclaimer": "persona 为思维透镜，不构成买卖建议。三种 lens 冲突时，应回到 declare 明确立场。",
        "confidence": 0.8,
    }


def test_pending_persona_stress_has_three_pending():
    payload = pending_persona_stress()
    assert len(payload["personas"]) == 3
    assert {p["id"] for p in payload["personas"]} == set(PERSONA_IDS)
    assert all(p["status"] == "pending" for p in payload["personas"])


def test_validate_emphasized_refs_rejects_oob():
    evidence = {
        "bull_evidence": [{"index": 1, "text": "b1"}],
        "bear_evidence": [{"index": 1, "text": "r1"}],
    }
    assert validate_emphasized_refs(
        {"emphasized_refs": [{"side": "bull", "index": 1}]}, evidence
    )
    assert not validate_emphasized_refs(
        {"emphasized_refs": [{"side": "bull", "index": 9}]}, evidence
    )


def test_stress_all_personas_succeed(monkeypatch):
    narrator = PersonaStressNarrator()
    evidence = narrator.build_evidence(
        EvidenceBuckets(bull_evidence=["多方"], bear_evidence=["空方"]),
        code="600519",
    )
    calls: list[str] = []

    def _fake_narrate(ev, schema, instruction, **kwargs):
        calls.append(instruction[:20])
        return NarrateResult(ok=True, data=_ok_persona_data(), confidence=0.8, grounded=True)

    monkeypatch.setattr(
        "service.guard.persona_stress_narrator.narrate",
        _fake_narrate,
    )
    outcome = narrator.stress(evidence)
    assert len(outcome.payload["personas"]) == 3
    assert all(p["status"] == "ok" for p in outcome.payload["personas"])
    assert len(calls) == 3


def test_stress_isolates_single_persona_failure(monkeypatch):
    narrator = PersonaStressNarrator()
    evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [{"index": 1, "text": "空方"}],
    }
    n = {"i": 0}

    def _fake_narrate(ev, schema, instruction, **kwargs):
        n["i"] += 1
        # 第二个 persona（trend_momentum）失败
        if n["i"] == 2:
            return NarrateResult(ok=False, error="grounded 校验失败", grounded=False)
        return NarrateResult(ok=True, data=_ok_persona_data(), confidence=0.8, grounded=True)

    monkeypatch.setattr(
        "service.guard.persona_stress_narrator.narrate",
        _fake_narrate,
    )
    outcome = narrator.stress(evidence)
    statuses = {p["id"]: p["status"] for p in outcome.payload["personas"]}
    assert statuses["value_quality"] == "ok"
    assert statuses["trend_momentum"] == "failed"
    assert statuses["risk_governor"] == "ok"


def test_stress_retries_on_invalid_emphasized_refs(monkeypatch):
    narrator = PersonaStressNarrator()
    evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [{"index": 1, "text": "空方"}],
    }
    attempts = {"n": 0}

    def _fake_narrate(ev, schema, instruction, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            bad = _ok_persona_data(index=99)
            return NarrateResult(ok=True, data=bad, confidence=0.5, grounded=True)
        return NarrateResult(ok=True, data=_ok_persona_data(), confidence=0.8, grounded=True)

    monkeypatch.setattr(
        "service.guard.persona_stress_narrator.narrate",
        _fake_narrate,
    )
    # 只跑一个 persona，便于断言重试次数
    outcome = narrator.stress(evidence, persona_ids=("value_quality",))
    assert outcome.payload["personas"][0]["status"] == "ok"
    assert attempts["n"] == 2


def test_stress_passes_cache(monkeypatch):
    narrator = PersonaStressNarrator()
    evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [],
    }
    cache = MagicMock()
    seen = {"cache": False}

    def _fake_narrate(ev, schema, instruction, **kwargs):
        seen["cache"] = kwargs.get("cache") is cache
        return NarrateResult(ok=True, data=_ok_persona_data(), confidence=0.8, grounded=True)

    monkeypatch.setattr(
        "service.guard.persona_stress_narrator.narrate",
        _fake_narrate,
    )
    narrator.stress(evidence, cache=cache, persona_ids=("value_quality",))
    assert seen["cache"] is True
