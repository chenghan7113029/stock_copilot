"""EvidenceBucketer 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from service.dual_track.evidence_bucketer import EvidenceBucketer, strip_numeric_assertions
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange, ValuationResult


def _value_result(
    *,
    assessment: str = "低估",
    prototype: str = "value_growth",
    method_results: dict | None = None,
    warnings: list[str] | None = None,
) -> ValueAnalysisResult:
    return ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype=prototype,
        method_keys_used=list((method_results or {}).keys()),
        fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
        margin_of_safety=25.0,
        price_percentile=0.3,
        assessment=assessment,
        confidence="High",
        method_results=method_results or {},
        warnings=warnings or [],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _tech_result(
    *,
    signal_reasons: list[str] | None = None,
    risk_factors: list[str] | None = None,
    trend: TrendStatus = TrendStatus.STRONG_BULL,
) -> TechAnalysisResult:
    return TechAnalysisResult(
        code="600519",
        trend_status=trend,
        signal_score=80,
        buy_signal=BuySignal.STRONG_BUY,
        signal_reasons=signal_reasons or [],
        risk_factors=risk_factors or [],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _report(
    value=None,
    tech=None,
    value_rating: ValueRating | None = ValueRating.UNDERVALUED,
) -> DualTrackReport:
    return DualTrackReport(
        code="600519",
        value_result=value,
        tech_result=tech,
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=value_rating,
    )


def test_undervalued_and_tech_signal_go_to_bull():
    value = _value_result(
        method_results={
            "dcf": ValuationResult(
                method="dcf",
                fair_value=2000,
                current_price=1500,
                premium_discount=-0.25,
                assessment="Undervalued",
            )
        }
    )
    tech = _tech_result(signal_reasons=["MA5 上穿 MA20"])
    buckets = EvidenceBucketer().bucket(_report(value, tech))

    assert any("低估" in e for e in buckets.bull_evidence)
    assert any("MA5 上穿 MA20" in e for e in buckets.bull_evidence)
    assert any("Undervalued" in e for e in buckets.bull_evidence)


def test_value_trap_high_goes_to_bear():
    value = _value_result(
        assessment="合理",
        method_results={
            "value_trap": ValuationResult(
                method="value_trap",
                fair_value=0,
                current_price=1500,
                premium_discount=0,
                assessment="High risk",
                details={"overall_risk": "High"},
            )
        },
    )
    buckets = EvidenceBucketer().bucket(
        _report(value, _tech_result(), value_rating=ValueRating.FAIR)
    )

    assert any("value_trap" in e and "High" in e for e in buckets.bear_evidence)


def test_risk_factors_go_to_bear():
    tech = _tech_result(risk_factors=["RSI 超买"])
    buckets = EvidenceBucketer().bucket(
        _report(_value_result(), tech, value_rating=ValueRating.UNDERVALUED)
    )

    assert any("RSI 超买" in e for e in buckets.bear_evidence)


def test_strong_bull_triggers_bear_fallback():
    """强多头、无空方证据时触发兜底，bear_evidence 非空。"""
    value = _value_result(
        method_results={
            "dcf": ValuationResult(
                method="dcf",
                fair_value=2000,
                current_price=1500,
                premium_discount=-0.25,
                assessment="Undervalued",
            )
        }
    )
    tech = _tech_result(signal_reasons=["均线多头排列"], risk_factors=[], trend=TrendStatus.STRONG_BULL)
    buckets = EvidenceBucketer().bucket(_report(value, tech))

    assert len(buckets.bear_evidence) >= 2
    assert any("假设脆弱性" in e for e in buckets.bear_evidence)


def test_fallback_text_has_no_numeric_assertions():
    buckets = EvidenceBucketer().bucket(
        _report(
            _value_result(prototype="bank"),
            _tech_result(signal_reasons=["多头"], risk_factors=[]),
        )
    )
    fallback_items = [e for e in buckets.bear_evidence if "假设脆弱性" in e]
    assert fallback_items
    for item in fallback_items:
        assert strip_numeric_assertions(item) or "假设脆弱性" in item
        # 不允许形如「增长 20%」的个股数字断言；方法论文案中的编号/阈值除外用启发式放宽
        assert "预测" not in item
        assert "20%" not in item


def test_warning_with_risk_goes_to_bear():
    value = _value_result(warnings=["关键字段缺失导致结果不可信"])
    buckets = EvidenceBucketer().bucket(
        _report(value, _tech_result(risk_factors=["RSI 超买"]), value_rating=ValueRating.FAIR)
    )
    assert any("不可信" in e for e in buckets.bear_evidence)


def test_honesty_degrade_skips_method_assessment_keyword_bucketing():
    value = _value_result(
        assessment="方法暂不适用",
        method_results={
            "epv": ValuationResult(
                method="epv",
                fair_value=2000,
                current_price=1500,
                premium_discount=-0.25,
                assessment="Undervalued",
            )
        },
    )
    value.methodology_applicable = False
    buckets = EvidenceBucketer().bucket(
        _report(value, None, value_rating=ValueRating.UNKNOWN)
    )
    assert not any("Undervalued" in e for e in buckets.bull_evidence)
    assert not any("[价值评级] 低估" in e for e in buckets.bull_evidence)


def test_numbered_evidence_indices_stable_across_two_buckets():
    report = _report(
        _value_result(
            method_results={
                "dcf": ValuationResult(
                    method="dcf",
                    fair_value=2000,
                    current_price=1500,
                    premium_discount=-0.25,
                    assessment="Undervalued",
                )
            }
        ),
        _tech_result(signal_reasons=["MA5 上穿 MA20"], risk_factors=["RSI 超买"]),
    )
    bucketer = EvidenceBucketer()
    first = bucketer.bucket(report).numbered()
    second = bucketer.bucket(report).numbered()
    assert first == second
    assert first["bull_evidence"][0]["index"] == 1
    assert "text" in first["bull_evidence"][0]
    assert first["bear_evidence"][0]["index"] == 1

