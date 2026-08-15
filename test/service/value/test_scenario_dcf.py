"""浅情景 DCF 单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.scenario_config import resolve_scenario_params
from service.value.valuation.scenario_dcf import ScenarioDCF


def test_resolve_scenario_params_defaults_and_code_override():
    params = resolve_scenario_params(
        "002594",
        {
            "value_analysis": {
                "scenario_dcf": {
                    "defaults": {"base": {"growth_rate_1_5": 11.0}},
                    "by_code": {"002594": {"bull": {"growth_rate_1_5": 22.0}}},
                }
            }
        },
    )
    assert params["bear"].growth_rate_1_5 == 6.0
    assert params["base"].growth_rate_1_5 == 11.0
    assert params["bull"].growth_rate_1_5 == 22.0


def test_scenario_dcf_returns_three_buckets():
    stock = StockData(
        code="002594",
        name="比亚迪",
        current_price=100.0,
        fcf=5e9,
        shares_outstanding=1e9,
        net_debt=0.0,
        proto="growth_manufacturing",
    )
    adapter = StockDataAdapter(stock, AssumptionProvider())
    result = ScenarioDCF().calculate(adapter)

    assert result.error is None
    assert result.applicability == "Applicable"
    assert result.details["output_type"] == "scenario"
    scenarios = result.details["scenarios"]
    assert scenarios["bear"]["fair_value"] < scenarios["bull"]["fair_value"]
    assert result.fair_value == scenarios["base"]["fair_value"]
    assert result.fair_value_range is not None
    assert result.fair_value_range.low <= result.fair_value_range.base <= result.fair_value_range.high


def test_scenario_dcf_falls_back_to_net_income_when_fcf_non_positive():
    stock = StockData(
        code="002594",
        name="比亚迪",
        current_price=100.0,
        fcf=-1e9,
        net_income=10e9,
        shares_outstanding=1e9,
        net_debt=0.0,
        proto="growth_manufacturing",
    )
    adapter = StockDataAdapter(stock, AssumptionProvider({"value_analysis": {"fcf_rate": 0.8}}))
    result = ScenarioDCF(config={"value_analysis": {"fcf_rate": 0.8}}).calculate(adapter)

    assert result.error is None
    assert result.details["cash_source"] == "net_income_fcf_rate"
    assert result.details["cash_base"] == 8e9
    assert result.details["output_type"] == "scenario"
    assert result.confidence == "Low"


def test_resolve_scenario_cash_base_prefers_ocf_over_net_income():
    from types import SimpleNamespace

    from service.value.valuation.scenario_dcf import _resolve_scenario_cash_base

    stock = SimpleNamespace(fcf=-1.0, operating_cash_flow=5e9, net_income=10e9)
    cash, source, notes = _resolve_scenario_cash_base(stock, None)
    assert cash == 5e9
    assert source == "operating_cash_flow"
    assert notes


def test_scenario_dcf_fails_without_cash_base():
    stock = StockData(code="002594", current_price=100.0, shares_outstanding=1e9)
    adapter = StockDataAdapter(stock, AssumptionProvider())
    result = ScenarioDCF().calculate(adapter)
    assert result.applicability == "Not Applicable"
    assert result.error
