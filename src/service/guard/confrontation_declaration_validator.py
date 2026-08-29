"""ConfrontationDeclaration 确定性校验（零 LLM）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from service.guard.models.confrontation_declaration import (
    FORBIDDEN_DECLARE_KEYS,
    SIDE_VALUES,
    STANCE_VALUES,
    ConfrontationDeclaration,
)

# 要求 rationale 中至少出现一次 [n] 或 [bull:n] / [bear:n]
_REF_IN_TEXT = re.compile(r"\[(?:bull|bear)[:\s-]?\d+|\d+\]", re.IGNORECASE)


@dataclass(frozen=True)
class DeclarationValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


class ConfrontationDeclarationValidator:
    """纯规则校验用户 declare。"""

    def validate(
        self,
        declaration: ConfrontationDeclaration | dict[str, Any],
        *,
        evidence: dict[str, Any],
        already_declared: bool = False,
    ) -> DeclarationValidationResult:
        errors: list[str] = []
        if already_declared:
            errors.append("该 confrontation 已有成功 declare，V1 不允许覆盖")

        raw = declaration if isinstance(declaration, dict) else declaration.to_dict()
        forbidden = sorted(set(raw) & FORBIDDEN_DECLARE_KEYS)
        if forbidden:
            errors.append(f"禁止字段: {', '.join(forbidden)}")

        decl = (
            declaration
            if isinstance(declaration, ConfrontationDeclaration)
            else ConfrontationDeclaration.from_dict(raw)
        )

        if decl.stance not in STANCE_VALUES:
            errors.append(f"非法 stance: {decl.stance!r}")
        if decl.adopted_side not in SIDE_VALUES:
            errors.append(f"非法 adopted_side: {decl.adopted_side!r}")
        if decl.rejected_side not in SIDE_VALUES:
            errors.append(f"非法 rejected_side: {decl.rejected_side!r}")
        if not (0.0 <= decl.confidence <= 1.0):
            errors.append("confidence 必须在 [0, 1]")

        bull_max = _side_max_index(evidence, "bull")
        bear_max = _side_max_index(evidence, "bear")
        errors.extend(_check_refs("adopted_evidence_refs.bull", decl.adopted_evidence_refs.bull, bull_max))
        errors.extend(_check_refs("adopted_evidence_refs.bear", decl.adopted_evidence_refs.bear, bear_max))
        errors.extend(_check_refs("rejected_evidence_refs.bull", decl.rejected_evidence_refs.bull, bull_max))
        errors.extend(_check_refs("rejected_evidence_refs.bear", decl.rejected_evidence_refs.bear, bear_max))

        if decl.rejected_evidence_refs.any():
            if not decl.rejection_rationale.strip():
                errors.append("拒绝证据非空时 rejection_rationale 不能为空")
            elif not _REF_IN_TEXT.search(decl.rejection_rationale):
                errors.append("rejection_rationale 须包含证据引用，如 [1] 或 [bear:2]")

        if decl.stance == "partial":
            if not (
                decl.adopted_evidence_refs.any() and decl.rejected_evidence_refs.any()
            ):
                errors.append("stance=partial 时 adopted 与 rejected 两侧 refs 均须非空")

        return DeclarationValidationResult(ok=not errors, errors=errors)


def _side_max_index(evidence: dict[str, Any], side: str) -> int:
    items = evidence.get(f"{side}_evidence") or []
    if not isinstance(items, list):
        return 0
    max_idx = 0
    for i, item in enumerate(items, start=1):
        if isinstance(item, dict) and "index" in item:
            try:
                max_idx = max(max_idx, int(item["index"]))
            except (TypeError, ValueError):
                max_idx = max(max_idx, i)
        else:
            max_idx = max(max_idx, i)
    return max_idx


def _check_refs(label: str, refs: list[int], max_index: int) -> list[str]:
    errors: list[str] = []
    for ref in refs:
        if ref < 1 or (max_index > 0 and ref > max_index) or max_index == 0:
            errors.append(f"{label} 含越界引用 {ref}（有效范围 1..{max_index}）")
    return errors
