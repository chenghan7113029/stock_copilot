"""Tushare fetcher 离线单元测试（mock pro_api，不发网络请求）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from common.exceptions import DataProviderError
from data_provider.tushare.fetcher import TushareFetcher, _safe_float, _scale_value


@pytest.mark.parametrize("raw,expected", [
    (None, None),
    (float("nan"), None),
    ("", None),
    (0, 0.0),
    (0.0, 0.0),
    ("12.5", 12.5),
])
def test_safe_float(raw, expected):
    if expected is None and isinstance(raw, float) and raw != raw:
        assert _safe_float(raw) is None
    else:
        assert _safe_float(raw) == expected


def test_scale_value_wan():
    assert _scale_value("market_cap", 100.0) == 1_000_000.0
    assert _scale_value("shares_outstanding", 50.0) == 500_000.0
    assert _scale_value("eps", 3.5) == 3.5


def _make_pro_mock():
    pro = MagicMock()

    pro.daily.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "trade_date": "20240601",
        "close": 1680.0,
    }])

    pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "trade_date": "20240601",
        "pe_ttm": 25.5,
        "pb": 8.2,
        "total_mv": 2100000.0,
        "total_share": 125619.0,
        "dv_ratio": 1.8,
    }])

    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20240331",
        "eps": 15.88,
        "bps": 180.5,
        "roe": 28.5,
        "roic": 22.1,
        "netprofit_margin": 52.0,
    }])

    pro.income.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20240331",
        "revenue": 45000000000.0,
        "n_income_attr_p": 24000000000.0,
        "operate_profit": 30000000000.0,
        "fin_exp_int_exp": 1000000.0,
    }])

    pro.balancesheet.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20240331",
        "total_assets": 280000000000.0,
        "total_liab": 50000000000.0,
        "total_cur_assets": 200000000000.0,
        "total_cur_liab": 40000000000.0,
        "total_hldr_eqy_exc_min_int": 230000000000.0,
    }])

    pro.cashflow.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20240331",
        "n_cashflow_act": 20000000000.0,
        "c_pay_acq_const_fiolta": 1500000000.0,
        "depr_fa_cog_dp": 500000000.0,
    }])

    pro.dividend.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20231231",
        "cash_div_tax": 30.876,
    }])

    return pro


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_quote_maps_fields(mock_pro_api, mock_set_token):
    mock_pro_api.return_value = _make_pro_mock()
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert result.data["current_price"] == 1680.0
    assert result.data["pe_ratio"] == 25.5
    assert result.data["market_cap"] == 21_000_000_000.0
    assert result.data["shares_outstanding"] == 1_256_190_000.0


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_fundamentals_none_semantics(mock_pro_api, mock_set_token):
    pro = _make_pro_mock()
    pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "end_date": "20240331",
        "eps": 0.0,
        "bps": None,
        "roe": 28.5,
    }])
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data["eps"] == 0.0
    assert result.data.get("bvps") is None
    assert "bvps" in result.missing_fields
    assert result.data["fcf"] == 18_500_000_000.0


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_quote_api_error(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.daily.side_effect = RuntimeError("rate limit")
    pro.daily_basic.side_effect = RuntimeError("rate limit")
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_quote("600519", "SH")
    assert not result.ok
    assert result.error


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_quote_derives_price_without_daily(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.daily.side_effect = RuntimeError("no permission")
    pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "trade_date": "20240601",
        "total_mv": 2100000.0,
        "total_share": 125619.0,
        "pe_ttm": 25.5,
    }])
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert result.data["current_price"] == pytest.approx(2100000.0 / 125619.0)


def test_init_empty_token_raises():
    with pytest.raises(DataProviderError):
        TushareFetcher(token="")
