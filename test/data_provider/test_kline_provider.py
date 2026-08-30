"""KlineProvider offline / persist_today 测试。"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd

from data_provider.kline_provider import KlineProvider


def test_offline_mode_reads_cache_only():
    cached = [
        {
            "code": "600519",
            "trade_date": "2025-06-01",
            "date": "2025-06-01",
            "open": 10.0,
            "high": 10.5,
            "low": 9.5,
            "close": 10.2,
            "volume": 1_000_000.0,
        }
    ]
    repo = MagicMock()
    repo.query_range.return_value = cached
    baostock = MagicMock()
    provider = KlineProvider(repo, baostock_fetcher=baostock, akshare_fetcher=MagicMock())

    df, warnings, quote_mode = provider.get_kline("600519", days=90, offline=True)

    assert not df.empty
    assert quote_mode == "eod"
    baostock.fetch_kline.assert_not_called()


def test_offline_mode_empty_cache():
    repo = MagicMock()
    repo.query_range.return_value = []
    provider = KlineProvider(repo, baostock_fetcher=MagicMock(), akshare_fetcher=MagicMock())

    df, warnings, quote_mode = provider.get_kline("600519", days=90, offline=True)

    assert df.empty
    assert quote_mode == "eod"
    assert any("无K线缓存" in w for w in warnings)


def test_persist_today_writes_row():
    repo = MagicMock()
    repo.query_range.return_value = []
    today = date.today().strftime("%Y-%m-%d")
    df_api = pd.DataFrame(
        {
            "date": [today],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "volume": [1_000_000.0],
        }
    )
    baostock = MagicMock()
    baostock.fetch_kline.return_value = df_api

    overlay = MagicMock()
    overlay.overlay.return_value = (df_api, "realtime", [])

    provider = KlineProvider(
        repo,
        baostock_fetcher=baostock,
        akshare_fetcher=MagicMock(),
        realtime_overlay=overlay,
    )
    provider.get_kline("600519", days=90, use_realtime=True, persist_today=True)

    repo.upsert_batch.assert_called()
    upserted = repo.upsert_batch.call_args[0][0]
    assert upserted[-1]["trade_date"] == today


def test_skips_akshare_fallback_when_disabled():
    repo = MagicMock()
    repo.query_range.return_value = []
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = RuntimeError("baostock down")
    akshare = MagicMock()

    provider = KlineProvider(
        repo,
        baostock_fetcher=baostock,
        akshare_fetcher=akshare,
        use_akshare=False,
    )

    try:
        provider.get_kline("600519", days=90)
        raised = False
    except Exception:
        raised = True

    assert raised
    akshare.fetch_kline.assert_not_called()


def test_realtime_falls_back_when_akshare_disabled():
    cached = [
        {
            "code": "600519",
            "trade_date": "2025-06-01",
            "date": "2025-06-01",
            "open": 10.0,
            "high": 10.5,
            "low": 9.5,
            "close": 10.2,
            "volume": 1_000_000.0,
        }
    ]
    repo = MagicMock()
    repo.query_range.return_value = cached
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = RuntimeError("skip api")

    provider = KlineProvider(repo, baostock_fetcher=baostock, use_akshare=False)
    df, warnings, quote_mode = provider.get_kline("600519", days=90, use_realtime=True)

    assert not df.empty
    assert quote_mode == "eod_fallback"
    assert any("实时" in w or "EOD" in w for w in warnings)


def test_failover_uses_second_source_when_first_fails():
    repo = MagicMock()
    repo.query_range.return_value = []
    today = date.today().strftime("%Y-%m-%d")
    df_api = pd.DataFrame(
        {
            "date": [today],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "volume": [1_000_000.0],
        }
    )
    first = MagicMock()
    first.fetch_kline.side_effect = RuntimeError("down")
    second = MagicMock()
    second.fetch_kline.return_value = df_api

    provider = KlineProvider(
        repo,
        kline_fetchers=[(first, "baostock"), (second, "akshare")],
        realtime_overlay=None,
    )
    df, warnings, quote_mode = provider.get_kline("600519", days=90)
    assert not df.empty
    assert quote_mode == "eod"
    first.fetch_kline.assert_called()
    second.fetch_kline.assert_called()


def test_failover_baostock_fails_tushare_succeeds():
    """Baostock 失败时 Tushare 可独立完成 K 线拉取并写入缓存（Issue #1）。"""
    repo = MagicMock()
    hist_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    today = date.today().strftime("%Y-%m-%d")
    df_api = pd.DataFrame(
        {
            "date": [hist_date, today],
            "open": [10.0, 10.1],
            "high": [10.5, 10.6],
            "low": [9.5, 9.6],
            "close": [10.2, 10.3],
            "volume": [1_000_000.0, 1_100_000.0],
        }
    )
    baostock = MagicMock()
    baostock.fetch_kline.side_effect = RuntimeError("baostock down")
    tushare = MagicMock()
    tushare.fetch_kline.return_value = df_api

    def _query_after_upsert(code, start, end):
        if repo.upsert_batch.called:
            return [
                {
                    "code": "600519",
                    "trade_date": hist_date,
                    "date": hist_date,
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.5,
                    "close": 10.2,
                    "volume": 1_000_000.0,
                }
            ]
        return []

    repo.query_range.side_effect = _query_after_upsert

    provider = KlineProvider(
        repo,
        kline_fetchers=[(baostock, "baostock"), (tushare, "tushare")],
        realtime_overlay=None,
    )
    df, warnings, quote_mode = provider.get_kline("600519", days=90)

    assert not df.empty
    assert quote_mode == "eod"
    baostock.fetch_kline.assert_called()
    tushare.fetch_kline.assert_called()
    repo.upsert_batch.assert_called()
    upserted = repo.upsert_batch.call_args[0][0]
    assert any(r["trade_date"] == hist_date for r in upserted)
    assert provider._last_kline_source == "tushare"


