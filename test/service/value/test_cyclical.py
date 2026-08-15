"""周期调整估值单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.cycle_config import apply_cycle_inputs, infer_cycle_position_from_pe
from service.value.valuation.cyclical import CyclicalFCF, CyclicalPE


def test_cyclical_methods_require_cycle_position():
    stock = StockData(
        code="002027",
        current_price=10.0,
        eps=0.8,
        bvps=2.0,
        fcf=5e9,
        shares_outstanding=1e9,
        historical_roe=[20.0, 18.0, 22.0, 19.0],
    )
    adapter = StockDataAdapter(stock, AssumptionProvider())
    pe = CyclicalPE().calculate(adapter)
    fcf = CyclicalFCF().calculate(adapter)
    assert pe.applicability == "Not Applicable"
    assert fcf.applicability == "Not Applicable"
    assert "cycle_position" in (pe.missing_fields or [])


def test_cyclical_pe_and_fcf_with_position():
    stock = StockData(
        code="002027",
        current_price=10.0,
        eps=0.5,
        bvps=2.0,
        fcf=5e9,
        shares_outstanding=1e9,
        cycle_position="mid",
        historical_roe=[20.0, 18.0, 22.0, 19.0],
    )
    adapter = StockDataAdapter(stock, AssumptionProvider())
    pe = CyclicalPE().calculate(adapter)
    fcf = CyclicalFCF().calculate(adapter)

    assert pe.error is None and pe.fair_value > 0
    assert pe.details["output_type"] == "cyclical"
    assert "周期位置" in pe.assessment
    assert fcf.error is None and fcf.fair_value > 0
    assert fcf.details["fcf_source"] == "current_fcf"


def test_apply_cycle_inputs_from_config():
    stock = StockData(code="002027", current_price=8.0)
    notes = apply_cycle_inputs(
        stock,
        {
            "value_analysis": {
                "cyclical": {
                    "by_code": {
                        "002027": {
                            "cycle_position": "late",
                            "normalized_eps": 0.4,
                            "normalized_fcf": 4e9,
                        }
                    }
                }
            }
        },
    )
    assert stock.cycle_position == "late"
    assert stock.normalized_eps == 0.4
    assert stock.normalized_fcf == 4e9
    assert notes


def test_infer_cycle_position_from_pe_percentile():
    stock = StockData(
        code="002027",
        pe_ratio=8.0,
        historical_pe=[25, 22, 20, 18, 15, 12, 10, 9, 8, 7],
    )
    assert infer_cycle_position_from_pe(stock) == "late"
