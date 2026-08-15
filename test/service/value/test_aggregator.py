"""ValuationAggregator 单元测试。"""

from __future__ import annotations

from service.value.aggregator import ValuationAggregator
from service.value.valuation.base import ValuationResult


def _value_result(fair_value: float, **kwargs) -> ValuationResult:
    return ValuationResult(
        method=kwargs.pop("method", "Test"),
        fair_value=fair_value,
        current_price=kwargs.pop("current_price", 650.0),
        premium_discount=0,
        assessment="Fair",
        **kwargs,
    )


def _score_result(method: str, **details) -> ValuationResult:
    return ValuationResult(
        method=method,
        fair_value=650.0,
        current_price=650.0,
        premium_discount=0,
        assessment="Safe",
        details={"output_type": "score", **details},
    )


def test_score_methods_excluded_from_range():
    agg = ValuationAggregator()
    results = {
        "altman_z": _score_result("Altman Z-Score", z_score=3.5),
        "piotroski_f": _score_result("Piotroski F-Score", f_score=7),
        "dcf": _value_result(700.0, method="DCF"),
    }
    out = agg.aggregate(results, current_price=650.0)
    assert out.fair_value_range is not None
    assert out.fair_value_range.base == 700.0
    assert len(out.warnings) == 2


def test_all_unavailable_returns_insufficient_data():
    agg = ValuationAggregator()
    results = {
        "dcf": ValuationResult(
            method="DCF",
            fair_value=0,
            current_price=650,
            premium_discount=0,
            assessment="N/A",
            error="missing data",
            applicability="Not Applicable",
        ),
        "epv": ValuationResult(
            method="EPV",
            fair_value=0,
            current_price=650,
            premium_discount=0,
            assessment="N/A",
            applicability="Not Applicable",
        ),
    }
    out = agg.aggregate(results, current_price=650.0)
    assert out.fair_value_range is None
    assert out.margin_of_safety is None
    assert out.assessment == "数据不足"
    assert out.confidence == "Low"


def test_single_valid_value_degenerates_range():
    agg = ValuationAggregator()
    results = {"graham_number": _value_result(500.0, method="Graham Number")}
    out = agg.aggregate(results, current_price=450.0)
    assert out.fair_value_range.low == 500.0
    assert out.fair_value_range.base == 500.0
    assert out.fair_value_range.high == 500.0
    assert out.confidence == "Low"


def test_iqr_outlier_removed():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(500.0),
        "b": _value_result(520.0),
        "c": _value_result(540.0),
        "d": _value_result(3000.0),
    }
    out = agg.aggregate(results, current_price=510.0)
    assert out.fair_value_range.base == 520.0
    assert any("IQR" in w for w in out.warnings)


def test_iqr_skipped_when_fewer_than_four_values():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(500.0),
        "b": _value_result(3000.0),
    }
    out = agg.aggregate(results, current_price=2000.0)
    assert out.fair_value_range.base == 1750.0
    assert not any("IQR" in w for w in out.warnings)


def test_normal_aggregation_and_mos():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(600.0),
        "b": _value_result(700.0),
        "c": _value_result(800.0),
    }
    out = agg.aggregate(results, current_price=650.0)
    assert out.fair_value_range.base == 700.0
    assert out.fair_value_range.low == 650.0
    assert out.fair_value_range.high == 750.0
    assert abs(out.margin_of_safety - 7.142857) < 0.01
    assert out.assessment == "合理偏低"


def test_overvalued_assessment():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(600.0),
        "b": _value_result(700.0),
        "c": _value_result(800.0),
    }
    out = agg.aggregate(results, current_price=900.0)
    assert out.assessment == "高估"


def test_same_mos_differs_by_prototype_thresholds():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(600.0),
        "b": _value_result(700.0),
        "c": _value_result(800.0),
    }
    # base=700, current=595 => MOS=15%
    bank_out = agg.aggregate(results, current_price=595.0, prototype="bank")
    growth_out = agg.aggregate(results, current_price=595.0, prototype="value_growth")
    assert bank_out.assessment == "低估"
    assert growth_out.assessment == "合理偏低"


def test_confidence_high_with_three_low_dispersion():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(680.0),
        "b": _value_result(700.0),
        "c": _value_result(720.0),
    }
    out = agg.aggregate(results, current_price=700.0)
    assert out.confidence == "High"


def test_confidence_medium_with_two_values():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(600.0),
        "b": _value_result(900.0),
    }
    out = agg.aggregate(results, current_price=750.0)
    assert out.confidence == "Medium"


def test_all_primary_na_marks_unreliable():
    agg = ValuationAggregator()
    results = {
        "dcf": ValuationResult(
            method="DCF",
            fair_value=0,
            current_price=1168.0,
            premium_discount=0,
            assessment="N/A",
            error="missing fcf",
            applicability="Not Applicable",
        ),
        "pe_relative": ValuationResult(
            method="PE Relative",
            fair_value=0,
            current_price=1168.0,
            premium_discount=0,
            assessment="N/A - Insufficient historical PE data",
            error="historical_pe",
            applicability="Not Applicable",
        ),
        "owner_earnings": _value_result(157.0, method="Owner Earnings"),
        "graham_formula": _value_result(467.0, method="Graham Formula"),
    }
    out = agg.aggregate(results, current_price=1168.0)
    assert out.confidence == "不可信"
    assert out.warnings[0].startswith("⚠ 核心估值方法")


def test_value_trap_high_adds_alert_and_downgrades_confidence():
    agg = ValuationAggregator()
    results = {
        "a": _value_result(680.0),
        "b": _value_result(700.0),
        "c": _value_result(720.0),
        "value_trap": _score_result(
            "Value Trap Detector",
            overall_risk="High",
            financial_health="High",
            business_deterioration="Low",
        ),
    }

    out = agg.aggregate(results, current_price=700.0)

    assert out.value_trap_alert is not None
    assert "财务健康" in out.value_trap_alert
    assert out.confidence == "Medium"
    assert any("risk=High" in warning for warning in out.warnings)


def test_non_high_value_trap_does_not_change_confidence_or_add_alert():
    agg = ValuationAggregator()
    base_results = {
        "a": _value_result(680.0),
        "b": _value_result(700.0),
        "c": _value_result(720.0),
    }
    base = agg.aggregate(base_results, current_price=700.0)

    for risk in ("Medium", "Low", "Limited"):
        results = {
            **base_results,
            "value_trap": _score_result("Value Trap Detector", overall_risk=risk),
        }
        out = agg.aggregate(results, current_price=700.0)
        assert out.value_trap_alert is None
        assert out.confidence == base.confidence


def test_value_trap_high_preserves_unreliable_confidence():
    agg = ValuationAggregator()
    results = {
        "dcf": ValuationResult(
            method="DCF",
            fair_value=0,
            current_price=1168.0,
            premium_discount=0,
            assessment="N/A",
            error="missing fcf",
            applicability="Not Applicable",
        ),
        "pe_relative": ValuationResult(
            method="PE Relative",
            fair_value=0,
            current_price=1168.0,
            premium_discount=0,
            assessment="N/A",
            error="historical_pe",
            applicability="Not Applicable",
        ),
        "owner_earnings": _value_result(157.0, method="Owner Earnings"),
        "value_trap": _score_result(
            "Value Trap Detector",
            overall_risk="High",
            moat_erosion="High",
        ),
    }

    out = agg.aggregate(results, current_price=1168.0)

    assert out.value_trap_alert is not None
    assert out.confidence == "不可信"
