"""EPV 单元测试。"""

from __future__ import annotations

from service.value.valuation.epv import EPV

from .conftest import assert_within_pct, make_stock


def test_epv_vs_ref():
    stock = make_stock(
        revenue=100e9,
        operating_margin=35.0,
        tax_rate=25.0,
        net_debt=0.0,
        shares_outstanding=1.26e9,
        depreciation=0.0,
        capex=0.0,
        current_price=1800.0,
    )
    result = EPV(cost_of_capital=10.0).calculate(stock)
    assert_within_pct(result.fair_value, 208.33)


def test_epv_operating_margin_derived_from_ebit():
    stock = make_stock(
        revenue=100e9,
        operating_margin=None,
        ebit=35e9,
        tax_rate=25.0,
        net_debt=0.0,
        shares_outstanding=1.26e9,
        depreciation=0.0,
        capex=0.0,
        current_price=1800.0,
    )
    result = EPV(cost_of_capital=10.0).calculate(stock)
    assert result.fair_value > 0
    assert any("derived" in note.lower() for note in result.analysis)


def test_epv_all_profit_fields_missing():
    stock = make_stock(
        revenue=None,
        operating_margin=None,
        ebit=None,
        tax_rate=25.0,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = EPV(cost_of_capital=10.0).calculate(stock)
    assert "revenue" in result.missing_fields or result.error is not None


def test_epv_net_debt_exceeds_value_limited():
    stock = make_stock(
        revenue=100e9,
        operating_margin=35.0,
        tax_rate=25.0,
        net_debt=500e9,
        shares_outstanding=1.26e9,
        depreciation=0.0,
        capex=0.0,
        current_price=1800.0,
    )
    result = EPV(cost_of_capital=10.0).calculate(stock)
    assert result.fair_value < 0
    assert result.applicability == "Limited"
