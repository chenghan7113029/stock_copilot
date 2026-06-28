"""StockDataProvider 离线重建测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.models import StockSnapshot
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.manager import SourceManager
from data_provider.provider import StockDataProvider


def _make_repo():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return StockSnapshotRepo(session), session


def _make_manager():
    ak = MagicMock()
    ak.source_name = "akshare"
    ak.priority = 1
    bs = MagicMock()
    bs.source_name = "baostock"
    bs.priority = 2
    return SourceManager([ak, bs])


def test_get_stock_data_offline_has_data():
    repo, session = _make_repo()
    session.add(
        StockSnapshot(
            code="600519",
            source="akshare",
            report_period="20250628",
            current_price=1800.0,
            eps=47.5,
            data_timestamp=datetime(2025, 6, 28, 9, 15),
        )
    )
    session.commit()

    provider = StockDataProvider(_make_manager(), repo=repo)
    stock = provider.get_stock_data_offline("600519")

    assert stock is not None
    assert stock.code == "600519"
    assert stock.current_price == 1800.0
    assert stock.eps == 47.5


def test_get_stock_data_offline_empty():
    repo, session = _make_repo()
    provider = StockDataProvider(_make_manager(), repo=repo)
    assert provider.get_stock_data_offline("600519") is None


def test_get_stock_data_offline_no_repo():
    provider = StockDataProvider(_make_manager(), repo=None)
    assert provider.get_stock_data_offline("600519") is None
