"""TushareFetcher.fetch_kline 单测（mock pro_bar）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from common.exceptions import DataProviderError
from data_provider.tushare.fetcher import TushareFetcher


@patch("tushare.pro_bar")
@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_kline_success_normalizes_columns(mock_pro_api, mock_set_token, mock_pro_bar):
    mock_pro_api.return_value = MagicMock()
    mock_pro_bar.return_value = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260108",
                "open": 1700.0,
                "high": 1720.0,
                "low": 1690.0,
                "close": 1710.0,
                "vol": 20000.0,
            },
            {
                "ts_code": "600519.SH",
                "trade_date": "20260107",
                "open": 1680.0,
                "high": 1705.0,
                "low": 1675.0,
                "close": 1695.0,
                "vol": 18000.0,
            },
        ]
    )
    fetcher = TushareFetcher(token="fake-token")

    df = fetcher.fetch_kline("600519", "SH", "2026-01-01", "2026-01-09")

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(df["date"]) == ["2026-01-07", "2026-01-08"]
    assert float(df.iloc[-1]["close"]) == 1710.0
    assert float(df.iloc[0]["volume"]) == 18000.0
    mock_pro_bar.assert_called_once()
    kwargs = mock_pro_bar.call_args.kwargs
    assert kwargs["ts_code"] == "600519.SH"
    assert kwargs["adj"] == "qfq"
    assert kwargs["start_date"] == "20260101"
    assert kwargs["end_date"] == "20260109"


@patch("tushare.pro_bar")
@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_kline_empty_raises(mock_pro_api, mock_set_token, mock_pro_bar):
    mock_pro_api.return_value = MagicMock()
    mock_pro_bar.return_value = pd.DataFrame()
    fetcher = TushareFetcher(token="fake-token")

    with pytest.raises(DataProviderError, match="未查询到"):
        fetcher.fetch_kline("600519", "SH", "2026-01-01", "2026-01-09")


@patch("tushare.pro_bar")
@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_kline_api_error_raises(mock_pro_api, mock_set_token, mock_pro_bar):
    mock_pro_api.return_value = MagicMock()
    mock_pro_bar.side_effect = RuntimeError("network down")
    fetcher = TushareFetcher(token="fake-token")

    with pytest.raises(DataProviderError, match="pro_bar"):
        fetcher.fetch_kline("600519", "SH", "2026-01-01", "2026-01-09")
