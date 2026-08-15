"""军工订单驱动估值单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.defense_config import apply_defense_order_inputs
from service.value.valuation.defense_orders import DefenseOrders


def test_defense_orders_requires_backlog_inputs():
    stock = StockData(
        code="600072",
        current_price=20.0,
        shares_outstanding=1e9,
        industry="国防军工",
    )
    result = DefenseOrders().calculate(StockDataAdapter(stock, AssumptionProvider()))
    assert result.applicability == "Not Applicable"
    assert "order_backlog" in (result.missing_fields or [])


def test_defense_orders_computes_fair_value_from_backlog():
    stock = StockData(
        code="600072",
        current_price=20.0,
        shares_outstanding=1e9,
        order_backlog=12e9,
        order_execution_years=3.0,
        order_margin=12.0,
        tax_rate=25.0,
        net_debt=0.0,
    )
    result = DefenseOrders().calculate(StockDataAdapter(stock, AssumptionProvider()))
    assert result.error is None
    assert result.fair_value > 0
    assert result.details["output_type"] == "defense_orders"
    assert "在手订单" in result.assessment


def test_apply_defense_order_inputs_from_config():
    stock = StockData(code="600072", current_price=15.0)
    notes = apply_defense_order_inputs(
        stock,
        {
            "value_analysis": {
                "defense_orders": {
                    "by_code": {
                        "600072": {
                            "order_backlog": 8e9,
                            "order_execution_years": 4.0,
                            "order_margin": 10.0,
                        }
                    }
                }
            }
        },
    )
    assert stock.order_backlog == 8e9
    assert stock.order_execution_years == 4.0
    assert notes
