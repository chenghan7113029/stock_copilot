"""保险 EV/NBV 单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.insurance_config import apply_insurance_inputs
from service.value.valuation.insurance_ev import InsuranceEV


def test_insurance_ev_requires_embedded_value():
    stock = StockData(
        code="601318",
        current_price=50.0,
        shares_outstanding=18e9,
        industry="保险",
    )
    result = InsuranceEV().calculate(StockDataAdapter(stock, AssumptionProvider()))
    assert result.applicability == "Not Applicable"
    assert "embedded_value" in (result.missing_fields or [])


def test_insurance_ev_computes_from_ev_and_nbv():
    stock = StockData(
        code="601318",
        current_price=50.0,
        shares_outstanding=18e9,
        embedded_value=1200e9,
        nbv=50e9,
        p_ev_fair=1.0,
    )
    result = InsuranceEV().calculate(StockDataAdapter(stock, AssumptionProvider()))
    assert result.error is None
    assert result.fair_value > 0
    assert result.details["output_type"] == "insurance_ev"
    assert "P/EV" in result.assessment


def test_apply_insurance_inputs_from_config():
    stock = StockData(code="601318", current_price=50.0)
    notes = apply_insurance_inputs(
        stock,
        {
            "value_analysis": {
                "insurance": {
                    "by_code": {
                        "601318": {
                            "embedded_value": 1e12,
                            "nbv": 4e10,
                            "p_ev_fair": 0.9,
                        }
                    }
                }
            }
        },
    )
    assert stock.embedded_value == 1e12
    assert stock.nbv == 4e10
    assert stock.p_ev_fair == 0.9
    assert notes
