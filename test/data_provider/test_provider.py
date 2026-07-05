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
    """同 source 多 report_period：行情取 fetched_at 最新，财报取年报。"""
    repo, session = _make_repo()
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20260628",
            current_price=1168.0,
            data_timestamp=datetime(2026, 6, 26),
            fetched_at=datetime(2026, 7, 4, 10, 0),
        )
    )
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20251231",
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

    assert stock.current_price == 1168.0
    assert stock.revenue == 168_800_000_000.0
    assert stock.total_assets == 303_800_000_000.0
    assert stock.fcf == 59_000_000_000.0


def test_offline_financials_prefer_annual_over_newer_quarterly():
    """Q1 快照 fetched_at 更新但 FCF 应取年报值。"""
    repo, session = _make_repo()
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20260331",
            current_price=1194.45,
            fcf=263_050_000_000.0,
            revenue=168_800_000_000.0,
            fetched_at=datetime(2026, 7, 4, 9, 19),
        )
    )
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20251231",
            fcf=583_946_000_000.0,
            revenue=168_800_000_000.0,
            total_assets=303_800_000_000.0,
            fetched_at=datetime(2026, 7, 4, 8, 35),
        )
    )
    session.commit()

    provider = StockDataProvider(
        SourceManager([MagicMock(source_name="tushare", priority=1)]),
        repo=repo,
    )
    stock = provider.get_stock_data_offline("600519")

    assert stock.current_price == 1194.45
    assert stock.fcf == 583_946_000_000.0
    assert stock.field_sources["fcf"] == "tushare"


def test_offline_baostock_does_not_override_tushare_annual_fcf():
    """低优先级 Baostock 估算 FCF 不得覆盖 Tushare 年报 FCF。"""
    repo, session = _make_repo()
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20260331",
            current_price=1194.45,
            fcf=263_050_000_000.0,
            net_income=82_320_000_000.0,
            shares_outstanding=1_250_800_000.0,
            fetched_at=datetime(2026, 7, 4, 9, 19),
        )
    )
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20251231",
            fcf=583_946_000_000.0,
            net_income=82_320_000_000.0,
            revenue=168_800_000_000.0,
            fetched_at=datetime(2026, 7, 4, 8, 35),
        )
    )
    session.add(
        StockSnapshot(
            code="600519",
            source="baostock",
            report_period="20260704",
            fcf=239_307_567_664.0,
            net_income=281_538_314_898.9,
            fetched_at=datetime(2026, 7, 4, 9, 20),
        )
    )
    session.commit()

    manager = SourceManager([
        MagicMock(source_name="tushare", priority=1),
        MagicMock(source_name="baostock", priority=2),
    ])
    provider = StockDataProvider(manager, repo=repo)
    stock = provider.get_stock_data_offline("600519")

    assert stock.fcf == 583_946_000_000.0
    assert stock.field_sources["fcf"] == "tushare"
    assert abs(stock.eps - 65.84) < 0.1


def test_ttm_eps_derived_from_net_income():
    """年报净利润 / 总股本应覆写 fina_indicator 单季 EPS。"""
    fetcher = MagicMock()
    fetcher.source_name = "tushare"
    fetcher.priority = 1
    fetcher.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={
            "eps": 21.76,
            "net_income": 82_320_000_000.0,
            "shares_outstanding": 1_250_800_000.0,
        },
        missing_fields=[],
    )

    provider = StockDataProvider(SourceManager([fetcher]))
    stock = provider.get_stock_data("600519")

    assert stock.eps == 82_320_000_000.0 / 1_250_800_000.0
    assert abs(stock.eps - 65.84) < 0.1
    assert stock.field_sources["eps"] == "derived:ttm"


def test_ttm_eps_not_derived_when_net_income_missing():
    fetcher = MagicMock()
    fetcher.source_name = "tushare"
    fetcher.priority = 1
    fetcher.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={"eps": 21.76},
        missing_fields=[],
    )

    provider = StockDataProvider(SourceManager([fetcher]))
    stock = provider.get_stock_data("600519")

    assert stock.eps == 21.76
    assert stock.field_sources.get("eps") == "tushare"


def test_offline_historical_pb_from_snapshot():
    """离线重建应读取 historical_pb_json。"""
    import json

    repo, session = _make_repo()
    pb_series = [8.5, 8.2, 7.9, 7.5, 7.2, 7.0, 6.8, 6.5, 6.3, 6.0, 5.8, 5.5]
    session.add(
        StockSnapshot(
            code="600519",
            source="tushare",
            report_period="20251231",
            current_price=1400.0,
            eps=65.0,
            bvps=180.0,
            historical_pb_json=json.dumps(pb_series),
            data_timestamp=datetime(2025, 12, 31, 9, 15),
        )
    )
    session.commit()

    provider = StockDataProvider(_make_manager(), repo=repo)
    stock = provider.get_stock_data_offline("600519")

    assert stock is not None
    assert stock.historical_pb is not None
    assert len(stock.historical_pb) >= 10
    assert stock.field_sources["historical_pb"] == "tushare"


def test_tushare_historical_pe_not_overridden_by_baostock():
    """Tushare 5 年 historical_pe 不应被 Baostock 2 年覆盖。"""
    ts_pe = [30.0 - i * 0.5 for i in range(15)]
    bs_pe = [28.0, 27.0, 26.0, 25.0, 24.0, 23.0, 22.0, 21.0]

    ts = MagicMock()
    ts.source_name = "tushare"
    ts.priority = 1
    ts.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={"current_price": 1400.0, "historical_pe": ts_pe},
        missing_fields=[],
    )
    bs = MagicMock()
    bs.source_name = "baostock"
    bs.priority = 2
    bs.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={"current_price": 1401.0, "historical_pe": bs_pe},
        missing_fields=[],
    )

    provider = StockDataProvider(SourceManager([ts, bs]))
    stock = provider.get_stock_data("600519")

    assert stock.historical_pe == ts_pe
    assert stock.field_sources["historical_pe"] == "tushare"


def test_baostock_historical_pe_fallback_when_tushare_missing():
    """Tushare 无 historical_pe 时 Baostock fallback 生效。"""
    bs_pe = [28.0, 27.0, 26.0, 25.0, 24.0, 23.0, 22.0, 21.0]
    ts = MagicMock()
    ts.source_name = "tushare"
    ts.priority = 1
    ts.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={"current_price": 1400.0},
        missing_fields=["historical_pe"],
    )
    bs = MagicMock()
    bs.source_name = "baostock"
    bs.priority = 2
    bs.fetch_all.return_value = MagicMock(
        ok=True,
        error=None,
        data={"current_price": 1401.0, "historical_pe": bs_pe},
        missing_fields=[],
    )

    provider = StockDataProvider(SourceManager([ts, bs]))
    stock = provider.get_stock_data("600519")

    assert stock.historical_pe == bs_pe
    assert stock.field_sources["historical_pe"] == "baostock"
