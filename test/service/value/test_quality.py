"""质量/风险评分单元测试。"""

from __future__ import annotations

from service.value.valuation.mscore import BeneishMScore
from service.value.valuation.quality import AltmanZScore, PiotroskiFScore

from .conftest import make_stock


def test_altman_z_safe_zone():
    stock = make_stock(
        total_assets=500e9,
        total_liabilities=150e9,
        current_assets=200e9,
        ebit=80e9,
        revenue=300e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = AltmanZScore().calculate(stock)
    assert result.details["output_type"] == "score"
    assert result.details["z_score"] > 2.99
    assert result.fair_value == stock.current_price


def test_altman_z_distress_zone():
    stock = make_stock(
        total_assets=100e9,
        total_liabilities=90e9,
        current_assets=10e9,
        ebit=1e9,
        revenue=20e9,
        shares_outstanding=1e9,
        current_price=5.0,
    )
    result = AltmanZScore().calculate(stock)
    assert result.details["z_score"] < 1.81


def test_piotroski_f_score_integer_and_details():
    stock = make_stock(
        net_income=50e9,
        total_assets=500e9,
        fcf=60e9,
        total_liabilities=150e9,
        current_assets=200e9,
        current_liabilities=100e9,
        revenue=300e9,
        operating_margin=30.0,
        shares_outstanding=1.26e9,
        current_price=1800.0,
        prior_roa=0.08,
        prior_debt_ratio=0.35,
        prior_current_ratio=1.5,
        prior_shares_outstanding=1.26e9,
        prior_gross_margin=25.0,
        prior_asset_turnover=0.8,
    )
    result = PiotroskiFScore().calculate(stock)
    assert result.details["output_type"] == "score"
    assert isinstance(result.details["f_score"], int)
    assert 0 <= result.details["f_score"] <= 9
    assert result.fair_value == stock.current_price


def test_piotroski_limited_when_many_prior_missing():
    stock = make_stock(
        net_income=50e9,
        total_assets=500e9,
        fcf=60e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = PiotroskiFScore().calculate(stock)
    assert result.applicability == "Limited"
    assert len(result.details["criteria_skipped"]) >= 4


def test_beneish_m_score_thresholds():
    stock = make_stock(
        revenue=120e9,
        total_assets=500e9,
        current_assets=200e9,
        accounts_receivable=30e9,
        net_income=50e9,
        fcf=45e9,
        net_fixed_assets=150e9,
        depreciation=10e9,
        operating_margin=35.0,
        total_liabilities=150e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = BeneishMScore(
        prior_revenue=100e9,
        prior_gross_margin=38.0,
        prior_total_assets=450e9,
        prior_current_assets=180e9,
        prior_ppe=140e9,
        prior_depreciation=9e9,
        prior_sga=12e9,
        prior_total_debt=140e9,
        prior_accounts_receivable=25e9,
    ).calculate(stock)
    assert result.details["output_type"] == "score"
    assert "m_score" in result.details
    assert result.details["m_score"] < -2.22


def test_beneish_missing_prior_limited():
    stock = make_stock(
        revenue=120e9,
        total_assets=500e9,
        net_income=50e9,
        shares_outstanding=1.26e9,
        current_price=1800.0,
    )
    result = BeneishMScore().calculate(stock)
    assert result.applicability == "Limited"
    assert result.error is None
