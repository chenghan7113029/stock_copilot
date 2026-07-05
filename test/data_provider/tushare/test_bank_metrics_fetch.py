"""Tushare 银行专项指标映射测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_provider.tushare.fetcher import TushareFetcher


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_fundamentals_maps_bank_metrics(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.stock_basic.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "name": "工商银行",
        "industry": "银行",
    }])
    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "eps": 1.0,
        "bps": 8.0,
        "roe": 12.0,
        "netint_margin": 2.05,
        "prov_cov": 215.0,
        "npl_ratio": 1.35,
    }])
    pro.income.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "revenue": 820_000_000_000.0,
        "n_income_attr_p": 300_000_000_000.0,
    }])
    pro.balancesheet.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "total_assets": 40_000_000_000_000.0,
        "total_liab": 37_000_000_000_000.0,
        "total_hldr_eqy_exc_min_int": 3_000_000_000_000.0,
        "money_cap": 5_000_000_000_000.0,
    }])
    pro.cashflow.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "n_cashflow_act": 400_000_000_000.0,
    }])
    pro.dividend.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_fundamentals("601398", "SH")

    assert result.ok
    assert result.data["industry"] == "银行"
    assert result.data["net_interest_margin"] == pytest.approx(2.05)
    assert result.data["provision_coverage"] == pytest.approx(215.0)
    assert result.data["npl_ratio"] == pytest.approx(1.35)


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_fundamentals_stock_basic_industry_for_router(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.stock_basic.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "name": "工商银行",
        "industry": "银行",
    }])
    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "eps": 1.0,
    }])
    pro.income.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "revenue": 100.0,
    }])
    pro.balancesheet.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "total_assets": 100.0,
        "total_liab": 90.0,
        "money_cap": 10.0,
    }])
    pro.cashflow.return_value = pd.DataFrame([{
        "ts_code": "601398.SH",
        "end_date": "20251231",
        "n_cashflow_act": 5.0,
    }])
    pro.dividend.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_fundamentals("601398", "SH")

    assert result.ok
    assert result.data.get("industry") == "银行"
    assert "net_interest_margin" in result.missing_fields
