"""成长估值方法单元测试。"""

from __future__ import annotations

from service.value.valuation.growth import EVEBITDA, GARP, PEG

from .conftest import assert_within_pct, make_stock


def test_peg_vs_ref():
    stock = make_stock(
        eps=50.0,
        growth_rate=15.0,
        current_price=1800.0,
        shares_outstanding=1.26e9,
    )
    result = PEG().calculate(stock)
    assert_within_pct(result.fair_value, 750.0)


def test_peg_growth_zero_error():
    stock = make_stock(
        eps=50.0,
        growth_rate=0.0,
        current_price=1800.0,
        shares_outstanding=1.26e9,
    )
    result = PEG().calculate(stock)
    assert result.error is not None


def test_garp_vs_ref():
    stock = make_stock(
        eps=50.0,
        growth_rate=15.0,
        current_price=1800.0,
        shares_outstanding=1.26e9,
    )
    result = GARP().calculate(stock)
    assert_within_pct(result.fair_value, 1027.17)


def test_ev_ebitda_vs_ref():
    stock = make_stock(
        ebitda=80e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        net_debt=0.0,
    )
    result = EVEBITDA(fair_multiple=12.0).calculate(stock)
    assert_within_pct(result.fair_value, 761.9)
