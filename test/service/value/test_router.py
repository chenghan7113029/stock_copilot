"""PrototypeRouter 单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value import router as router_module
from service.value.router import PrototypeRouter, describe_unimplemented_industry


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


def test_insurance_industry_short_circuits_high_leverage_bank_heuristic():
    router = PrototypeRouter()
    stock = StockData(
        code="601318",
        industry="保险",
        total_assets=10e12,
        total_liabilities=9e12,
    )
    prototype, _ = router.route(stock)
    assert prototype == "unknown"


def test_military_industries_short_circuit_financial_heuristics():
    router = PrototypeRouter()
    for industry in ("国防军工", "军工"):
        stock = StockData(
            code="600000",
            industry=industry,
            total_assets=10e12,
            total_liabilities=9e12,
        )
        prototype, _ = router.route(stock)
        assert prototype == "unknown"


def test_describe_unimplemented_industry_returns_specific_methodology_gaps():
    assert describe_unimplemented_industry("保险") == (
        "保险",
        "专用估值方法论（内含价值 EV/NBV 模型）暂缺",
    )
    assert describe_unimplemented_industry("国防军工") == (
        "军工",
        "专用估值方法论（在手订单驱动 + 资产重估模型）暂缺",
    )


def test_describe_unimplemented_industry_returns_none_for_missing_or_unlisted_industry():
    assert describe_unimplemented_industry("") is None
    assert describe_unimplemented_industry(None) is None
    assert describe_unimplemented_industry("某未收录行业") is None


def test_describe_unimplemented_industry_uses_generic_gap_when_dictionaries_diverge(monkeypatch):
    monkeypatch.setitem(router_module._INDUSTRY_V2_UNIMPLEMENTED, "未来行业", "未来原型")
    assert describe_unimplemented_industry("未来行业") == ("未来原型", "专用估值方法论暂缺")


def test_power_industry_routes_to_high_dividend_before_heuristics():
    router = PrototypeRouter()
    stock = StockData(
        code="600000",
        industry="电力",
        total_assets=10e12,
        total_liabilities=4e12,
        dividend_yield=1.0,
        growth_rate=20.0,
    )
    prototype, _ = router.route(stock)
    assert prototype == "high_dividend"


def test_high_leverage_routes_to_bank():
    router = PrototypeRouter()
    stock = StockData(
        code="000001",
        industry="",
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
        industry=None,
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


def test_manual_override_has_priority_over_hardcoded_code():
    router = PrototypeRouter()
    stock = StockData(code="601398", name="工商银行")

    prototype, keys = router.route(stock, override="high_dividend")

    assert prototype == "high_dividend"
    assert stock.proto == "high_dividend"
    assert "ddm" in keys
    assert "pb" not in keys


def test_none_override_preserves_existing_routing_behavior():
    router = PrototypeRouter()
    stock = StockData(code="601398", name="工商银行")

    prototype, keys = router.route(stock, override=None)

    assert prototype == "bank"
    assert "pb" in keys


def test_invalid_manual_override_falls_back_to_normal_routing():
    router = PrototypeRouter()
    stock = StockData(code="601398", name="工商银行")

    prototype, keys = router.route(stock, override="invalid_prototype")

    assert prototype == "bank"
    assert stock.proto == "bank"
    assert "pb" in keys
