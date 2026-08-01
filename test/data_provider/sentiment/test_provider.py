from datetime import datetime
from unittest.mock import MagicMock

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
