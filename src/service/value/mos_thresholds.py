"""按原型管理 MOS 评估/评级阈值。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssessmentThresholds:
    undervalued: float
    mildly_undervalued: float
    fair_low: float
    mildly_overvalued: float


@dataclass(frozen=True)
class ValueRatingThresholds:
    undervalued: float
    overvalued: float


_DEFAULT_ASSESSMENT_BY_PROTO: dict[str, AssessmentThresholds] = {
    "bank": AssessmentThresholds(12.0, 3.0, -3.0, -12.0),
    "high_dividend": AssessmentThresholds(12.0, 3.0, -3.0, -12.0),
    "value_growth": AssessmentThresholds(20.0, 5.0, -5.0, -20.0),
}

_DEFAULT_VALUE_RATING_BY_PROTO: dict[str, ValueRatingThresholds] = {
    "bank": ValueRatingThresholds(12.0, -12.0),
    "high_dividend": ValueRatingThresholds(12.0, -12.0),
    "value_growth": ValueRatingThresholds(20.0, -10.0),
}

_DEFAULT_FALLBACK_PROTO = "value_growth"


def _normalize_proto(prototype: str | None) -> str:
    proto = (prototype or "").strip()
    return proto if proto in _DEFAULT_ASSESSMENT_BY_PROTO else _DEFAULT_FALLBACK_PROTO


def _section_by_priority(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = config or {}
    return cfg.get("value") or cfg.get("value_analysis") or {}


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _custom_thresholds(config: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    section = _section_by_priority(config)
    raw = section.get("mos_thresholds_by_proto") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for proto, payload in raw.items():
        if isinstance(payload, dict):
            out[str(proto)] = payload
    return out


def get_assessment_thresholds(
    prototype: str | None,
    config: dict[str, Any] | None = None,
) -> AssessmentThresholds:
    proto = _normalize_proto(prototype)
    default = _DEFAULT_ASSESSMENT_BY_PROTO[proto]
    payload = _custom_thresholds(config).get(proto) or {}
    return AssessmentThresholds(
        undervalued=_coerce_float(payload.get("undervalued"), default.undervalued),
        mildly_undervalued=_coerce_float(
            payload.get("mildly_undervalued"), default.mildly_undervalued
        ),
        fair_low=_coerce_float(payload.get("fair_low"), default.fair_low),
        mildly_overvalued=_coerce_float(
            payload.get("mildly_overvalued"), default.mildly_overvalued
        ),
    )


def assessment_from_mos(
    mos: float,
    prototype: str | None,
    config: dict[str, Any] | None = None,
) -> str:
    t = get_assessment_thresholds(prototype, config)
    if mos > t.undervalued:
        return "低估"
    if mos > t.mildly_undervalued:
        return "合理偏低"
    if mos > t.fair_low:
        return "合理"
    if mos > t.mildly_overvalued:
        return "合理偏高"
    return "高估"


def get_value_rating_thresholds(
    prototype: str | None,
    config: dict[str, Any] | None = None,
) -> ValueRatingThresholds:
    proto = _normalize_proto(prototype)
    default = _DEFAULT_VALUE_RATING_BY_PROTO[proto]
    payload = _custom_thresholds(config).get(proto) or {}
    return ValueRatingThresholds(
        undervalued=_coerce_float(payload.get("undervalued"), default.undervalued),
        overvalued=_coerce_float(payload.get("overvalued"), default.overvalued),
    )

