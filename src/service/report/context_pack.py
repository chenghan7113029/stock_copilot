"""DualTrackReport → narrate() evidence 打包（仅确定性字段）。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from service.dual_track.models.report import DualTrackReport


def _enum_value(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    return v


def build_dual_track_evidence(report: DualTrackReport) -> dict[str, Any]:
    """从 DualTrackReport 打包 narrate() 所需 evidence。

    不含 warnings；不对数值再加工。某一维度为 None 时跳过该分区。
    """
    evidence: dict[str, Any] = {
        "code": report.code,
    }

    value = report.value_result
    if value is not None:
        value_block: dict[str, Any] = {
            "assessment": value.assessment,
            "confidence": value.confidence,
            "prototype": value.prototype,
            "margin_of_safety": value.margin_of_safety,
            "price_percentile": value.price_percentile,
        }
        if value.fair_value_range is not None:
            r = value.fair_value_range
            value_block["fair_value_range"] = {
                "low": r.low,
                "base": r.base,
                "high": r.high,
            }
        evidence["value"] = value_block

    tech = report.tech_result
    if tech is not None:
        evidence["tech"] = {
            "trend_status": _enum_value(tech.trend_status),
            "signal_score": tech.signal_score,
            "buy_signal": _enum_value(tech.buy_signal),
            "signal_reasons": list(tech.signal_reasons),
            "risk_factors": list(tech.risk_factors),
        }

    evidence["fusion"] = {
        "combined_signal": _enum_value(report.combined_signal),
        "value_rating": _enum_value(report.value_rating)
        if report.value_rating is not None
        else None,
    }
    return evidence
