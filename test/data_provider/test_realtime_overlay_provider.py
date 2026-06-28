"""RealtimeOverlayProvider 单元测试。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from common.exceptions import DataProviderError
from data_provider.realtime_overlay_provider import RealtimeOverlayProvider


def _sample_df(dates: list[str]) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame(
        {
            "date": dates,
            "open": [10.0] * n,
            "high": [10.5] * n,
            "low": [9.5] * n,
            "close": [10.2] * n,
            "volume": [1_000_000.0] * n,
        }
    )


def _quote(close: float = 11.0) -> dict[str, float | str]:
    today = date.today().strftime("%Y-%m-%d")
    return {
        "date": today,
        "open": 10.8,
        "high": 11.2,
        "low": 10.6,
        "close": close,
        "volume": 2_000_000.0,
    }


def test_overlay_replaces_today_row():
    today = date.today().strftime("%Y-%m-%d")
    df = _sample_df(["2025-01-02", today])
    fetcher = MagicMock()
    fetcher.fetch_realtime_quote.return_value = _quote(11.5)

    overlay = RealtimeOverlayProvider(fetcher)
    result, quote_mode, warnings = overlay.overlay(df, "600519")

    assert quote_mode == "realtime"
    assert not warnings
    assert result.iloc[-1]["date"] == today
    assert result.iloc[-1]["close"] == pytest.approx(11.5)
    assert len(result) == 2


def test_overlay_appends_when_today_missing():
    df = _sample_df(["2025-01-02", "2025-01-03"])
    fetcher = MagicMock()
    fetcher.fetch_realtime_quote.return_value = _quote(11.0)

    overlay = RealtimeOverlayProvider(fetcher)
    result, quote_mode, warnings = overlay.overlay(df, "600519")

    assert quote_mode == "realtime"
    assert not warnings
    assert len(result) == 3
    assert str(result.iloc[-1]["date"])[:10] == date.today().strftime("%Y-%m-%d")


def test_overlay_fallback_on_fetch_failure():
    df = _sample_df(["2025-01-02", "2025-01-03"])
    fetcher = MagicMock()
    fetcher.fetch_realtime_quote.side_effect = DataProviderError("network down")

    overlay = RealtimeOverlayProvider(fetcher)
    result, quote_mode, warnings = overlay.overlay(df, "600519")

    assert quote_mode == "eod_fallback"
    assert any("实时报价获取失败" in w for w in warnings)
    assert result.iloc[-1]["close"] == pytest.approx(10.2)


def test_overlay_fallback_on_zero_close():
    df = _sample_df(["2025-01-02", "2025-01-03"])
    fetcher = MagicMock()
    fetcher.fetch_realtime_quote.return_value = _quote(0.0)

    overlay = RealtimeOverlayProvider(fetcher)
    result, quote_mode, warnings = overlay.overlay(df, "600519")

    assert quote_mode == "eod_fallback"
    assert any("无效" in w for w in warnings)
    assert result.iloc[-1]["close"] == pytest.approx(10.2)
