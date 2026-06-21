"""银行专用估值单元测试。"""

from __future__ import annotations

from service.value.valuation.bank import PBValuation, ResidualIncome

from .conftest import assert_within_pct, make_stock


def test_pb_valuation_vs_ref():
    stock = make_stock(bvps=8.0, roe=12.0, current_price=5.0)
    result = PBValuation(cost_of_equity=10.0, sustainable_growth=2.0).calculate(stock)
    assert_within_pct(result.fair_value, 10.0)


def test_pb_valuation_roe_below_coe_not_applicable():
    stock = make_stock(bvps=8.0, roe=8.0, current_price=5.0)
    result = PBValuation(cost_of_equity=10.0, sustainable_growth=2.0).calculate(stock)
    assert result.applicability == "Not Applicable"
    assert result.error is not None
    assert "ROE" in result.error


def test_pb_valuation_bvps_none():
    stock = make_stock(bvps=None, roe=12.0, current_price=5.0)
    result = PBValuation().calculate(stock)
    assert "bvps" in result.missing_fields


def test_residual_income_roe15_vs_ref():
    stock = make_stock(bvps=10.0, roe=15.0, current_price=12.0)
    result = ResidualIncome(cost_of_equity=10.0).calculate(stock)
    assert result.fair_value > 10.0
    assert_within_pct(result.fair_value, 13.87)


def test_residual_income_roe6_discount():
    stock = make_stock(bvps=10.0, roe=6.0, current_price=8.0)
    result = ResidualIncome(cost_of_equity=10.0).calculate(stock)
    assert result.fair_value < 10.0
    assert_within_pct(result.fair_value, 7.31)


def test_residual_income_roe_none():
    stock = make_stock(bvps=10.0, roe=None, current_price=12.0)
    result = ResidualIncome().calculate(stock)
    assert "roe" in result.missing_fields
