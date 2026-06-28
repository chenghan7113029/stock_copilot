"""KlineProvider offline / persist_today 测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from data_provider.kline_provider import KlineProvider


def test_offline_mode_reads_cache_only():
    cached = [
        {
            "code": "600519",
            "trade_date": "2025-06-01",
            "date": "2025-06-01",
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
    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=MagicMock())

    df, warnings, quote_mode = provider.get_kline("600519", days=90, offline=True)

    assert not df.empty
    assert quote_mode == "eod"
    baostock.fetch_kline.assert_not_called()


def test_offline_mode_empty_cache():
    repo = MagicMock()
    repo.query_range.return_value = []
    provider = KlineProvider(repo, baostock_fetcher=MagicMock(), akshare_fetcher=MagicMock())

    df, warnings, quote_mode = provider.get_kline("600519", days=90, offline=True)

    assert df.empty
    assert quote_mode == "eod"
    assert any("无缓存" in w for w in warnings)


def test_persist_today_writes_row():
    repo = MagicMock()
    repo.query_range.return_value = []
    today = date.today().strftime("%Y-%m-%d")
    df_api = pd.DataFrame(
        {
            "date": [today],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "volume": [1_000_000.0],
        }
    )
    baostock = MagicMock()
    baostock.fetch_kline.return_value = df_api

    overlay = MagicMock()
    overlay.overlay.return_value = (df_api, "realtime", [])

    provider = KlineProvider(
        repo,
        baostock_fetcher=baostock,
        akshare_fetcher=MagicMock(),
        realtime_overlay=overlay,
    )
    provider.get_kline("600519", days=90, use_realtime=True, persist_today=True)

    repo.upsert_batch.assert_called()
    upserted = repo.upsert_batch.call_args[0][0]
    assert upserted[-1]["trade_date"] == today
