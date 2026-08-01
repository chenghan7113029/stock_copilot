from datetime import datetime
from unittest.mock import MagicMock

from service.sentiment.analyzer import SentimentAnalyzer
from service.sentiment.models.sentiment_result import SentimentStatus


def test_analyze_offline_returns_deterministic_result() -> None:
    snapshot = MagicMock(
        limit_up_count=50,
        limit_down_count=10,
        margin_balance_change_pct=1.0,
        turnover_percentile=60.0,
        fetched_at=datetime(2026, 8, 1),
    )
    provider = MagicMock()
    provider.get_latest_offline.return_value = snapshot

    result = SentimentAnalyzer(provider).analyze_offline("600519")

    assert result is not None
    assert result.code == "600519"
    assert result.limit_updown_ratio == 50 / 60
    assert result.market_sentiment_status in SentimentStatus
    provider.fetch_and_persist_today.assert_not_called()


def test_analyze_offline_returns_none_without_snapshot() -> None:
    provider = MagicMock()
    provider.get_latest_offline.return_value = None

    assert SentimentAnalyzer(provider).analyze_offline("600519") is None
