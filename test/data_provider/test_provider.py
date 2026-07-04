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


def test_tushare_financials_override_baostock_estimates():
    """Tushare 财报字段应覆盖 Baostock 估算值。"""
    bs = MagicMock()
    bs.source_name = "baostock"
    bs.priority = 1
    bs.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={
            "current_price": 1400.0,
            "eps": 50.0,
            "shares_outstanding": 1_256_190_000.0,
            "revenue": 100_000_000_000.0,
            "fcf": 50_000_000_000.0,
        },
        missing_fields=[],
    )

    ts = MagicMock()
    ts.source_name = "tushare"
    ts.priority = 2
    ts.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={
            "revenue": 168_800_000_000.0,
            "fcf": 59_000_000_000.0,
            "total_assets": 303_800_000_000.0,
        },
        missing_fields=[],
    )

    manager = SourceManager([bs, ts])
    provider = StockDataProvider(manager)
    stock = provider.get_stock_data("600519")

    assert stock.revenue == 168_800_000_000.0
    assert stock.fcf == 59_000_000_000.0
    assert stock.field_sources["revenue"] == "tushare"
    assert stock.field_sources["fcf"] == "tushare"
    assert stock.current_price == 1400.0
    assert stock.field_sources["current_price"] == "baostock"


def test_get_stock_data_offline_picks_latest_fetched_per_source():
    """同 source 多 report_period 时，应取 fetched_at 最新的一条（含完整财报）。"""
    repo, session = _make_repo()
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20260628",
            current_price=1168.0,
            data_timestamp=datetime(2026, 6, 26),
            fetched_at=datetime(2026, 6, 28, 14, 0),
        )
    )
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20231231",
            revenue=168_800_000_000.0,
            total_assets=303_800_000_000.0,
            fcf=59_000_000_000.0,
            net_debt=-48_000_000_000.0,
            data_timestamp=datetime(2026, 7, 3),
            fetched_at=datetime(2026, 7, 4, 8, 33),
        )
    )
    session.commit()

    ts = MagicMock()
    ts.source_name = "tushare"
    ts.priority = 1
    provider = StockDataProvider(SourceManager([ts]), repo=repo)
    stock = provider.get_stock_data_offline("600519")

    assert stock.revenue == 168_800_000_000.0
    assert stock.total_assets == 303_800_000_000.0
    assert stock.fcf == 59_000_000_000.0
