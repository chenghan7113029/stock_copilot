from dao.engine import Base, create_db_engine, make_session_factory
from dao.market_sentiment_repo import MarketSentimentRepo
from dao.models import MarketSentimentSnapshot  # noqa: F401


def _snapshot(trade_date: str, limit_up_count: int = 50) -> dict:
    return {
        "trade_date": trade_date,
        "limit_up_count": limit_up_count,
        "limit_down_count": 10,
        "up_count": 3000,
        "down_count": 1000,
        "margin_balance_change_pct": 1.2,
        "turnover_percentile": 60.0,
        "fear_greed_index": 70.0,
    }


def test_upsert_creates_and_updates_snapshot() -> None:
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        repo = MarketSentimentRepo(session)
        repo.upsert(_snapshot("2026-08-01", 50))
        repo.upsert(_snapshot("2026-08-01", 80))

        row = repo.get_by_date("2026-08-01")
        assert row is not None
        assert row.limit_up_count == 80
    finally:
        session.close()


def test_get_latest_handles_empty_and_multiple_records() -> None:
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        repo = MarketSentimentRepo(session)
        assert repo.get_latest() is None

        repo.upsert(_snapshot("2026-07-31"))
        repo.upsert(_snapshot("2026-08-01"))
        assert repo.get_latest().trade_date == "2026-08-01"
    finally:
        session.close()
