from datetime import datetime
from unittest.mock import MagicMock

import pytest

from common.exceptions import DataProviderError
from data_provider.base import FetchResult
from data_provider.sentiment.provider import MarketSentimentProvider


def test_fetch_and_persist_today_calculates_and_saves_snapshot() -> None:
    repo = MagicMock()
    fetcher = MagicMock()
    fetcher.fetch_market_breadth.return_value = FetchResult(
        data={"limit_up_count": 50, "limit_down_count": 10, "up_count": 3000, "down_count": 1000}
    )
    fetcher.fetch_margin_change.return_value = FetchResult(data={"margin_balance_change_pct": 1.0})
    fetcher.fetch_turnover_percentile.return_value = FetchResult(data={"turnover_percentile": 60.0})

    snapshot = MarketSentimentProvider(repo, fetcher).fetch_and_persist_today()

    assert snapshot["fear_greed_index"] is not None
    assert snapshot["limit_up_count"] == 50
    repo.upsert.assert_called_once_with(snapshot)


def test_get_latest_offline_never_calls_fetcher() -> None:
    repo = MagicMock()
    cached = MagicMock(fetched_at=datetime(2026, 8, 1))
    repo.get_latest.return_value = cached
    fetcher = MagicMock()

    result = MarketSentimentProvider(repo, fetcher).get_latest_offline()

    assert result is cached
    fetcher.fetch_market_breadth.assert_not_called()


def test_fetch_raises_when_no_sentiment_source() -> None:
    repo = MagicMock()
    empty = MarketSentimentProvider(repo, None, use_akshare=False)
    with pytest.raises(DataProviderError, match="data_sources.enabled"):
        empty.fetch_and_persist_today()


def test_fetch_via_tushare_fetcher_writes_warnings() -> None:
    repo = MagicMock()
    fetcher = MagicMock()
    fetcher.source_name = "tushare"
    fetcher.fetch_market_breadth.return_value = FetchResult(
        data={
            "limit_up_count": 40,
            "limit_down_count": 8,
            "up_count": 2000,
            "down_count": 1500,
            "_breadth_approximation": True,
        }
    )
    fetcher.fetch_margin_change.return_value = FetchResult(data={"margin_balance_change_pct": 0.5})
    fetcher.fetch_turnover_percentile.return_value = FetchResult(
        error="missing turnover", missing_fields=["turnover_percentile"]
    )

    snapshot = MarketSentimentProvider(repo, fetcher, use_akshare=False).fetch_and_persist_today()

    assert snapshot["limit_up_count"] == 40
    assert snapshot["source"] == "tushare"
    assert snapshot["turnover_percentile"] is None
    assert any("近似" in w for w in snapshot["warnings"])
    assert "_breadth_approximation" not in snapshot
    repo.upsert.assert_called_once()
