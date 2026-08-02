"""SignalFusion 单元测试。"""

from __future__ import annotations

import pytest

from service.dual_track.config import DualTrackConfig
from service.dual_track.models.report import CombinedSignal, ValueRating
from service.dual_track.signal_fusion import SignalFusion, derive_value_rating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange

_FUSION_EXPECTED = {
    ValueRating.UNDERVALUED: {
        BuySignal.STRONG_BUY: CombinedSignal.STRONG_BUY,
        BuySignal.BUY: CombinedSignal.BUY,
        BuySignal.HOLD: CombinedSignal.BUY,
        BuySignal.WAIT: CombinedSignal.WAIT,
        BuySignal.SELL: CombinedSignal.WAIT,
        BuySignal.STRONG_SELL: CombinedSignal.SELL,
    },
    ValueRating.FAIR: {
        BuySignal.STRONG_BUY: CombinedSignal.BUY,
        BuySignal.BUY: CombinedSignal.BUY,
        BuySignal.HOLD: CombinedSignal.HOLD,
        BuySignal.WAIT: CombinedSignal.WAIT,
        BuySignal.SELL: CombinedSignal.SELL,
        BuySignal.STRONG_SELL: CombinedSignal.STRONG_SELL,
    },
    ValueRating.OVERVALUED: {
        BuySignal.STRONG_BUY: CombinedSignal.HOLD,
        BuySignal.BUY: CombinedSignal.WAIT,
        BuySignal.HOLD: CombinedSignal.SELL,
        BuySignal.WAIT: CombinedSignal.SELL,
        BuySignal.SELL: CombinedSignal.STRONG_SELL,
        BuySignal.STRONG_SELL: CombinedSignal.STRONG_SELL,
    },
}


def _value_result(mos: float | None) -> ValueAnalysisResult:
    return ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=100.0,
        prototype="value_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=80, base=100, high=120),
        margin_of_safety=mos,
        price_percentile=50.0,
        assessment="合理",
        confidence="High",
    )


def _tech_result(buy_signal: BuySignal) -> TechAnalysisResult:
    return TechAnalysisResult(code="600519", buy_signal=buy_signal)


@pytest.mark.parametrize(
    "mos,expected",
    [
        (25.0, ValueRating.UNDERVALUED),
        (20.0, ValueRating.FAIR),
        (0.0, ValueRating.FAIR),
        (-10.0, ValueRating.FAIR),
        (-10.1, ValueRating.OVERVALUED),
        (-0.8, ValueRating.FAIR),
        (None, ValueRating.UNKNOWN),
    ],
)
def test_derive_value_rating(mos: float | None, expected: ValueRating):
    assert derive_value_rating(mos) == expected


@pytest.mark.parametrize("value_rating", list(ValueRating)[:3])
@pytest.mark.parametrize("buy_signal", list(BuySignal))
def test_fusion_matrix_all_combinations(value_rating: ValueRating, buy_signal: BuySignal):
    mos_map = {
        ValueRating.UNDERVALUED: 25.0,
        ValueRating.FAIR: 5.0,
        ValueRating.OVERVALUED: -20.0,
    }
    fusion = SignalFusion()
    combined, rating = fusion.fuse(
        _value_result(mos_map[value_rating]),
        _tech_result(buy_signal),
    )
    assert rating == value_rating
    assert combined == _FUSION_EXPECTED[value_rating][buy_signal]


def test_fusion_overvalued_strong_buy_downgraded_to_hold():
    fusion = SignalFusion()
    combined, _ = fusion.fuse(_value_result(-20.0), _tech_result(BuySignal.STRONG_BUY))
    assert combined == CombinedSignal.HOLD


def test_fusion_undervalued_strong_sell_becomes_sell():
    fusion = SignalFusion()
    combined, _ = fusion.fuse(_value_result(25.0), _tech_result(BuySignal.STRONG_SELL))
    assert combined == CombinedSignal.SELL


def test_fusion_value_only_none():
    fusion = SignalFusion()
    combined, rating = fusion.fuse(None, _tech_result(BuySignal.BUY))
    assert combined == CombinedSignal.BUY
    assert rating is None


def test_fusion_tech_only_none():
    fusion = SignalFusion()
    combined, rating = fusion.fuse(_value_result(25.0), None)
    assert combined == CombinedSignal.BUY
    assert rating == ValueRating.UNDERVALUED


def test_fusion_both_none():
    fusion = SignalFusion()
    combined, rating = fusion.fuse(None, None)
    assert combined == CombinedSignal.WAIT
    assert rating is None


def test_fusion_unknown_mos_uses_tech_signal():
    fusion = SignalFusion()
    combined, rating = fusion.fuse(
        _value_result(None), _tech_result(BuySignal.STRONG_BUY)
    )
    assert combined == CombinedSignal.STRONG_BUY
    assert rating == ValueRating.UNKNOWN


def test_fusion_tech_only_value_rating_mapping():
    fusion = SignalFusion()
    for mos, expected_signal in [
        (25.0, CombinedSignal.BUY),
        (5.0, CombinedSignal.HOLD),
        (-20.0, CombinedSignal.WAIT),
        (None, CombinedSignal.WAIT),
    ]:
        combined, _ = fusion.fuse(_value_result(mos), None)
        assert combined == expected_signal


def test_custom_mos_thresholds():
    config = DualTrackConfig(undervalued_mos_threshold=30.0, overvalued_mos_threshold=-5.0)
    assert derive_value_rating(25.0, config) == ValueRating.FAIR
    assert derive_value_rating(31.0, config) == ValueRating.UNDERVALUED
    assert derive_value_rating(-6.0, config) == ValueRating.OVERVALUED
