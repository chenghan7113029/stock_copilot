"""Graham 体系单元测试。"""

from __future__ import annotations

from service.value.valuation.graham import NCAV, GrahamFormula, GrahamNumber

from .conftest import assert_within_pct, make_stock


def test_graham_number_vs_ref():
    stock = make_stock(eps=5.0, bvps=30.0, current_price=50.0)
    result = GrahamNumber().calculate(stock)
    assert_within_pct(result.fair_value, 58.09)


def test_graham_number_bvps_below_threshold():
    stock = make_stock(eps=5.0, bvps=2.0, current_price=50.0)
    result = GrahamNumber().calculate(stock)
    assert result.applicability == "Not Applicable"
    assert result.error is not None
    assert "BVPS" in result.error


def test_graham_number_eps_none():
    stock = make_stock(eps=None, bvps=30.0, current_price=50.0)
    result = GrahamNumber().calculate(stock)
    assert "eps" in result.missing_fields


def test_graham_formula_vs_ref():
    stock = make_stock(
        eps=4.0,
        growth_rate=10.0,
        current_price=60.0,
    )
    result = GrahamFormula().calculate(stock)
    assert_within_pct(result.fair_value, 94.64)


def test_graham_formula_growth_none_defaults_zero():
    stock = make_stock(eps=4.0, growth_rate=None, current_price=60.0)
    result = GrahamFormula().calculate(stock)
    assert result.fair_value > 0
    assert any("0%" in note for note in result.analysis)


def test_graham_formula_growth_capped_at_20():
    stock = make_stock(eps=4.0, growth_rate=25.0, current_price=60.0)
    result = GrahamFormula().calculate(stock)
    assert result.details["growth_rate"] == 20.0
    assert any("capped" in note.lower() for note in result.analysis)


def test_ncav_normal():
    stock = make_stock(
        current_assets=10e9,
        total_liabilities=5e9,
        shares_outstanding=1e9,
        current_price=3.0,
    )
    result = NCAV().calculate(stock)
    assert result.fair_value == 5.0
    assert result.components["buy_target_2_3"] == 3.35


def test_ncav_negative_total():
    stock = make_stock(
        current_assets=3e9,
        total_liabilities=8e9,
        shares_outstanding=1e9,
        current_price=3.0,
    )
    result = NCAV().calculate(stock)
    assert result.fair_value < 0
    assert any("negative" in line.lower() or "solvency" in line.lower() for line in result.analysis)


def test_ncav_shares_none():
    stock = make_stock(
        current_assets=10e9,
        total_liabilities=5e9,
        shares_outstanding=None,
        current_price=3.0,
    )
    result = NCAV().calculate(stock)
    assert "shares_outstanding" in result.missing_fields
