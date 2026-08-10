"""价值面与技术面信号融合（确定性规则）。"""

from __future__ import annotations

from service.dual_track.config import DualTrackConfig
from service.dual_track.models.report import CombinedSignal, ValueRating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult
from service.value.models.analysis_result import ValueAnalysisResult

_FUSION_MATRIX: dict[ValueRating, dict[BuySignal, CombinedSignal]] = {
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

_VALUE_ONLY_SIGNAL: dict[ValueRating, CombinedSignal] = {
    ValueRating.UNDERVALUED: CombinedSignal.BUY,
    ValueRating.FAIR: CombinedSignal.HOLD,
    ValueRating.OVERVALUED: CombinedSignal.WAIT,
    ValueRating.UNKNOWN: CombinedSignal.WAIT,
}


def derive_value_rating(
    mos: float | None, config: DualTrackConfig | None = None
) -> ValueRating:
    config = config or DualTrackConfig()
    if mos is None:
        return ValueRating.UNKNOWN
    if mos > config.undervalued_mos_threshold:
        return ValueRating.UNDERVALUED
    if mos < config.overvalued_mos_threshold:
        return ValueRating.OVERVALUED
    return ValueRating.FAIR


def _buy_signal_to_combined(signal: BuySignal) -> CombinedSignal:
    return CombinedSignal[signal.name]


class SignalFusion:
    """价值面 × 技术面确定性融合。"""

    def __init__(self, config: DualTrackConfig | None = None) -> None:
        self._config = config or DualTrackConfig()

    def fuse(
        self,
        value_result: ValueAnalysisResult | None,
        tech_result: TechAnalysisResult | None,
    ) -> tuple[CombinedSignal, ValueRating | None]:
        if value_result is None and tech_result is None:
            return CombinedSignal.WAIT, None

        if value_result is None:
            assert tech_result is not None
            return _buy_signal_to_combined(tech_result.buy_signal), None

        if not value_result.methodology_applicable:
            value_rating = ValueRating.UNKNOWN
        else:
            value_rating = derive_value_rating(
                value_result.margin_of_safety, self._config
            )

        if tech_result is None:
            return _VALUE_ONLY_SIGNAL[value_rating], value_rating

        if value_rating == ValueRating.UNKNOWN:
            return _buy_signal_to_combined(tech_result.buy_signal), value_rating

        combined = _FUSION_MATRIX[value_rating][tech_result.buy_signal]
        return combined, value_rating
