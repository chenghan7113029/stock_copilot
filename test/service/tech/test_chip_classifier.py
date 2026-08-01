"""筹码集中度分类规则测试。"""

from __future__ import annotations

import pytest

from service.tech.chip_classifier import classify_chip_status
from service.tech.config import IndicatorParams
from service.tech.models.tech_result import ChipStatus


@pytest.mark.parametrize(
    ("concentration", "expected"),
    [
        (10.0, ChipStatus.HIGHLY_CONCENTRATED),
        (10.1, ChipStatus.CONCENTRATED),
        (29.9, ChipStatus.NORMAL),
        (30.0, ChipStatus.DISPERSED),
    ],
)
def test_classify_chip_status_boundaries(concentration: float, expected: ChipStatus) -> None:
    assert classify_chip_status(concentration, IndicatorParams()) is expected


def test_classify_chip_status_returns_none_when_concentration_missing() -> None:
    assert classify_chip_status(None, IndicatorParams()) is None
