"""PrototypeRouter 单元测试。"""

from __future__ import annotations

from common.models.stock_data import StockData
from service.value import router as router_module
from service.value.router import (
    PrototypeRouter,
    describe_honesty_gap,
    describe_unimplemented_industry,
)


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
        code="601601",
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
    insurance = describe_unimplemented_industry("保险")
    assert insurance is not None
    assert insurance[0] == "保险"
    assert "EV/NBV" in insurance[1]
    assert "不应用于买卖决策" in insurance[1]

    military = describe_unimplemented_industry("国防军工")
    assert military is not None
    assert military[0] == "军工"
    assert "订单" in military[1]
    assert "不应用于买卖决策" in military[1]


def test_describe_unimplemented_industry_returns_none_for_missing_or_unlisted_industry():
    assert describe_unimplemented_industry("") is None
    assert describe_unimplemented_industry(None) is None
    assert describe_unimplemented_industry("某未收录行业") is None


def test_describe_unimplemented_industry_uses_generic_gap_when_dictionaries_diverge(monkeypatch):
    monkeypatch.setitem(router_module._INDUSTRY_V2_UNIMPLEMENTED, "未来行业", "未来原型")
    result = describe_unimplemented_industry("未来行业")
    assert result is not None
    assert result[0] == "未来原型"
    assert "专用估值方法论暂缺" in result[1]
    assert "不应用于买卖决策" in result[1]


def test_byd_routes_to_growth_manufacturing_after_p1():
    router = PrototypeRouter()
    byd = StockData(code="002594", industry="汽车整车", growth_rate=20.0, total_assets=1e11)
    focus = StockData(code="002027", industry="广告营销", growth_rate=12.0, total_assets=1e10)

    byd_proto, byd_keys = router.route(byd)
    focus_proto, focus_keys = router.route(focus)

    assert byd_proto == "growth_manufacturing"
    assert "scenario_dcf" in byd_keys
    assert focus_proto == "cashflow_ad_cycle"
    assert "cyclical_fcf" in focus_keys
    assert "cyclical_pe" in focus_keys


def test_cssc_routes_to_defense_orders():
    router = PrototypeRouter()
    stock = StockData(
        code="600072",
        name="中船科技",
        industry="国防军工",
        total_assets=1e11,
        total_liabilities=9e10,
    )
    prototype, keys = router.route(stock)
    assert prototype == "defense_orders"
    assert "defense_orders" in keys
    assert describe_honesty_gap("600072", "国防军工") is None


def test_other_military_stock_still_honesty_unknown():
    router = PrototypeRouter()
    stock = StockData(
        code="600760",
        industry="国防军工",
        total_assets=1e11,
        total_liabilities=9e10,
    )
    prototype, _ = router.route(stock)
    assert prototype == "unknown"
    gap = describe_honesty_gap("600760", "国防军工")
    assert gap is not None
    assert gap.label == "军工"

    router = PrototypeRouter()
    stock = StockData(code="600519", name="贵州茅台", growth_rate=15.0, total_assets=1e11)
    prototype, keys = router.route(stock)
    assert prototype == "value_growth"
    assert "dcf" in keys


def test_honesty_code_override_to_value_growth_still_works():
    router = PrototypeRouter()
    stock = StockData(code="002594", industry="汽车整车", growth_rate=20.0)
    prototype, keys = router.route(stock, override="value_growth")
    assert prototype == "value_growth"
    assert "dcf" in keys


def test_describe_honesty_gap_code_priority_and_industry():
    assert describe_honesty_gap("002594", "汽车整车") is None
    assert describe_honesty_gap("002027", "广告营销") is None
    assert describe_honesty_gap("601318", "保险") is None

    insurance = describe_honesty_gap("601601", "保险")
    assert insurance is not None
    assert insurance.label == "保险"
    assert "EV/NBV" in insurance.methodology_gap

    assert describe_honesty_gap("600519", "白酒") is None


def test_huace_routes_to_growth_tech():
    router = PrototypeRouter()
    stock = StockData(code="300627", name="华测导航", growth_rate=25.0, total_assets=1e10)
    prototype, keys = router.route(stock)
    assert prototype == "growth_tech"
    assert "peg" in keys
    assert "rule_of_40" in keys
    assert "garp" in keys


def test_software_industry_maps_to_growth_tech():
    router = PrototypeRouter()
    stock = StockData(code="999001", industry="软件服务", growth_rate=20.0, total_assets=1e10)
    prototype, keys = router.route(stock)
    assert prototype == "growth_tech"
    assert "peg" in keys


def test_ping_an_routes_to_insurance():
    router = PrototypeRouter()
    stock = StockData(
        code="601318",
        name="中国平安",
        industry="保险",
        total_assets=10e12,
        total_liabilities=9e12,
    )
    prototype, keys = router.route(stock)
    assert prototype == "insurance"
    assert "insurance_ev" in keys


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
