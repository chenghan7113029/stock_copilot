"""股息模型单元测试。"""

from __future__ import annotations

from service.value.valuation.ddm import DDM, TwoStageDDM

from .conftest import assert_within_pct, make_stock


def test_ddm_vs_ref():
    stock = make_stock(
        dividend_per_share=1.2,
        dividend_growth_rate=4.0,
        current_price=15.0,
    )
    result = DDM(required_return=10.0).calculate(stock)
    assert_within_pct(result.fair_value, 20.8)


def test_ddm_g_ge_r_error():
    stock = make_stock(
        dividend_per_share=1.2,
        dividend_growth_rate=12.0,
        current_price=15.0,
    )
    result = DDM(required_return=10.0).calculate(stock)
    assert result.error is not None
    assert result.fair_value == 0


def test_ddm_dividend_none():
    stock = make_stock(
        dividend_per_share=None,
        dividend_growth_rate=4.0,
        current_price=15.0,
    )
    result = DDM(required_return=10.0).calculate(stock)
    assert "dividend_per_share" in result.missing_fields


def test_two_stage_ddm_vs_ref():
    stock = make_stock(
        dividend_per_share=0.8,
        current_price=20.0,
    )
    result = TwoStageDDM(
        growth_stage1=6.0,
        stage1_years=5,
        growth_stage2=3.0,
        required_return=9.0,
    ).calculate(stock)
    assert_within_pct(result.fair_value, 15.63)


def test_two_stage_ddm_g2_ge_r_error():
    stock = make_stock(
        dividend_per_share=0.8,
        current_price=20.0,
    )
    result = TwoStageDDM(
        growth_stage1=6.0,
        growth_stage2=10.0,
        required_return=9.0,
    ).calculate(stock)
    assert result.error is not None
    assert result.fair_value == 0
