"""Owner Earnings 单元测试。"""

from __future__ import annotations

from service.value.valuation.quality import OwnerEarnings

from .conftest import assert_within_pct, make_stock


def test_owner_earnings_vs_ref():
    stock = make_stock(
        net_income=50e9,
        depreciation=5e9,
        capex=8e9,
        net_working_capital=2e9,
        revenue=100e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        growth_rate=8.0,
    )
    result = OwnerEarnings(cost_of_capital=10.0).calculate(stock)
    assert_within_pct(result.fair_value, 1249.52)


def test_owner_earnings_negative_oe_error():
    stock = make_stock(
        net_income=1e9,
        depreciation=0.0,
        capex=50e9,
        net_working_capital=0.0,
        revenue=100e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = OwnerEarnings(cost_of_capital=10.0).calculate(stock)
    assert result.error is not None
    assert result.fair_value == 0


def test_owner_earnings_net_income_none():
    stock = make_stock(
        net_income=None,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = OwnerEarnings().calculate(stock)
    assert "net_income" in result.missing_fields
