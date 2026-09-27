"""StockMarginDetailRepo / StockMoneyFlowRepo SQLite 行为测试。"""

from __future__ import annotations

from dao.engine import Base, create_db_engine, make_session_factory
from dao.fund_flow_repo import StockMarginDetailRepo, StockMoneyFlowRepo
from dao.models import StockMarginDetail, StockMoneyFlow  # noqa: F401 — register ORM models


def _margin_record(trade_date: str, rzrqye: float) -> dict:
    return {
        "code": "600519",
        "trade_date": trade_date,
        "rzye": 100.0,
        "rqye": 10.0,
        "rzrqye": rzrqye,
        "rzmre": 50.0,
        "rzche": 40.0,
        "rqyl": 1000.0,
        "rqmcl": 200.0,
    }


def _moneyflow_record(trade_date: str, net_mf_amount: float) -> dict:
    return {
        "code": "600519",
        "trade_date": trade_date,
        "net_mf_amount": net_mf_amount,
        "buy_elg_amount": 100.0,
        "sell_elg_amount": 50.0,
        "buy_lg_amount": 80.0,
        "sell_lg_amount": 60.0,
    }


def _make_session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_margin_upsert_new_and_query_latest() -> None:
    session = _make_session()
    try:
        repo = StockMarginDetailRepo(session)
        repo.upsert_batch(
            [_margin_record("2026-07-30", 100.0), _margin_record("2026-07-31", 110.0)]
        )
        assert repo.query_latest("600519")["trade_date"] == "2026-07-31"
    finally:
        session.close()


def test_margin_query_latest_empty_table() -> None:
    session = _make_session()
    try:
        repo = StockMarginDetailRepo(session)
        assert repo.query_latest("600519") is None
    finally:
        session.close()


def test_margin_upsert_overwrites_existing_composite_key() -> None:
    session = _make_session()
    try:
        repo = StockMarginDetailRepo(session)
        repo.upsert_batch([_margin_record("2026-07-31", 100.0)])
        repo.upsert_batch([_margin_record("2026-07-31", 120.0)])

        rows = repo.query_range("600519", 5)
        assert len(rows) == 1
        assert rows[0]["rzrqye"] == 120.0
    finally:
        session.close()


def test_margin_query_range_returns_recent_trade_days_ascending() -> None:
    session = _make_session()
    try:
        repo = StockMarginDetailRepo(session)
        dates = ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
        repo.upsert_batch([_margin_record(d, float(i)) for i, d in enumerate(dates)])

        rows = repo.query_range("600519", 3)
        assert [r["trade_date"] for r in rows] == ["2026-07-29", "2026-07-30", "2026-07-31"]
    finally:
        session.close()


def test_moneyflow_upsert_and_query_latest() -> None:
    session = _make_session()
    try:
        repo = StockMoneyFlowRepo(session)
        repo.upsert_batch(
            [
                _moneyflow_record("2026-07-30", 100.0),
                _moneyflow_record("2026-07-31", -50.0),
            ]
        )
        latest = repo.query_latest("600519")
        assert latest["trade_date"] == "2026-07-31"
        assert latest["net_mf_amount"] == -50.0
    finally:
        session.close()
