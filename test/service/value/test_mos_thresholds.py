"""MOS 按原型阈值解析单元测试。"""

from __future__ import annotations

from service.value.mos_thresholds import (
    assessment_from_mos,
    get_assessment_thresholds,
    get_value_rating_thresholds,
)


def test_default_thresholds_by_prototype():
    bank = get_assessment_thresholds("bank")
    assert bank.undervalued == 12
    assert bank.mildly_overvalued == -12

    growth = get_assessment_thresholds("value_growth")
    assert growth.undervalued == 20
    assert growth.mildly_overvalued == -20


def test_unknown_prototype_fallbacks_to_value_growth():
    unknown = get_assessment_thresholds("unknown")
    growth = get_assessment_thresholds("value_growth")
    assert unknown == growth


def test_assessment_boundaries_with_default_thresholds():
    assert assessment_from_mos(15.0, "bank") == "低估"
    assert assessment_from_mos(15.0, "value_growth") == "合理偏低"
    assert assessment_from_mos(-25.0, "value_growth") == "高估"


def test_yaml_override_value_section():
    cfg = {
        "value": {
            "mos_thresholds_by_proto": {
                "bank": {
                    "undervalued": 10,
                    "mildly_undervalued": 2,
                    "fair_low": -2,
                    "mildly_overvalued": -10,
                    "overvalued": -15,
                }
            }
        }
    }
    bank_assess = get_assessment_thresholds("bank", cfg)
    bank_rating = get_value_rating_thresholds("bank", cfg)
    assert bank_assess.undervalued == 10
    assert bank_assess.mildly_undervalued == 2
    assert bank_rating.undervalued == 10
    assert bank_rating.overvalued == -15


def test_yaml_override_value_analysis_section_compat():
    cfg = {
        "value_analysis": {
            "mos_thresholds_by_proto": {
                "high_dividend": {
                    "undervalued": 11,
                    "mildly_undervalued": 4,
                    "fair_low": -4,
                    "mildly_overvalued": -11,
                }
            }
        }
    }
    thresholds = get_assessment_thresholds("high_dividend", cfg)
    assert thresholds.undervalued == 11
    assert thresholds.mildly_undervalued == 4

