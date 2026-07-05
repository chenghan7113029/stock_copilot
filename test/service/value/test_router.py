"""PrototypeRouter 单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value.router import PrototypeRouter


def test_icbc_hardcoded_bank():
    router = PrototypeRouter()
    stock = StockData(code="601398", name="工商银行")
    prototype, keys = router.route(stock)
    assert prototype == "bank"
    assert stock.proto == "bank"
    assert "pb" in keys
    assert "residual_income" in keys
    assert "dcf" not in keys


def test_yangtze_power_hardcoded_high_dividend():
    router = PrototypeRouter()
    stock = StockData(code="600900", name="长江电力")
    prototype, keys = router.route(stock)
    assert prototype == "high_dividend"
    assert "ddm" in keys
    assert "two_stage_ddm" in keys


def test_moutai_hardcoded_value_growth():
    router = PrototypeRouter()
    stock = StockData(code="600519", name="贵州茅台")
    prototype, keys = router.route(stock)
    assert prototype == "value_growth"
    assert stock.proto == "value_growth"
    assert "dcf" in keys
    assert "epv" in keys
    assert "owner_earnings" in keys


def test_unknown_when_insufficient_data():
    router = PrototypeRouter()
    stock = StockData(code="999999")
    prototype, keys = router.route(stock)
    assert prototype == "unknown"
    assert stock.proto == "unknown"
    assert "graham_number" in keys
    assert "altman_z" in keys
    assert "value_trap" in keys


def test_bank_classification_by_industry():
    router = PrototypeRouter()
    stock = StockData(code="601288", name="农业银行", industry="商业银行")
    prototype, keys = router.route(stock)
    assert prototype == "bank"
    assert "pb" in keys
    assert "residual_income" in keys


def test_high_leverage_routes_to_bank():
    router = PrototypeRouter()
    stock = StockData(
        code="000001",
        total_assets=10e12,
        total_liabilities=9.5e12,
        dividend_yield=1.0,
        growth_rate=15.0,
    )
    prototype, keys = router.route(stock)
    assert prototype == "bank"
    assert "pb" in keys


def test_high_dividend_low_growth_heuristic():
    router = PrototypeRouter()
    stock = StockData(
        code="000002",
        total_assets=1e11,
        total_liabilities=5e10,
        dividend_yield=5.5,
        growth_rate=3.0,
    )
    prototype, _ = router.route(stock)
    assert prototype == "high_dividend"


def test_normal_stock_defaults_value_growth():
    router = PrototypeRouter()
    stock = StockData(
        code="000003",
        total_assets=1e11,
        total_liabilities=4e10,
        dividend_yield=1.5,
        growth_rate=18.0,
    )
    prototype, keys = router.route(stock)
    assert prototype == "value_growth"
    assert "ncav" not in keys
    assert "dcf" in keys
    assert "piotroski_f" in keys
