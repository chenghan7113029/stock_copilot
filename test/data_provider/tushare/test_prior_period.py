"""Tushare prior 年度财报推导 prior_* 字段测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_provider.tushare.fetcher import TushareFetcher, _prior_year_period


def test_prior_year_period_from_annual():
    assert _prior_year_period("20251231") == "20241231"
    assert _prior_year_period("20260331") is None


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_prior_year_financials_derives_six_fields(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20241231",
        "roa": 28.5,
    }])
    pro.balancesheet.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20241231",
        "total_assets": 280_000_000_000.0,
        "total_liab": 50_000_000_000.0,
        "total_cur_assets": 200_000_000_000.0,
        "total_cur_liab": 40_000_000_000.0,
        "total_share": 1_256_190_000.0,
    }])
    pro.income.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20241231",
        "revenue": 150_000_000_000.0,
        "oper_cost": 20_000_000_000.0,
        "total_share": 1_256_190_000.0,
    }])
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    data: dict = {}
    missing: list[str] = []
    fetcher._fetch_prior_year_financials("600519.SH", "20251231", data, missing)

    assert data["prior_roa"] == pytest.approx(28.5)
    assert data["prior_debt_ratio"] == pytest.approx(50_000_000_000.0 / 280_000_000_000.0)
    assert data["prior_current_ratio"] == pytest.approx(5.0)
    assert data["prior_gross_margin"] == pytest.approx((150_000_000_000.0 - 20_000_000_000.0) / 150_000_000_000.0)
    assert data["prior_asset_turnover"] == pytest.approx(150_000_000_000.0 / 280_000_000_000.0)
    assert data["prior_shares_outstanding"] == pytest.approx(1_256_190_000.0)
    for field in (
        "prior_roa",
        "prior_debt_ratio",
        "prior_current_ratio",
        "prior_shares_outstanding",
        "prior_gross_margin",
        "prior_asset_turnover",
    ):
        assert field not in missing


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_prior_year_financials_empty_api_marks_missing(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.fina_indicator.return_value = pd.DataFrame()
    pro.balancesheet.return_value = pd.DataFrame()
    pro.income.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    data: dict = {}
    missing: list[str] = []
    fetcher._fetch_prior_year_financials("600519.SH", "20251231", data, missing)

    assert not data
    assert "prior_roa" in missing
    assert "prior_gross_margin" in missing


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_fundamentals_skips_prior_for_quarterly_report(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20260331",
        "eps": 21.76,
        "roe": 28.5,
    }])
    pro.income.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20260331",
        "revenue": 45_000_000_000.0,
        "n_income_attr_p": 24_000_000_000.0,
    }])
    pro.balancesheet.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20260331",
        "total_assets": 280_000_000_000.0,
        "total_liab": 50_000_000_000.0,
        "money_cap": 180_000_000_000.0,
    }])
    pro.cashflow.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20260331",
        "n_cashflow_act": 20_000_000_000.0,
    }])
    pro.dividend.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data.get("prior_roa") is None
    assert pro.fina_indicator.call_count == 1


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_fundamentals_fetches_prior_when_annual_report(mock_pro_api, mock_set_token):
    pro = MagicMock()

    def fina_indicator_side_effect(**kwargs):
        period = kwargs.get("period")
        if period == "20241231":
            return pd.DataFrame([{"ts_code": "600519.SH", "end_date": "20241231", "roa": 27.0}])
        return pd.DataFrame([{
            "ts_code": "600519.SH",
            "end_date": "20251231",
            "eps": 65.0,
            "roe": 30.0,
        }])

    def balancesheet_side_effect(**kwargs):
        period = kwargs.get("period")
        if period == "20241231":
            return pd.DataFrame([{
                "ts_code": "600519.SH",
                "end_date": "20241231",
                "total_assets": 300_000_000_000.0,
                "total_liab": 60_000_000_000.0,
                "total_cur_assets": 210_000_000_000.0,
                "total_cur_liab": 42_000_000_000.0,
            }])
        return pd.DataFrame([{
            "ts_code": "600519.SH",
            "end_date": "20251231",
            "total_assets": 320_000_000_000.0,
            "total_liab": 55_000_000_000.0,
            "money_cap": 200_000_000_000.0,
        }])

    def income_side_effect(**kwargs):
        period = kwargs.get("period")
        if period == "20241231":
            return pd.DataFrame([{
                "ts_code": "600519.SH",
                "end_date": "20241231",
                "revenue": 160_000_000_000.0,
                "oper_cost": 18_000_000_000.0,
            }])
        return pd.DataFrame([{
            "ts_code": "600519.SH",
            "end_date": "20251231",
            "revenue": 170_000_000_000.0,
            "n_income_attr_p": 82_000_000_000.0,
        }])

    pro.fina_indicator.side_effect = fina_indicator_side_effect
    pro.balancesheet.side_effect = balancesheet_side_effect
    pro.income.side_effect = income_side_effect
    pro.cashflow.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20251231",
        "n_cashflow_act": 60_000_000_000.0,
    }])
    pro.dividend.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data["prior_roa"] == pytest.approx(27.0)
    assert result.data.get("fundamental_report_date") == date(2025, 12, 31)
    assert pro.fina_indicator.call_count == 2
