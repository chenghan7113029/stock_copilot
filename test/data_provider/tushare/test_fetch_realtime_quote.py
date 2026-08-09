"""TushareFetcher.fetch_realtime_quote 单测（mock rt_k）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from common.exceptions import DataProviderError
from data_provider.tushare.fetcher import TushareFetcher


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_realtime_quote_success(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.rt_k.return_value = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "name": "贵州茅台",
                "open": 1700.0,
                "high": 1720.0,
                "low": 1690.0,
                "close": 1710.0,
                "vol": 1_234_567,
                "trade_time": "2026-08-09 10:30:00",
            }
        ]
    )
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    quote = fetcher.fetch_realtime_quote("600519")

    assert quote["date"] == "2026-08-09"
    assert quote["open"] == 1700.0
    assert quote["high"] == 1720.0
    assert quote["low"] == 1690.0
    assert quote["close"] == 1710.0
    assert quote["volume"] == 1_234_567.0
    pro.rt_k.assert_called_once_with(ts_code="600519.SH")
    pro.daily.assert_not_called()


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_realtime_quote_permission_error(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.rt_k.side_effect = Exception("抱歉，您没有接口访问权限")
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    with pytest.raises(DataProviderError, match="无权限|未开通"):
        fetcher.fetch_realtime_quote("600519")
    pro.daily.assert_not_called()


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_realtime_quote_empty_raises_without_daily_fallback(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.rt_k.return_value = pd.DataFrame()
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    with pytest.raises(DataProviderError, match="rt_k"):
        fetcher.fetch_realtime_quote("600519")
    pro.daily.assert_not_called()
