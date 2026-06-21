"""KlineProvider 单元测试。"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from common.exceptions import KlineUnavailableError
from data_provider.kline_provider import KlineProvider


def _sample_df(start: str, n: int = 5) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": [10.0] * n,
            "high": [10.5] * n,
            "low": [9.5] * n,
            "close": [10.2] * n,
            "volume": [1_000_000.0] * n,
        }
    )


def test_empty_cache_fetches_and_upserts():
    repo = MagicMock()
    repo.query_range.return_value = []
    baostock = MagicMock()
    baostock.fetch_kline.return_value = _sample_df("2025-01-01", 10)
    akshare = MagicMock()

    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=akshare)
    df, warnings = provider.get_kline("600519", days=90)

    assert not df.empty
    baostock.fetch_kline.assert_called_once()
    assert repo.upsert_batch.called
    upserted = repo.upsert_batch.call_args[0][0]
    today_str = date.today().strftime("%Y-%m-%d")
    assert all(r["trade_date"] < today_str for r in upserted)


def test_partial_cache_only_fetches_gaps():
    cached = [
        {
            "code": "600519",
            "trade_date": "2025-01-02",
            "date": "2025-01-02",
            "open": 10.0,
            "high": 10.5,
            "low": 9.5,
            "close": 10.2,
            "volume": 1_000_000.0,
        }
    ]
    repo = MagicMock()
    repo.query_range.side_effect = [cached, cached + [
        {
            "code": "600519",
            "trade_date": "2025-01-03",
            "date": "2025-01-03",
            "open": 10.1,
            "high": 10.6,
            "low": 9.6,
            "close": 10.3,
            "volume": 1_100_000.0,
        }
    ]]
    baostock = MagicMock()
    baostock.fetch_kline.return_value = _sample_df("2025-01-01", 5)
    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=MagicMock())

    df, _ = provider.get_kline("600519", days=90)
    assert not df.empty
    baostock.fetch_kline.assert_called_once()


def test_baostock_fallback_to_akshare():
    repo = MagicMock()
    repo.query_range.return_value = []
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = Exception("baostock down")
    akshare = MagicMock()
    akshare.fetch_kline.return_value = _sample_df("2025-01-01", 5)

    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=akshare)
    df, _ = provider.get_kline("600519", days=90)

    assert not df.empty
    akshare.fetch_kline.assert_called_once()


def test_both_sources_fail_raises():
    repo = MagicMock()
    repo.query_range.return_value = []
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = Exception("baostock down")
    akshare = MagicMock()
    akshare.fetch_kline.side_effect = Exception("akshare down")

    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=akshare)
    with pytest.raises(KlineUnavailableError):
        provider.get_kline("600519", days=90)


def test_cache_fallback_with_warning_when_fetch_fails():
    old_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    cached = [
        {
            "code": "600519",
            "trade_date": old_date,
            "date": old_date,
            "open": 10.0,
            "high": 10.5,
            "low": 9.5,
            "close": 10.2,
            "volume": 1_000_000.0,
        }
    ]
    repo = MagicMock()
    repo.query_range.return_value = cached
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = Exception("down")
    akshare = MagicMock()
    akshare.fetch_kline.side_effect = Exception("down")

    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=akshare)
    df, warnings = provider.get_kline("600519", days=90)

    assert not df.empty
    assert any("缺口" in w or "缓存" in w for w in warnings)


def test_today_not_written_to_cache():
    repo = MagicMock()
    repo.query_range.return_value = []
    today = date.today().strftime("%Y-%m-%d")
    df_api = _sample_df(today, 3)
    baostock = MagicMock()
    baostock.fetch_kline.return_value = df_api
    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=MagicMock())

    provider.get_kline("600519", days=90)
    if repo.upsert_batch.called:
        upserted = repo.upsert_batch.call_args[0][0]
        assert all(r["trade_date"] < today for r in upserted)
