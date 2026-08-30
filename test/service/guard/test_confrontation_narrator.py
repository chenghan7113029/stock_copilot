"""ConfrontationNarrator 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from common.llm.models import NarrateResult
from service.dual_track.evidence_bucketer import EvidenceBuckets
from service.guard.confrontation_narrator import ConfrontationNarrator


def test_build_evidence_numbers_both_sides():
    buckets = EvidenceBuckets(bull_evidence=["b1", "b2"], bear_evidence=["r1"])
    payload = ConfrontationNarrator().build_evidence(
        buckets, code="600519", analysis_summary="摘要"
    )
    assert payload["code"] == "600519"
    assert payload["bull_evidence"] == [
        {"index": 1, "text": "b1"},
        {"index": 2, "text": "b2"},
    ]
    assert payload["bear_evidence"] == [{"index": 1, "text": "r1"}]


def test_narrate_success_returns_narrative(monkeypatch):
    narrator = ConfrontationNarrator()
    buckets = EvidenceBuckets(bull_evidence=["多方证据"], bear_evidence=["空方证据"])

    def _fake_narrate(evidence, schema, instruction, **kwargs):
        return NarrateResult(
            ok=True,
            data={
                "bull_thesis": "多方",
                "bear_thesis": "空方",
                "bull_rebuttals": [{"target_side": "bear", "target_index": 1, "text": "反驳"}],
                "bear_rebuttals": [{"target_side": "bull", "target_index": 1, "text": "反驳"}],
                "disclaimer": "叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实。不构成买卖建议。",
                "confidence": 0.9,
            },
            confidence=0.9,
            grounded=True,
        )

    monkeypatch.setattr(
        "service.guard.confrontation_narrator.narrate",
        _fake_narrate,
    )
    outcome = narrator.narrate(buckets, code="600519")
    assert outcome.result.ok is True
    assert outcome.narrative is not None
    assert outcome.narrative["bull_thesis"] == "多方"


def test_narrate_grounded_failure_has_no_narrative(monkeypatch):
    narrator = ConfrontationNarrator()
    buckets = EvidenceBuckets(bull_evidence=["多方证据"], bear_evidence=["空方证据"])

    monkeypatch.setattr(
        "service.guard.confrontation_narrator.narrate",
        lambda *a, **k: NarrateResult(
            ok=False, error="grounded 校验失败", grounded=False
        ),
    )
    outcome = narrator.narrate(buckets, code="600519")
    assert outcome.result.ok is False
    assert outcome.narrative is None


def test_narrate_uses_cache_when_provided(monkeypatch):
    narrator = ConfrontationNarrator()
    buckets = EvidenceBuckets(bull_evidence=["多方证据"], bear_evidence=["空方证据"])
    cache = MagicMock()
    calls = {"n": 0}

    def _fake_narrate(evidence, schema, instruction, **kwargs):
        calls["n"] += 1
        assert kwargs.get("cache") is cache
        return NarrateResult(
            ok=True,
            data={
                "bull_thesis": "多方",
                "bear_thesis": "空方",
                "bull_rebuttals": [],
                "bear_rebuttals": [],
                "disclaimer": "x",
                "confidence": 0.85,
            },
            confidence=0.85,
            grounded=True,
            from_cache=True,
        )

    monkeypatch.setattr(
        "service.guard.confrontation_narrator.narrate",
        _fake_narrate,
    )
    outcome = narrator.narrate(buckets, code="600519", cache=cache)
    assert outcome.result.from_cache is True
    assert calls["n"] == 1
