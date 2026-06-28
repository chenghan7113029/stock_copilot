"""技术面综合评分引擎。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from service.tech.calculator import TechIndicators, WeeklyIndicators
from service.tech.config import ScoringParams
from service.tech.models.tech_result import (
    BuySignal,
    KDJStatus,
    MACDStatus,
    RSIStatus,
    TrendStatus,
    VolumeStatus,
    WeeklyTrendStatus,
)


@dataclass
class TechSignal:
    signal_score: int = 0
    buy_signal: BuySignal = BuySignal.WAIT
    signal_reasons: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)


class ScoringEngine(Protocol):
    def score(
        self,
        indicators: TechIndicators,
        params: ScoringParams,
        weekly_indicators: WeeklyIndicators | None = None,
    ) -> TechSignal: ...


class BullTrendScorer:
    """严进多头趋势评分风格。"""

    def score(
        self,
        indicators: TechIndicators,
        params: ScoringParams,
        weekly_indicators: WeeklyIndicators | None = None,
    ) -> TechSignal:
        score = 0
        reasons: list[str] = []
        risks: list[str] = []

        trend_scores = {
            TrendStatus.STRONG_BULL: params.trend_weight,
            TrendStatus.BULL: int(params.trend_weight * 26 / 30),
            TrendStatus.WEAK_BULL: int(params.trend_weight * 18 / 30),
            TrendStatus.CONSOLIDATION: int(params.trend_weight * 12 / 30),
            TrendStatus.WEAK_BEAR: int(params.trend_weight * 8 / 30),
            TrendStatus.BEAR: int(params.trend_weight * 4 / 30),
            TrendStatus.STRONG_BEAR: 0,
        }
        score += trend_scores.get(indicators.trend_status, int(params.trend_weight * 12 / 30))

        if indicators.trend_status in (TrendStatus.STRONG_BULL, TrendStatus.BULL):
            reasons.append(f"✅ {indicators.trend_status.value}，顺势做多")
        elif indicators.trend_status in (TrendStatus.BEAR, TrendStatus.STRONG_BEAR):
            risks.append(f"⚠️ {indicators.trend_status.value}，不宜做多")

        score += self._score_bias(indicators, params, reasons, risks)
        score += self._score_volume(indicators, params, reasons, risks)
        score += self._score_support(indicators, params, reasons)
        score += self._score_macd(indicators, params, reasons, risks)
        score += self._score_momentum(indicators, params, reasons, risks)

        if (
            params.kdj_weight > 0
            and indicators.trend_status == TrendStatus.STRONG_BULL
            and indicators.trend_strength >= 90
            and score < params.hold_threshold
        ):
            risks.append("趋势强劲但其他维度信号疲弱，建议人工复核量价背离情况")

        if params.kdj_weight > 0 and (indicators.kdj_j > 100 or indicators.kdj_j < 0):
            risks.append(f"KDJ J 值超界：{indicators.kdj_j:.1f}")

        buy_signal = self._resolve_buy_signal(score, indicators.trend_status, params)
        buy_signal = self._apply_weekly_filter(
            buy_signal, weekly_indicators, params, risks
        )

        return TechSignal(
            signal_score=score,
            buy_signal=buy_signal,
            signal_reasons=reasons,
            risk_factors=risks,
        )

    @staticmethod
    def _score_bias(
        indicators: TechIndicators,
        params: ScoringParams,
        reasons: list[str],
        risks: list[str],
    ) -> int:
        bias = indicators.bias_ma5
        base_threshold = params.bias_threshold
        is_strong_trend = (
            indicators.trend_status == TrendStatus.STRONG_BULL
            and indicators.trend_strength >= 70
        )
        effective_threshold = (
            base_threshold * params.strong_trend_bias_multiplier
            if is_strong_trend
            else base_threshold
        )

        if bias < 0:
            if bias > -3:
                reasons.append(f"✅ 价格略低于MA5({bias:.1f}%)，回踩买点")
                return params.bias_weight
            if bias > -5:
                reasons.append(f"✅ 价格回踩MA5({bias:.1f}%)，观察支撑")
                return int(params.bias_weight * 16 / 20)
            risks.append(f"⚠️ 乖离率过大({bias:.1f}%)，可能破位")
            return int(params.bias_weight * 8 / 20)
        if bias < 2:
            reasons.append(f"✅ 价格贴近MA5({bias:.1f}%)，介入好时机")
            return int(params.bias_weight * 18 / 20)
        if bias < base_threshold:
            reasons.append(f"⚡ 价格略高于MA5({bias:.1f}%)，可小仓介入")
            return int(params.bias_weight * 14 / 20)
        if bias > effective_threshold:
            risks.append(
                f"❌ 乖离率过高({bias:.1f}%>{effective_threshold:.1f}%)，严禁追高！"
            )
            return int(params.bias_weight * 4 / 20)
        if bias > base_threshold and is_strong_trend:
            reasons.append(f"⚡ 强势趋势中乖离率偏高({bias:.1f}%)，可轻仓追踪")
            return int(params.bias_weight * 10 / 20)
        risks.append(f"❌ 乖离率过高({bias:.1f}%>{base_threshold:.1f}%)，严禁追高！")
        return int(params.bias_weight * 4 / 20)

    @staticmethod
    def _score_volume(
        indicators: TechIndicators,
        params: ScoringParams,
        reasons: list[str],
        risks: list[str],
    ) -> int:
        volume_scores = {
            VolumeStatus.SHRINK_VOLUME_DOWN: params.volume_weight,
            VolumeStatus.HEAVY_VOLUME_UP: int(params.volume_weight * 12 / 15),
            VolumeStatus.NORMAL: int(params.volume_weight * 10 / 15),
            VolumeStatus.SHRINK_VOLUME_UP: int(params.volume_weight * 6 / 15),
            VolumeStatus.HEAVY_VOLUME_DOWN: 0,
        }
        vol_score = volume_scores.get(
            indicators.volume_status, int(params.volume_weight * 8 / 15)
        )
        if indicators.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("✅ 缩量回调，主力洗盘")
        elif indicators.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("⚠️ 放量下跌，注意风险")
        return vol_score

    @staticmethod
    def _score_support(
        indicators: TechIndicators, params: ScoringParams, reasons: list[str]
    ) -> int:
        score = 0
        half = params.support_weight // 2
        if indicators.support_ma5:
            score += half
            reasons.append("✅ MA5支撑有效")
        if indicators.support_ma10:
            score += half
            reasons.append("✅ MA10支撑有效")
        return score

    @staticmethod
    def _score_macd(
        indicators: TechIndicators,
        params: ScoringParams,
        reasons: list[str],
        risks: list[str],
    ) -> int:
        macd_scores = {
            MACDStatus.GOLDEN_CROSS_ZERO: params.macd_weight,
            MACDStatus.GOLDEN_CROSS: int(params.macd_weight * 12 / 15),
            MACDStatus.CROSSING_UP: int(params.macd_weight * 10 / 15),
            MACDStatus.BULLISH: int(params.macd_weight * 8 / 15),
            MACDStatus.BEARISH: int(params.macd_weight * 2 / 15),
            MACDStatus.CROSSING_DOWN: 0,
            MACDStatus.DEATH_CROSS: 0,
        }
        macd_score = macd_scores.get(indicators.macd_status, int(params.macd_weight * 5 / 15))
        if indicators.macd_status in (MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS):
            reasons.append(f"✅ {indicators.macd_signal}")
        elif indicators.macd_status in (MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN):
            risks.append(f"⚠️ {indicators.macd_signal}")
        else:
            reasons.append(indicators.macd_signal)
        return macd_score

    @staticmethod
    def _score_momentum(
        indicators: TechIndicators,
        params: ScoringParams,
        reasons: list[str],
        risks: list[str],
    ) -> int:
        rsi_scores = {
            RSIStatus.OVERSOLD: params.rsi_weight,
            RSIStatus.STRONG_BUY: int(params.rsi_weight * 5 / 6),
            RSIStatus.NEUTRAL: int(params.rsi_weight * 3 / 6),
            RSIStatus.WEAK: int(params.rsi_weight * 2 / 6),
            RSIStatus.OVERBOUGHT: 0,
        }
        kdj_scores = {
            KDJStatus.OVERSOLD: params.kdj_weight,
            KDJStatus.GOLDEN_CROSS: int(params.kdj_weight * 3 / 4),
            KDJStatus.NEUTRAL: int(params.kdj_weight * 2 / 4),
            KDJStatus.DEATH_CROSS: int(params.kdj_weight * 1 / 4),
            KDJStatus.OVERBOUGHT: 0,
        }
        rsi_score = rsi_scores.get(indicators.rsi_status, int(params.rsi_weight * 3 / 6))
        kdj_score = kdj_scores.get(indicators.kdj_status, int(params.kdj_weight * 2 / 4))

        if indicators.rsi_status in (RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY):
            reasons.append(f"✅ {indicators.rsi_signal}")
        elif indicators.rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"⚠️ {indicators.rsi_signal}")
        else:
            reasons.append(indicators.rsi_signal)

        if indicators.kdj_status in (KDJStatus.OVERSOLD, KDJStatus.GOLDEN_CROSS):
            reasons.append(f"✅ {indicators.kdj_signal}")
        elif indicators.kdj_status == KDJStatus.OVERBOUGHT:
            risks.append(f"⚠️ {indicators.kdj_signal}")
        elif params.kdj_weight > 0:
            reasons.append(indicators.kdj_signal)

        return rsi_score + kdj_score

    @staticmethod
    def _resolve_buy_signal(
        score: int, trend: TrendStatus, params: ScoringParams
    ) -> BuySignal:
        if trend in (TrendStatus.BEAR, TrendStatus.STRONG_BEAR):
            return BuySignal.STRONG_SELL
        if score >= params.strong_buy_threshold and trend in (
            TrendStatus.STRONG_BULL,
            TrendStatus.BULL,
        ):
            return BuySignal.STRONG_BUY
        if score >= params.buy_threshold and trend in (
            TrendStatus.STRONG_BULL,
            TrendStatus.BULL,
            TrendStatus.WEAK_BULL,
        ):
            return BuySignal.BUY
        if score >= params.hold_threshold:
            return BuySignal.HOLD
        if score >= params.wait_threshold:
            return BuySignal.WAIT
        if trend in (TrendStatus.BEAR, TrendStatus.STRONG_BEAR):
            return BuySignal.STRONG_SELL
        return BuySignal.SELL

    @staticmethod
    def _apply_weekly_filter(
        buy_signal: BuySignal,
        weekly_indicators: WeeklyIndicators | None,
        params: ScoringParams,
        risks: list[str],
    ) -> BuySignal:
        if not params.weekly_filter_enabled or weekly_indicators is None:
            return buy_signal

        if weekly_indicators.weekly_trend_status not in (
            WeeklyTrendStatus.BEAR,
            WeeklyTrendStatus.STRONG_BEAR,
        ):
            return buy_signal

        downgrade_map = {
            BuySignal.STRONG_BUY: BuySignal.BUY,
            BuySignal.BUY: BuySignal.WAIT,
            BuySignal.HOLD: BuySignal.WAIT,
        }
        if buy_signal in downgrade_map:
            risks.append("⚠️ 周线空头，日线买点风险较高")
            return downgrade_map[buy_signal]
        return buy_signal


class LegacyRefScorer(BullTrendScorer):
    """与 ref/daily_stock_analysis StockTrendAnalyzer 评分口径一致（RSI 动量 10 分，无 KDJ）。"""

    def score(
        self,
        indicators: TechIndicators,
        params: ScoringParams | None = None,
        weekly_indicators: WeeklyIndicators | None = None,
    ) -> TechSignal:
        del params
        legacy = ScoringParams(
            trend_weight=30,
            bias_weight=20,
            volume_weight=15,
            support_weight=10,
            macd_weight=15,
            rsi_weight=10,
            kdj_weight=0,
            bias_threshold=5.0,
            strong_trend_bias_multiplier=1.5,
            strong_buy_threshold=75,
            buy_threshold=60,
            hold_threshold=45,
            wait_threshold=30,
        )
        return super().score(indicators, legacy, weekly_indicators)
