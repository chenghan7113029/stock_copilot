"""TopListProvider 单元测试（mock Tushare 返回值，不联网）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from dao.engine import Base, create_db_engine, make_session_factory
from dao.top_list_repo import (
    StockTopInstRepo,
    StockTopListRepo,
    TopListSyncMarkerRepo,
)
from data_provider.toplist.provider import TopListProvider, TopListRepos


def _top_list_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-10-08", "2026-10-08", "2026-10-08"],
            "code": ["000678", "000678", "300530"],
            "name": ["襄阳轴承", "襄阳轴承", "宜通世纪"],
            "close": [12.24, 12.24, 8.0],
            "pct_change": [-5.04, -5.04, 15.0],
            "turnover_rate": [28.23, 28.23, 12.0],
            "amount": [1.68e9, 1.68e9, 5.0e8],
            "l_sell": [3.18e8, 3.18e8, 2.7e7],
            "l_buy": [2.33e8, 2.33e8, 1.04e8],
            "l_amount": [5.51e8, 5.51e8, 1.31e8],
            "net_amount": [-8.54e7, -8.54e7, 7.68e7],
            "net_rate": [-5.07, -5.07, 58.0],
            "amount_rate": [32.69, 32.69, 26.0],
            "float_values": [5.63e9, 5.63e9, 2.4e9],
            "reason": [
                "日振幅值达到15%的前5只证券",
                "日换手率达到20%的前5只证券",
                "日涨幅达到15%的前5只证券",
            ],
        }
    )


def _top_inst_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-10-08", "2026-10-08"],
            "code": ["000678", "000678"],
            "exalter": ["机构专用", "机构专用"],
            "side": ["0", "1"],
            "buy": [3.6e7, 1.2e7],
            "buy_rate": [3.4, 1.1],
            "sell": [2.2e7, 2.3e7],
            "sell_rate": [2.1, 2.2],
            "net_buy": [1.4e7, -1.1e7],
            "reason": ["日振幅值达到15%的前5只证券", "日振幅值达到15%的前5只证券"],
        }
    )


def _make_session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def _repos(session) -> TopListRepos:
    return TopListRepos(
        top_list=StockTopListRepo(session),
        top_inst=StockTopInstRepo(session),
        marker=TopListSyncMarkerRepo(session),
    )


def _fetcher(*, inst_error: Exception | None = None, empty: bool = False) -> MagicMock:
    fetcher = MagicMock()
    fetcher.source_name = "tushare"
    fetcher.latest_trade_date.return_value = "20261008"
    fetcher.recent_trade_dates.return_value = ["2026-10-08", "2026-10-09"]
    fetcher.fetch_top_list.return_value = pd.DataFrame() if empty else _top_list_df()
    if inst_error is not None:
        fetcher.fetch_top_inst.side_effect = inst_error
    else:
        fetcher.fetch_top_inst.return_value = _top_inst_df()
    return fetcher


def test_sync_trade_date_persists_market_wide_rows() -> None:
    session = _make_session()
    repos = _repos(session)
    provider = TopListProvider(repos, fetchers=[_fetcher()])
    try:
        warnings = provider.sync_trade_date("2026-10-08")
        session.commit()

        assert warnings == []
        # 全市场落库：不同股票都入库
        assert repos.top_list.count_day_rows("2026-10-08") == 3
        assert len(repos.top_list.query_range("300530", "2026-07-10")) == 1
        assert repos.top_inst.count_day_rows("2026-10-08") == 2
        assert repos.marker.has("2026-10-08") is True
    finally:
        session.close()


def test_sync_trade_date_empty_result_does_not_write_marker() -> None:
    session = _make_session()
    repos = _repos(session)
    provider = TopListProvider(repos, fetchers=[_fetcher(empty=True)])
    try:
        warnings = provider.sync_trade_date("2026-10-08")
        session.commit()

        assert repos.top_list.count_day_rows("2026-10-08") == 0
        assert repos.marker.has("2026-10-08") is False
        assert any("无榜单数据" in w for w in warnings)
    finally:
        session.close()


def test_top_inst_failure_degrades_but_keeps_top_list() -> None:
    session = _make_session()
    repos = _repos(session)
    provider = TopListProvider(
        repos, fetchers=[_fetcher(inst_error=RuntimeError("permission denied"))]
    )
    try:
        warnings = provider.sync_trade_date("2026-10-08")
        session.commit()

        assert repos.top_list.count_day_rows("2026-10-08") == 3
        assert repos.top_inst.count_day_rows("2026-10-08") == 0
        assert repos.marker.has("2026-10-08") is True
        assert any("机构席位接口不可用" in w for w in warnings)
    finally:
        session.close()


def test_sync_trade_date_is_idempotent() -> None:
    session = _make_session()
    repos = _repos(session)
    provider = TopListProvider(repos, fetchers=[_fetcher()])
    try:
        provider.sync_trade_date("2026-10-08")
        provider.sync_trade_date("2026-10-08")
        session.commit()

        assert repos.top_list.count_day_rows("2026-10-08") == 3
        assert repos.top_inst.count_day_rows("2026-10-08") == 2
        assert repos.marker.count() == 1
    finally:
        session.close()


def test_no_fetchers_returns_warning() -> None:
    session = _make_session()
    provider = TopListProvider(_repos(session), fetchers=[])
    try:
        warnings = provider.sync_trade_date("2026-10-08")
        assert any("无可用数据源" in w for w in warnings)

        day, warnings_latest = provider.sync_latest()
        assert day is None
        assert any("无可用数据源" in w for w in warnings_latest)
    finally:
        session.close()


def test_sync_latest_skips_when_already_covered() -> None:
    session = _make_session()
    repos = _repos(session)
    fetcher = _fetcher()
    provider = TopListProvider(repos, fetchers=[fetcher])
    try:
        provider.sync_trade_date("2026-10-08")
        session.commit()
        fetcher.fetch_top_list.reset_mock()

        day, warnings = provider.sync_latest()

        assert day == "2026-10-08"
        assert warnings == []
        fetcher.fetch_top_list.assert_not_called()
    finally:
        session.close()


def test_offline_reads_records_and_coverage_without_network() -> None:
    session = _make_session()
    repos = _repos(session)
    fetcher = _fetcher()
    provider = TopListProvider(repos, fetchers=[fetcher])
    try:
        provider.sync_trade_date("2026-10-08")
        session.commit()
        fetcher.fetch_top_list.reset_mock()

        data = provider.get_offline("000678", 90)

        assert data is not None
        assert len(data.list_records) == 2
        assert len(data.inst_records) == 2
        assert data.covered_dates == ["2026-10-08"]
        fetcher.fetch_top_list.assert_not_called()
    finally:
        session.close()


def test_offline_absent_stock_with_coverage_is_not_none() -> None:
    """未上榜（有水位）→ 返回数据，appearance 计数为 0；完全未拉取 → None。"""
    session = _make_session()
    repos = _repos(session)
    provider = TopListProvider(repos, fetchers=[_fetcher()])
    try:
        assert provider.get_offline("600519", 90) is None

        provider.sync_trade_date("2026-10-08")
        session.commit()

        data = provider.get_offline("600519", 90)
        assert data is not None
        assert data.list_records == []
        assert data.covered_dates == ["2026-10-08"]
    finally:
        session.close()


def test_from_config_builds_fetcher_when_tushare_enabled() -> None:
    session = _make_session()
    config = {
        "data_sources": {
            "enabled": [{"name": "tushare", "priority": 1, "token": "test-token"}]
        }
    }
    with patch(
        "data_provider.toplist.provider.TushareTopListFetcher"
    ) as mock_fetcher_cls:
        provider = TopListProvider.from_config(config, _repos(session))
        mock_fetcher_cls.assert_called_once_with(token="test-token")
        assert provider._fetchers == [mock_fetcher_cls.return_value]
    session.close()


def test_from_config_no_fetchers_when_tushare_disabled() -> None:
    session = _make_session()
    provider = TopListProvider.from_config({}, _repos(session))
    assert provider._fetchers == []
    session.close()
