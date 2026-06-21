"""基础设施层单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.base import BaseValuation, FieldRequirement, ValuationResult
from service.value.valuation.engine import ValuationEngine
from service.value.valuation.graham import GrahamNumber
from service.value.valuation.wacc import calculate_wacc

from .conftest import assert_within_pct, make_stock


def test_none_is_missing_not_zero():
    stock = make_stock(eps=None, bvps=30.0, current_price=50.0)
    result = GrahamNumber().calculate(stock)
    assert "eps" in result.missing_fields
    assert result.fair_value == 0
    assert result.error is not None


def test_zero_interest_expense_not_missing():
    data = StockData(code="T", interest_expense=0.0)
    adapter = StockDataAdapter(data, AssumptionProvider())
    assert adapter.interest_expense == 0.0


def test_assumption_provider_default_discount_rate():
    provider = AssumptionProvider()
    stock = StockData(code="T")
    assert provider.get_discount_rate(stock) == 10.0


def test_assumption_provider_tax_rate_from_stock():
    provider = AssumptionProvider()
    stock = StockData(code="T", tax_rate=8.5)
    assert provider.get_tax_rate(stock) == 8.5


def test_engine_run_all_continues_on_exception():
    class Boom(BaseValuation):
        method_name = "Boom"

        def calculate(self, stock) -> ValuationResult:
            raise RuntimeError("boom")

    engine = ValuationEngine()
    engine.register("boom", Boom())
    engine.register("graham_number", GrahamNumber())

    stock_data = StockData(code="T", eps=5.0, bvps=30.0, current_price=50.0)
    results = engine.run_all(stock_data)

    assert results["boom"].error == "boom"
    assert results["graham_number"].fair_value == 58.09


def test_wacc_matches_ref():
    stock = make_stock(
        current_price=10.0,
        shares_outstanding=1e9,
        net_debt=2e9,
        interest_expense=100e6,
        short_term_debt=1e9,
        long_term_debt=1e9,
        tax_rate=25.0,
    )
    wacc = calculate_wacc(stock, assumptions=AssumptionProvider())
    assert_within_pct(wacc.wacc, 8.9583)
    assert_within_pct(wacc.equity_weight, 0.8333)
    assert_within_pct(wacc.debt_weight, 0.1667)


def test_wacc_no_debt_equity_weight_one():
    stock = make_stock(
        current_price=10.0,
        shares_outstanding=1e9,
        net_debt=0.0,
        interest_expense=0.0,
        tax_rate=25.0,
    )
    wacc = calculate_wacc(stock, assumptions=AssumptionProvider())
    assert wacc.equity_weight == 1.0
    assert wacc.debt_weight == 0.0


class _FieldProbe(BaseValuation):
    method_name = "FieldProbe"
    required_fields = [
        FieldRequirement("interest_expense", "Interest Expense", is_critical=False),
    ]

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, _ = self.validate_data(stock)
        return ValuationResult(
            method=self.method_name,
            fair_value=1.0,
            current_price=1.0,
            premium_discount=0.0,
            assessment="Fair",
            missing_fields=missing,
        )


def test_zero_not_treated_as_missing_in_validate():
    stock = make_stock(interest_expense=0.0, current_price=1.0)
    result = _FieldProbe().calculate(stock)
    assert result.missing_fields == []
