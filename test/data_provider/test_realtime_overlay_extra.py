"""RealtimeOverlayProvider：无默认 AKShare、failover 链。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.realtime_overlay_provider import RealtimeOverlayProvider


def _sample_df() -> pd.DataFrame:
    yesterday = "2026-08-08"
    return pd.DataFrame(
        {
            "date": [yesterday],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "volume": [1_000_000.0],
        }
    )


def test_no_arg_constructor_does_not_use_akshare():
    overlay = RealtimeOverlayProvider()
    df, mode, warnings = overlay.overlay(_sample_df(), "600519")
    assert mode == "eod_fallback"
    assert any("无可用" in w for w in warnings)


def test_failover_skips_baostock_and_uses_next():
    today = date.today().strftime("%Y-%m-%d")
    bs = MagicMock()
    bs.source_name = "baostock"
    bs.fetch_realtime_quote.side_effect = AssertionError("baostock must be skipped")

    ts = MagicMock()
    ts.source_name = "tushare"
    ts.fetch_realtime_quote.return_value = {
        "date": today,
        "open": 11.0,
        "high": 11.5,
        "low": 10.8,
        "close": 11.2,
        "volume": 1.0,
    }

    overlay = RealtimeOverlayProvider(fetchers=[bs, ts])
    df, mode, warnings = overlay.overlay(_sample_df(), "600519")
    assert mode == "realtime"
    assert float(df.iloc[-1]["close"]) == 11.2
    bs.fetch_realtime_quote.assert_not_called()


def test_all_quote_sources_fail():
    bad = MagicMock()
    bad.source_name = "akshare"
    bad.fetch_realtime_quote.side_effect = DataProviderError("down")
    overlay = RealtimeOverlayProvider(fetchers=[bad])
    _, mode, warnings = overlay.overlay(_sample_df(), "600519")
    assert mode == "eod_fallback"
    assert warnings
