"""DCF 单元测试。"""

from __future__ import annotations

from service.value.valuation.dcf import DCF, ReverseDCF

from .conftest import assert_within_pct, make_stock


def test_dcf_vs_ref():
    stock = make_stock(
        fcf=60e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        net_debt=0.0,
    )
    result = DCF(
        growth_1_5=5.0,
        growth_6_10=3.0,
        terminal_growth=2.0,
        discount_rate=10.0,
    ).calculate(stock)
    assert_within_pct(result.fair_value, 709.44)


def test_dcf_fcf_none_missing():
    stock = make_stock(
        fcf=None,
        capex=None,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = DCF().calculate(stock)
    assert "fcf" in result.missing_fields
    assert result.error is not None


def test_dcf_net_debt_none_treated_as_zero():
    stock = make_stock(
        fcf=60e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        net_debt=None,
    )
    result = DCF(
        growth_1_5=5.0,
        growth_6_10=3.0,
        terminal_growth=2.0,
        discount_rate=10.0,
    ).calculate(stock)
    assert_within_pct(result.fair_value, 709.44)


def test_reverse_dcf_implied_growth():
    stock = make_stock(
        fcf=60e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        net_debt=0.0,
    )
    result = ReverseDCF().calculate(stock)
    assert_within_pct(result.details["implied_growth_rate"], 22.0)


def test_reverse_dcf_no_solution_negative_fcf():
    stock = make_stock(
        fcf=-10e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = ReverseDCF().calculate(stock)
    assert result.error is not None