def test_from_config_baostock_only_does_not_build_akshare(monkeypatch):
    created: list[str] = []

    class _FakeBS:
        source_name = "baostock"
        priority = 1

        def fetch_kline(self, *args, **kwargs):
            raise RuntimeError("no net")

    def fake_build(name, priority_override, src=None, config=None):
        created.append(name)
        if name == "baostock":
            return _FakeBS()
        raise AssertionError(f"should not build {name}")

    monkeypatch.setattr(
        "data_provider.router.DataFetcherRouter.build_fetcher",
        staticmethod(fake_build),
    )
    repo = MagicMock()
    cfg = {"data_sources": {"enabled": [{"name": "baostock", "priority": 1}]}}
    provider = KlineProvider.from_config(cfg, repo)
    assert created == ["baostock"]
    assert all(name != "akshare" for _, name in provider._kline_sources)


def test_as_of_overrides_wall_clock_window():
    """显式 as_of 决定 query_range 窗口，不跟随墙钟。"""
    repo = MagicMock()
    repo.query_range.return_value = []
    provider = KlineProvider(repo, baostock_fetcher=MagicMock(), akshare_fetcher=MagicMock())

    provider.get_kline("600519", days=90, offline=True, as_of="2026-08-10")

    repo.query_range.assert_called_once_with("600519", "2026-05-12", "2026-08-10")


def test_as_of_stable_when_today_mocked(monkeypatch):
    """固定 as_of 时，伪造不同 today 仍查询同一窗口。"""
    repo = MagicMock()
    repo.query_range.return_value = []
    provider = KlineProvider(repo, baostock_fetcher=MagicMock(), akshare_fetcher=MagicMock())

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return date(2099, 1, 1)

    monkeypatch.setattr("data_provider.kline_provider.date", _FakeDate)

    provider.get_kline("600519", days=90, offline=True, as_of="2026-08-10")
    assert repo.query_range.call_args.args == ("600519", "2026-05-12", "2026-08-10")
