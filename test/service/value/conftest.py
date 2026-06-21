"""估值方法单元测试辅助。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.valuation.adapter import StockDataAdapter
from service.value.valuation.assumptions import AssumptionProvider


def make_stock(**kwargs) -> StockDataAdapter:
    data = StockData(code="TEST", name="Test", **kwargs)
    return StockDataAdapter(data, AssumptionProvider())


def assert_within_pct(actual: float, expected: float, pct: float = 0.001) -> None:
    if expected == 0:
        assert actual == expected
        return
    assert abs(actual - expected) / abs(expected) <= pct, (
        f"expected {expected}, got {actual}, diff {abs(actual - expected) / abs(expected):.4%}"
    )
