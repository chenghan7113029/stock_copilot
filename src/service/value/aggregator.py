"""多方法估值结果区间聚合。"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from service.value.valuation.base import ValuationRange, ValuationResult

SCORE_METHOD_KEYS = frozenset({"altman_z", "piotroski_f", "beneish_m", "value_trap", "sbc"})

PRIMARY_METHODS_BY_PROTOTYPE: dict[str, frozenset[str]] = {
    "value_growth": frozenset({"dcf", "pe_relative"}),
    "bank": frozenset({"pb_relative", "residual_income"}),
    "high_dividend": frozenset({"ddm", "two_stage_ddm"}),
}

_UNRELIABLE_WARNING = (
    "⚠ 核心估值方法均因数据不足未运行，当前区间参考意义有限"
)


@dataclass
class AggregateResult:
    fair_value_range: ValuationRange | None = None
    margin_of_safety: float | None = None
    price_percentile: float | None = None
    assessment: str = "数据不足"
    confidence: str = "Low"
    warnings: list[str] = field(default_factory=list)


class ValuationAggregator:
    """将多方法 ValuationResult 聚合为公允价区间与 MOS。"""

    def aggregate(
        self,
        results: dict[str, ValuationResult],
        current_price: float | None,
    ) -> AggregateResult:
        warnings: list[str] = []
        values: list[float] = []

        for key, result in results.items():
            if self._is_score_result(key, result):
                warnings.append(self._score_summary(key, result))
                continue
            if result.error is not None:
                continue
            if result.applicability == "Not Applicable":
                continue
            if result.fair_value <= 0:
                continue
            values.append(result.fair_value)

        if not values:
            return AggregateResult(assessment="数据不足", confidence="Low", warnings=warnings)

        filtered, outlier_warnings = self._iqr_filter(values)
        warnings.extend(outlier_warnings)

        low = _percentile(filtered, 25)
        base = statistics.median(filtered)
        high = _percentile(filtered, 75)

        if len(filtered) == 1:
            low = base = high = filtered[0]

        fair_value_range = ValuationRange(low=low, base=base, high=high)
        mos = None
        price_percentile = None
        assessment = "数据不足"

        if current_price is not None and base > 0:
            mos = ((base - current_price) / base) * 100
            assessment = _assessment_from_mos(mos)
            price_percentile = _price_percentile(current_price, low, high)

        confidence = _confidence(filtered)

        primary_methods = self._detect_primary_methods(results)
        if primary_methods and self._all_primary_na(results, primary_methods):
            confidence = "不可信"
            warnings.insert(0, _UNRELIABLE_WARNING)

        return AggregateResult(
            fair_value_range=fair_value_range,
            margin_of_safety=mos,
            price_percentile=price_percentile,
            assessment=assessment,
            confidence=confidence,
            warnings=warnings,
        )

    @staticmethod
    def _is_score_result(key: str, result: ValuationResult) -> bool:
        if key in SCORE_METHOD_KEYS:
            return True
        return result.details.get("output_type") == "score"

    @staticmethod
    def _score_summary(key: str, result: ValuationResult) -> str:
        method = result.method or key
        assessment = result.assessment
        details = result.details
        if key == "altman_z" and "z_score" in details:
            return f"{method}: Z={details['z_score']}, {assessment}"
        if key == "piotroski_f" and "f_score" in details:
            return f"{method}: F={details['f_score']}, {assessment}"
        if key == "beneish_m" and "m_score" in details:
            return f"{method}: M={details['m_score']}, {assessment}"
        if key == "value_trap" and "overall_risk" in details:
            return f"{method}: risk={details['overall_risk']}, {assessment}"
        if key == "sbc" and "dilution_rating" in details:
            return f"{method}: {details['dilution_rating']}, {assessment}"
        return f"{method}: {assessment}"

    @staticmethod
    def _iqr_filter(values: list[float]) -> tuple[list[float], list[str]]:
        if len(values) < 4:
            return list(values), []

        sorted_vals = sorted(values)
        q1 = _percentile(sorted_vals, 25)
        q3 = _percentile(sorted_vals, 75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = [v for v in sorted_vals if lower <= v <= upper]

        if len(filtered) < 2:
            return list(values), []

        removed = [v for v in sorted_vals if v not in filtered]
        warnings = []
        if removed:
            warnings.append(f"IQR 过滤剔除异常公允价: {removed}")
        return filtered, warnings

    @staticmethod
    def _detect_prototype(results: dict[str, ValuationResult]) -> str | None:
        keys = set(results.keys())
        if "dcf" in keys or "pe_relative" in keys:
            return "value_growth"
        if "pb_relative" in keys or "residual_income" in keys:
            return "bank"
        if "ddm" in keys or "two_stage_ddm" in keys:
            return "high_dividend"
        return None

    @classmethod
    def _detect_primary_methods(cls, results: dict[str, ValuationResult]) -> frozenset[str]:
        proto = cls._detect_prototype(results)
        if proto is None:
            return frozenset()
        return PRIMARY_METHODS_BY_PROTOTYPE.get(proto, frozenset())

    @staticmethod
    def _all_primary_na(
        results: dict[str, ValuationResult],
        primary_methods: frozenset[str],
    ) -> bool:
        if not primary_methods:
            return False
        for key in primary_methods:
            result = results.get(key)
            if result is None:
                continue
            if result.applicability != "Not Applicable" and result.fair_value > 0:
                return False
        return True


def _percentile(values: list[float], p: float) -> float:
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100
    f_idx = int(k)
    c_idx = min(f_idx + 1, len(sorted_vals) - 1)
    if f_idx == c_idx:
        return sorted_vals[f_idx]
    return sorted_vals[f_idx] + (k - f_idx) * (sorted_vals[c_idx] - sorted_vals[f_idx])


def _assessment_from_mos(mos: float) -> str:
    if mos > 20:
        return "低估"
    if mos > 5:
        return "合理偏低"
    if mos > -5:
        return "合理"
    if mos > -20:
        return "合理偏高"
    return "高估"


def _price_percentile(price: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    pct = (price - low) / (high - low) * 100
    return max(0.0, min(100.0, pct))


def _confidence(values: list[float]) -> str:
    n = len(values)
    if n >= 3:
        mean = statistics.mean(values)
        if mean > 0:
            cv = statistics.stdev(values) / mean
            if cv < 0.3:
                return "High"
    if n >= 2:
        return "Medium"
    return "Low"
