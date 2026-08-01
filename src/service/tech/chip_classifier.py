"""筹码集中度的确定性分类规则。"""

from __future__ import annotations

from service.tech.config import IndicatorParams
from service.tech.models.tech_result import ChipStatus


def classify_chip_status(
    concentration_90: float | None,
    params: IndicatorParams,
) -> ChipStatus | None:
    """按 90% 成本集中度分档；数值越小表示筹码越集中。"""
    if concentration_90 is None:
        return None
    if concentration_90 <= params.chip_concentration_strong:
        return ChipStatus.HIGHLY_CONCENTRATED
    if concentration_90 >= params.chip_concentration_weak:
        return ChipStatus.DISPERSED
    midpoint = (params.chip_concentration_strong + params.chip_concentration_weak) / 2
    if concentration_90 < midpoint:
        return ChipStatus.CONCENTRATED
    return ChipStatus.NORMAL
