"""相对估值与 Magic Formula 单元测试。"""

from __future__ import annotations

from service.value.valuation.magic_formula import MagicFormula
from service.value.valuation.relative import PBRelativeValuation, PERelativeValuation

from .conftest import assert_within_pct, make_stock

HISTORICAL_PE = [18.5, 20.1, 15.3, 22.0, 16.8]
HISTORICAL_PB = [3.2, 3.5, 2.8, 3.9, 3.1]


def test_magic_formula_vs_ref():
    stock = make_stock(
        ebit=61.74e9,
        net_fixed_assets=100e9,
        net_working_capital=20e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        net_debt=0.0,
    )
    result = MagicFormula().calculate(stock)
    assert_within_pct(result.fair_value, 490.0)


def test_pe_relative_with_historical_fixture():
    stock = make_stock(
        eps=50.0,
        current_price=1800.0,
        shares_outstanding=1.26e9,
        historical_pe=HISTORICAL_PE,
    )
    result = PERelativeValuation().calculate(stock)
    expected = 50.0 * (sum(HISTORICAL_PE) / len(HISTORICAL_PE))
    assert_within_pct(result.fair_value, expected)
    assert result.applicability == "Applicable"


def test_pe_relative_none_not_applicable():
    stock = make_stock(
        eps=50.0,
        current_price=1800.0,
        historical_pe=None,
    )
    result = PERelativeValuation().calculate(stock)
    assert result.applicability == "Not Applicable"


def test_pe_relative_short_history_not_applicable():
    stock = make_stock(
        eps=50.0,
        current_price=1800.0,
        historical_pe=[18.0, 20.0],
    )
    result = PERelativeValuation().calculate(stock)
    assert result.applicability == "Not Applicable"


def test_pb_relative_with_historical_fixture():
    stock = make_stock(
        bvps=500.0,
        current_price=1800.0,
        shares_outstanding=1.26e9,
        historical_pb=HISTORICAL_PB,
    )
    result = PBRelativeValuation().calculate(stock)
    expected = 500.0 * (sum(HISTORICAL_PB) / len(HISTORICAL_PB))
    assert_within_pct(result.fair_value, expected)
    assert result.applicability == "Applicable"


def test_pb_relative_none_not_applicable():
    stock = make_stock(
        bvps=500.0,
        current_price=1800.0,
        historical_pb=None,
    )
    result = PBRelativeValuation().calculate(stock)
    assert result.applicability == "Not Applicable"
