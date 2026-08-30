"""ConfrontationDeclarationValidator 单元测试。"""

from __future__ import annotations

from service.guard.confrontation_declaration_validator import ConfrontationDeclarationValidator
from service.guard.models.confrontation_declaration import (
    ConfrontationDeclaration,
    SideEvidenceRefs,
)

EVIDENCE = {
    "bull_evidence": [
        {"index": 1, "text": "低估"},
        {"index": 2, "text": "趋势"},
    ],
    "bear_evidence": [
        {"index": 1, "text": "风险A"},
        {"index": 2, "text": "风险B"},
        {"index": 3, "text": "风险C"},
    ],
}


def _decl(**overrides) -> ConfrontationDeclaration:
    base = ConfrontationDeclaration(
        stance="adopt_bull",
        adopted_side="bull",
        rejected_side="bear",
        adopted_evidence_refs=SideEvidenceRefs(bull=[1], bear=[]),
        rejected_evidence_refs=SideEvidenceRefs(bull=[], bear=[2]),
        rejection_rationale="拒绝空方[2]：证据不足",
        confidence=0.7,
    )
    data = base.to_dict()
    data.update(overrides)
    if "adopted_evidence_refs" in overrides and isinstance(overrides["adopted_evidence_refs"], dict):
        data["adopted_evidence_refs"] = overrides["adopted_evidence_refs"]
    if "rejected_evidence_refs" in overrides and isinstance(overrides["rejected_evidence_refs"], dict):
        data["rejected_evidence_refs"] = overrides["rejected_evidence_refs"]
    return ConfrontationDeclaration.from_dict(data)


def test_out_of_range_ref_rejected():
    result = ConfrontationDeclarationValidator().validate(
        _decl(rejected_evidence_refs={"bull": [], "bear": [99]}),
        evidence=EVIDENCE,
    )
    assert not result.ok
    assert any("越界" in e for e in result.errors)


def test_missing_rationale_rejected():
    result = ConfrontationDeclarationValidator().validate(
        _decl(rejection_rationale=""),
        evidence=EVIDENCE,
    )
    assert not result.ok
    assert any("rejection_rationale" in e for e in result.errors)


def test_success_path():
    result = ConfrontationDeclarationValidator().validate(_decl(), evidence=EVIDENCE)
    assert result.ok


def test_already_declared_rejected():
    result = ConfrontationDeclarationValidator().validate(
        _decl(),
        evidence=EVIDENCE,
        already_declared=True,
    )
    assert not result.ok
    assert any("不允许覆盖" in e for e in result.errors)


def test_illegal_stance_rejected():
    result = ConfrontationDeclarationValidator().validate(
        _decl(stance="buy_hard"),
        evidence=EVIDENCE,
    )
    assert not result.ok
    assert any("stance" in e for e in result.errors)
