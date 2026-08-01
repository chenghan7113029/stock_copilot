"""ChipDistributionRepo SQLite 行为测试。"""

from __future__ import annotations

from dao.chip_distribution_repo import ChipDistributionRepo
from dao.engine import Base, create_db_engine, make_session_factory
from dao.models import ChipDistribution  # noqa: F401 — register ORM model


def _record(trade_date: str, winner_ratio: float) -> dict[str, float | str]:
    return {
        "code": "600519",
        "trade_date": trade_date,
        "winner_ratio": winner_ratio,
        "avg_cost": 12.34,
        "concentration_90": 8.2,
        "concentration_70": 4.1,
        "cost_90_low": 10.0,
        "cost_90_high": 14.0,
        "cost_70_low": 11.0,
        "cost_70_high": 13.0,
    }


def test_query_latest_returns_latest_trade_date_after_upsert() -> None:
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        repo = ChipDistributionRepo(session)
        repo.upsert_batch([_record("2026-07-30", 40.0), _record("2026-07-31", 42.5)])

        assert repo.query_latest("600519")["trade_date"] == "2026-07-31"
    finally:
        session.close()


def test_upsert_overwrites_existing_composite_key() -> None:
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        repo = ChipDistributionRepo(session)
        repo.upsert_batch([_record("2026-07-31", 40.0)])
        repo.upsert_batch([_record("2026-07-31", 55.0)])

        rows = repo.query_range("600519", "2026-07-01", "2026-07-31")
        assert len(rows) == 1
        assert rows[0]["winner_ratio"] == 55.0
    finally:
        session.close()
