"""AssumptionProvider 单元测试。"""

from __future__ import annotations

import pytest

from common.models.stock_data import StockData
from service.value.valuation.assumptions import AssumptionProvider


def _stock(**kwargs) -> StockData:
    return StockData(**kwargs)


def test_discount_rate_value_growth_uses_capm():
    provider = AssumptionProvider()
    stock = _stock(proto="value_growth")
    assert provider.get_discount_rate(stock) == pytest.approx(5.4)


def test_discount_rate_unknown_proto_fallback():
    provider = AssumptionProvider()
    stock = _stock(proto="")
    assert provider.get_discount_rate(stock) == 10.0


def test_growth_rate_floor_applies_when_cagr_low():
    provider = AssumptionProvider()
    stock = _stock(proto="value_growth", growth_rate=3.14)
    assert provider.get_growth_rate_1_5(stock) == 8.0


def test_growth_rate_above_floor_unchanged():
    provider = AssumptionProvider()
    stock = _stock(proto="value_growth", growth_rate=15.0)
    assert provider.get_growth_rate_1_5(stock) == 15.0


def test_growth_rate_none_uses_max_of_config_and_floor():
    provider = AssumptionProvider({"value_analysis": {"growth_rate_1_5": 5.0}})
    stock = _stock(proto="value_growth", growth_rate=None)
    assert provider.get_growth_rate_1_5(stock) == 8.0
