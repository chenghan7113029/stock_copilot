"""FundFlowProvider 单元测试（mock Tushare 返回值）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from dao.engine import Base, create_db_engine, make_session_factory
from dao.fund_flow_repo import StockMarginDetailRepo, StockMoneyFlowRepo
from data_provider.fundflow.provider import FundFlowProvider, FundFlowRepos


def _margin_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-09-23", "2026-09-24"],
            "rzye": [1.0e8, 1.1e8],
            "rqye": [1.0e6, 1.1e6],
            "rzrqye": [1.01e8, 1.111e8],
            "rzmre": [1.0e7, 1.1e7],
            "rzche": [9.0e6, 9.5e6],
            "rqyl": [1000.0, 1100.0],
            "rqmcl": [100.0, 120.0],
        }
    )


def _moneyflow_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-09-23", "2026-09-24"],
            "net_mf_amount": [1000.0, -200.0],
            "buy_elg_amount": [5000.0, 6000.0],
            "sell_elg_amount": [4000.0, 5000.0],
            "buy_lg_amount": [3000.0, 3500.0],
            "sell_lg_amount": [2000.0, 2500.0],
        }
    )


def _make_session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def _repos(session) -> FundFlowRepos:
    return FundFlowRepos(
        margin=StockMarginDetailRepo(session),
        moneyflow=StockMoneyFlowRepo(session),
    )


def _fetcher(*, moneyflow_error=None) -> MagicMock:
    fetcher = MagicMock()
    fetcher.source_name = "tushare"
    fetcher.fetch_margin_detail.return_value = _margin_df()
    if moneyflow_error is not None:
        fetcher.fetch_moneyflow.side_effect = moneyflow_error
    else:
        fetcher.fetch_moneyflow.return_value = _moneyflow_df()
    return fetcher


def test_get_latest_online_success_persists_and_reads_back() -> None:
    session = _make_session()
    provider = FundFlowProvider(_repos(session), fetchers=[_fetcher()])
    try:
        data, warnings = provider.get_latest("600519")

        assert data is not None
        assert warnings == []
        assert [r["trade_date"] for r in data.margin_records] == ["2026-09-23", "2026-09-24"]
        assert data.margin_records[-1]["rzrqye"] == 1.111e8
        assert len(data.moneyflow_records) == 2
        assert data.moneyflow_records[-1]["net_mf_amount"] == -200.0
    finally:
        session.close()


def test_get_latest_single_interface_failure_degrades() -> None:
    session = _make_session()
    provider = FundFlowProvider(
        _repos(session), fetchers=[_fetcher(moneyflow_error=RuntimeError("moneyflow down"))]
    )
    try:
        data, warnings = provider.get_latest("600519")

        assert data is not None
        assert len(data.margin_records) == 2
        assert data.moneyflow_records == []
        assert any("moneyflow" in w for w in warnings)
    finally:
        session.close()


def test_get_latest_offline_no_cache_returns_none() -> None:
    session = _make_session()
    provider = FundFlowProvider(_repos(session), fetchers=[])
    try:
        assert provider.get_latest_offline("600519") is None

        data, warnings = provider.get_latest("600519", offline=True)
        assert data is None
        assert any("无资金面缓存" in w for w in warnings)
    finally:
        session.close()


def test_get_latest_offline_reads_cache_without_network() -> None:
    session = _make_session()
    fetcher = _fetcher()
    provider = FundFlowProvider(_repos(session), fetchers=[fetcher])
    try:
        provider.get_latest("600519")  # 联网填充缓存

        data = provider.get_latest_offline("600519")

        assert data is not None
        assert len(data.margin_records) == 2
        fetcher.fetch_margin_detail.assert_called_once()
        fetcher.fetch_moneyflow.assert_called_once()
    finally:
        session.close()


def test_from_config_builds_tushare_fetcher_when_enabled() -> None:
    session = _make_session()
    config = {"data_sources": {"enabled": [{"name": "tushare", "priority": 1, "token": "test-token"}]}}
    with patch("data_provider.fundflow.provider.TushareFundFlowFetcher") as mock_fetcher_cls:
        provider = FundFlowProvider.from_config(config, _repos(session))
        mock_fetcher_cls.assert_called_once_with(token="test-token")
        assert provider._fetchers == [mock_fetcher_cls.return_value]
    session.close()


def test_from_config_no_fetchers_when_tushare_disabled() -> None:
    session = _make_session()
    provider = FundFlowProvider.from_config({}, _repos(session))
    assert provider._fetchers == []
    session.close()
