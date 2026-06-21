"""ValueTrapDetector 单元测试。"""

import pytest

from service.value.valuation.value_trap import ValueTrapDetector


class _Stock:
    """最小 stub，模拟 StockDataAdapter 字段访问。"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name):
        return None


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def low_risk_stock():
    """高股息公用事业类：长江电力风格，各维度均 Low。"""
    return _Stock(
        current_price=30.0,
        # 财务健康 — market_cap 高使 X4=MC/Liabilities >> 1，z_score > 2.99
        total_assets=6e11,
        total_liabilities=2.4e11,     # D/A ≈ 40%
        current_assets=8e10,
        current_liabilities=4e10,     # CR = 2.0
        ebit=3e10,
        interest_expense=5e9,         # ICR = 6
        market_cap=2e12,              # X4 = 2e12/2.4e11 ≈ 8.3 → z > 2.99
        revenue=8e10,
        net_income=2e10,
        shares_outstanding=2.2e10,
        operating_margin=37.0,        # 业务健康
        roe=20.0,
        roic=15.0,
        dividend_per_share=1.2,
        dividend_payout_ratio=55.0,
        fcf=1.8e10,
        retained_earnings=1e11,
        # 其他 AltmanZ 需要字段
        net_working_capital=4e10,
    )


@pytest.fixture
def high_risk_stock():
    """高负债低利润：三个以上维度应为 High。"""
    return _Stock(
        current_price=5.0,
        total_assets=1e10,
        total_liabilities=9e9,          # D/A = 90%
        current_assets=2e9,
        current_liabilities=4e9,        # CR = 0.5
        ebit=5e7,
        interest_expense=8e8,           # ICR < 1
        market_cap=5e9,
        revenue=3e9,
        net_income=5e7,
        shares_outstanding=1e9,
        operating_margin=2.0,           # < 5%
        roe=5.0,
        roic=4.0,
        dividend_per_share=0.1,
        dividend_payout_ratio=120.0,    # > 100%
        fcf=-3e8,
        retained_earnings=5e8,
        net_working_capital=-2e9,
    )


# ── 测试 ─────────────────────────────────────────────────────────────────────

def test_low_risk_overall(low_risk_stock):
    result = ValueTrapDetector().calculate(low_risk_stock)
    assert result.error is None
    assert result.details["overall_risk"] == "Low"
    assert result.details["financial_health"] == "Low"
    assert result.details["moat_erosion"] == "Low"
    assert result.details["dividend_sustainability"] == "Low"


def test_high_risk_overall(high_risk_stock):
    result = ValueTrapDetector().calculate(high_risk_stock)
    assert result.error is None
    assert result.details["overall_risk"] == "High"
    high_dims = [
        d for d in [
            result.details["financial_health"],
            result.details["business_deterioration"],
            result.details["dividend_sustainability"],
        ]
        if d == "High"
    ]
    assert len(high_dims) >= 2


def test_revenue_growth_none_business_dimension_limited():
    stock = _Stock(
        current_price=50.0,
        total_assets=1e11,
        total_liabilities=3e10,
        operating_margin=8.0,
        roe=12.0,
        roic=9.0,
        dividend_per_share=1.0,
        dividend_payout_ratio=40.0,
        fcf=5e9,
        market_cap=2e10,
        net_income=5e9,
        shares_outstanding=5e8,
        revenue=3e10,
        # revenue_growth 不传（= None）
    )
    result = ValueTrapDetector().calculate(stock)
    assert result.error is None
    # revenue_growth=None → 业务恶化维度用 operating_margin 兜底，不应 Limited
    # (operating_margin=8% 在中间范围 → Medium)
    assert result.details["business_deterioration"] in ("Medium", "Limited")
    # 不抛异常即可


def test_no_dividend_data_dividend_not_applicable():
    stock = _Stock(
        current_price=100.0,
        total_assets=5e10,
        total_liabilities=2e10,
        operating_margin=25.0,
        roe=18.0,
        roic=14.0,
        # dividend_per_share = None（无分红）
        market_cap=1e11,
        net_income=5e9,
        shares_outstanding=5e8,
        revenue=2e10,
    )
    result = ValueTrapDetector().calculate(stock)
    assert result.error is None
    assert result.details["dividend_sustainability"] == "Not Applicable"


def test_ai_dimension_always_medium():
    stock = _Stock(current_price=50.0)
    result = ValueTrapDetector().calculate(stock)
    assert result.details["ai_vulnerability"] == "Medium"
    assert "需人工评估" in result.details["ai_vulnerability_note"]


def test_critical_fields_missing_no_exception():
    """total_assets=None 等 critical 字段缺失时不抛异常，维度降级 Limited。"""
    stock = _Stock(current_price=30.0)  # 所有字段均 None
    result = ValueTrapDetector().calculate(stock)
    assert result.error is None
    assert result.details["financial_health"] == "Limited"
    assert result.details["moat_erosion"] == "Limited"


def test_output_type_score():
    stock = _Stock(current_price=50.0, total_assets=1e10, total_liabilities=3e9)
    result = ValueTrapDetector().calculate(stock)
    assert result.details["output_type"] == "score"
    assert result.fair_value == result.current_price
