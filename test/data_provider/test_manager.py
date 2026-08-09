"""SourceManager 和 StockDataProvider 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from common.exceptions import DataProviderError, UnsupportedMarketError
from data_provider.base import BaseFetcher, FetchResult
from data_provider.manager import SourceManager
from data_provider.provider import StockDataProvider

# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _make_fetcher(name: str, priority: int, result: FetchResult) -> BaseFetcher:
    f = MagicMock(spec=BaseFetcher)
    f.source_name = name
    f.priority = priority
    f.fetch_all.return_value = result
    f.fetch_quote.return_value = result
    f.fetch_fundamentals.return_value = result
    return f


def _ok_result(code: str, source: str, **data) -> FetchResult:
    return FetchResult(code=code, source=source, data=data)


def _err_result(code: str, source: str) -> FetchResult:
    return FetchResult(code=code, source=source, error="network error")


# ── SourceManager 测试 ────────────────────────────────────────────────────────

def test_fetchers_sorted_by_priority():
    f1 = _make_fetcher("baostock", 2, _ok_result("600519", "baostock"))
    f2 = _make_fetcher("akshare", 1, _ok_result("600519", "akshare"))
    mgr = SourceManager([f1, f2])
    assert mgr.fetchers[0].source_name == "akshare"
    assert mgr.fetchers[1].source_name == "baostock"


def test_fetch_all_returns_first_success():
    high = _make_fetcher("akshare", 1, _ok_result("600519", "akshare", eps=47.76))
    low = _make_fetcher("baostock", 2, _ok_result("600519", "baostock", eps=47.0))
    mgr = SourceManager([low, high])
    result = mgr.fetch_all("600519", "SH")
    assert result.source == "akshare"
    assert result.data["eps"] == pytest.approx(47.76)


def test_failover_to_second_source():
    fail = _make_fetcher("akshare", 1, _err_result("600519", "akshare"))
    success = _make_fetcher("baostock", 2, _ok_result("600519", "baostock", eps=47.0))
    mgr = SourceManager([fail, success])
    result = mgr.fetch_all("600519", "SH")
    assert result.source == "baostock"
    assert result.ok


def test_all_fail_returns_error():
    f1 = _make_fetcher("akshare", 1, _err_result("600519", "akshare"))
    f2 = _make_fetcher("baostock", 2, _err_result("600519", "baostock"))
    mgr = SourceManager([f1, f2])
    result = mgr.fetch_all("600519", "SH")
    assert not result.ok


def test_from_config_builds_fetchers():
    config = {
        "data_sources": {
            "enabled": [
                {"name": "akshare", "priority": 1},
                {"name": "baostock", "priority": 2},
            ]
        }
    }
    mgr = SourceManager.from_config(config)
    names = [f.source_name for f in mgr.fetchers]
    assert "akshare" in names
    assert "baostock" in names


def test_from_config_unknown_source_skipped():
    config = {
        "data_sources": {
            "enabled": [
                {"name": "akshare", "priority": 1},
                {"name": "unknown_xyz", "priority": 99},
            ]
        }
    }
    mgr = SourceManager.from_config(config)
    assert len(mgr.fetchers) == 1


def test_from_config_empty_allows_offline_manager():
    """空 enabled 允许构造（离线工具/baseline）；在线 get_stock_data 再报错。"""
    mgr = SourceManager.from_config({"data_sources": {"enabled": []}})
    assert mgr.fetchers == []
    provider = StockDataProvider(mgr)
    with pytest.raises(DataProviderError, match="没有启用任何数据源"):
        provider.get_stock_data("600519")


# ── StockDataProvider 测试 ────────────────────────────────────────────────────

def test_non_a_share_raises():
    mgr = MagicMock(spec=SourceManager)
    provider = StockDataProvider(mgr)
    with pytest.raises(UnsupportedMarketError):
        provider.get_stock_data("AAPL")


def test_non_six_digit_raises():
    mgr = MagicMock(spec=SourceManager)
    provider = StockDataProvider(mgr)
    with pytest.raises(UnsupportedMarketError):
        provider.get_stock_data("60051")  # 5 位


def test_get_stock_data_field_sources_recorded():
    """字段应记录来源。"""
    f1 = _make_fetcher("akshare", 1, _ok_result("600519", "akshare", eps=47.76, roe=33.5))
    f2 = _make_fetcher("baostock", 2, _ok_result("600519", "baostock", growth_rate=15.2))
    mgr = SourceManager([f1, f2])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600519")
    assert stock.field_sources.get("eps") == "akshare"
    assert stock.field_sources.get("growth_rate") == "baostock"


def test_get_stock_data_high_priority_not_overwritten():
    """高优先级已写入的字段不被低优先级覆盖。"""
    f1 = _make_fetcher("akshare", 1, _ok_result("600519", "akshare", eps=47.76))
    f2 = _make_fetcher("baostock", 2, _ok_result("600519", "baostock", eps=47.0))
    mgr = SourceManager([f1, f2])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600519")
    assert stock.eps == pytest.approx(47.76)
    assert stock.field_sources["eps"] == "akshare"


def test_missing_fields_populated():
    """所有 None 字段应出现在 missing_fields 中。"""
    f1 = _make_fetcher("akshare", 1, _ok_result("600519", "akshare", eps=47.76))
    mgr = SourceManager([f1])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600519")
    assert "current_price" in stock.missing_fields
    assert "eps" not in stock.missing_fields


def test_pe_ratio_derived_when_price_and_eps_available():
    f1 = _make_fetcher("akshare", 1, _ok_result("600519", "akshare",
                                                  current_price=1800.0, eps=47.76))
    mgr = SourceManager([f1])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600519")
    assert stock.pe_ratio == pytest.approx(1800.0 / 47.76, rel=1e-4)
