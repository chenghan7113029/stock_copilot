"""治理事件 / 北向资金 Repo SQLite 行为测试。"""

from __future__ import annotations

from dao.engine import Base, create_db_engine, make_session_factory
from dao.event_repo import (
    BlockTradeRepo,
    HolderTradeRepo,
    NorthboundFlowRepo,
    PledgeStatRepo,
    RepurchaseRepo,
    ShareFloatRepo,
)
from dao.models import (  # noqa: F401 — register ORM models
    BlockTrade,
    HolderTrade,
    NorthboundFlow,
    PledgeStat,
    Repurchase,
    ShareFloat,
)


def _session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_holder_trade_upsert_and_query_range() -> None:
    session = _session()
    try:
        repo = HolderTradeRepo(session)
        repo.upsert_batch(
            [
                {"code": "600519", "ann_date": "2026-09-01", "holder_name": "A", "in_de": "DE",
                 "change_vol": 100000.0, "change_ratio": 0.1},
                {"code": "600519", "ann_date": "2026-09-05", "holder_name": "B", "in_de": "IN",
                 "change_vol": 30000.0, "change_ratio": 0.03},
            ]
        )
        rows = repo.query_range("600519", 10)
        assert [r["ann_date"] for r in rows] == ["2026-09-01", "2026-09-05"]
        assert rows[-1]["in_de"] == "IN"

        # 全量刷新：重写同一 code，不产生重复
        repo.upsert_batch(
            [
                {"code": "600519", "ann_date": "2026-09-01", "holder_name": "A", "in_de": "DE",
                 "change_vol": 120000.0, "change_ratio": 0.12},
            ]
        )
        rows = repo.query_range("600519", 10)
        assert len(rows) == 1
        assert rows[0]["change_vol"] == 120000.0
    finally:
        session.close()


def test_repurchase_upsert_and_query_latest() -> None:
    session = _session()
    try:
        repo = RepurchaseRepo(session)
        repo.upsert_batch(
            [
                {"code": "600519", "ann_date": "2026-09-01", "proc": "实施", "vol": 1000.0, "amount": 1.0e7},
                {"code": "600519", "ann_date": "2026-09-10", "proc": "完成", "vol": 2000.0, "amount": 2.0e7},
            ]
        )
        latest = repo.query_latest("600519")
        assert latest["ann_date"] == "2026-09-10"
        assert latest["proc"] == "完成"
    finally:
        session.close()


def test_share_float_upsert_and_query_range() -> None:
    session = _session()
    try:
        repo = ShareFloatRepo(session)
        repo.upsert_batch(
            [
                {"code": "600519", "ann_date": "2026-09-01", "float_date": "2026-09-28",
                 "float_share": 1.0e6, "float_ratio": 0.8},
                {"code": "600519", "ann_date": "2026-09-02", "float_date": "2026-10-10",
                 "float_share": 2.0e6, "float_ratio": 1.6},
            ]
        )
        rows = repo.query_range("600519", 10)
        assert [r["float_date"] for r in rows] == ["2026-09-28", "2026-10-10"]
    finally:
        session.close()


def test_pledge_stat_query_latest_by_end_date() -> None:
    session = _session()
    try:
        repo = PledgeStatRepo(session)
        repo.upsert_batch(
            [
                {"code": "600519", "end_date": "2026-09-23", "pledge_ratio": 0.05,
                 "unrest_pledge": 70.0, "total_share": 125000.0},
                {"code": "600519", "end_date": "2026-09-24", "pledge_ratio": 0.06,
                 "unrest_pledge": 75.0, "total_share": 125008.0},
            ]
        )
        latest = repo.query_latest("600519")
        assert latest["end_date"] == "2026-09-24"
        assert latest["pledge_ratio"] == 0.06
    finally:
        session.close()


def test_block_trade_upsert_and_query_range() -> None:
    session = _session()
    try:
        repo = BlockTradeRepo(session)
        repo.upsert_batch(
            [
                {"code": "600519", "trade_date": "2026-08-31", "price": 1299.52,
                 "vol": 7.0, "amount": 9096.64, "discount": -2.5},
            ]
        )
        rows = repo.query_range("600519", 10)
        assert len(rows) == 1
        assert rows[0]["discount"] == -2.5
    finally:
        session.close()


def test_northbound_flow_upsert_and_query_northbound() -> None:
    session = _session()
    try:
        repo = NorthboundFlowRepo(session)
        repo.upsert_batch(
            [
                {"trade_date": "2026-09-22", "north_money": 100.0, "south_money": 50.0},
                {"trade_date": "2026-09-23", "north_money": -20.0, "south_money": 30.0},
                {"trade_date": "2026-09-24", "north_money": 80.0, "south_money": 40.0},
            ]
        )
        rows = repo.query_northbound(2)
        assert [r["trade_date"] for r in rows] == ["2026-09-23", "2026-09-24"]
        assert rows[-1]["north_money"] == 80.0
    finally:
        session.close()
