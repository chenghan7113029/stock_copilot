"""EventProvider 单元测试（mock Tushare 返回值）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from dao.engine import Base, create_db_engine, make_session_factory
from dao.event_repo import (
    BlockTradeRepo,
    HolderTradeRepo,
    NorthboundFlowRepo,
    PledgeStatRepo,
    RepurchaseRepo,
    ShareFloatRepo,
)
from data_provider.event.provider import EventProvider, EventRepos


def _session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def _repos(session) -> EventRepos:
    return EventRepos(
        holder_trade=HolderTradeRepo(session),
        repurchase=RepurchaseRepo(session),
        share_float=ShareFloatRepo(session),
        pledge_stat=PledgeStatRepo(session),
        block_trade=BlockTradeRepo(session),
        northbound=NorthboundFlowRepo(session),
    )


def _fetcher(*, fail: str | None = None) -> MagicMock:
    f = MagicMock()
    f.source_name = "tushare"
    f.fetch_holder_trade.return_value = pd.DataFrame(
        {"ann_date": ["2026-09-01"], "holder_name": ["A"], "holder_type": ["C"],
         "in_de": ["DE"], "change_vol": [100000.0], "change_ratio": [0.1]}
    )
    f.fetch_repurchase.return_value = pd.DataFrame(
        {"ann_date": ["2026-09-01"], "proc": ["实施"], "vol": [1000.0], "amount": [1.0e7]}
    )
    f.fetch_share_float.return_value = pd.DataFrame(
        {"ann_date": ["2026-09-01"], "float_date": ["2026-09-28"],
         "float_share": [1.0e6], "float_ratio": [0.8]}
    )
    f.fetch_pledge_stat.return_value = pd.DataFrame(
        {"end_date": ["2026-09-24"], "pledge_ratio": [0.06],
         "unrest_pledge": [75.0], "total_share": [125008.0]}
    )
    f.fetch_block_trade.return_value = pd.DataFrame(
        {"trade_date": ["2026-08-31"], "price": [1299.52], "vol": [7.0],
         "amount": [9096.64], "discount": [-2.5]}
    )
    f.fetch_northbound_flow.return_value = pd.DataFrame(
        {"trade_date": ["2026-09-24"], "north_money": ["232511.99"], "south_money": ["55373.77"]}
    )
    if fail == "block_trade":
        f.fetch_block_trade.side_effect = RuntimeError("block_trade down")
    return f


def test_sync_all_success() -> None:
    session = _session()
    provider = EventProvider(_repos(session), fetchers=[_fetcher()])
    try:
        warnings = provider.sync("600519")
        assert warnings == []
        data = provider.get_latest_offline("600519")
        assert data is not None
        assert len(data.holder_trade_records) == 1
        assert len(data.block_trade_records) == 1
        assert data.pledge_records[-1]["pledge_ratio"] == 0.06
    finally:
        session.close()


def test_sync_partial_failure_keeps_others() -> None:
    session = _session()
    provider = EventProvider(_repos(session), fetchers=[_fetcher(fail="block_trade")])
    try:
        warnings = provider.sync("600519")
        assert any("大宗" in w for w in warnings)
        data = provider.get_latest_offline("600519")
        assert data is not None
        assert len(data.holder_trade_records) == 1
        assert data.block_trade_records == []
    finally:
        session.close()


def test_get_latest_offline_no_cache_returns_none() -> None:
    session = _session()
    provider = EventProvider(_repos(session), fetchers=[])
    try:
        assert provider.get_latest_offline("600519") is None

        data, warnings = provider.get_latest("600519", offline=True)
        assert data is None
        assert any("无治理事件缓存" in w for w in warnings)
    finally:
        session.close()


def test_fetch_northbound_flow_persists() -> None:
    session = _session()
    provider = EventProvider(_repos(session), fetchers=[_fetcher()])
    try:
        warnings = provider.fetch_northbound_flow()
        assert warnings == []
        rows = _repos(session).northbound.query_northbound(5)
        assert len(rows) == 1
        assert rows[0]["north_money"] == 232511.99
    finally:
        session.close()
