"""价值面合并 golden：去 override 后的 priority 语义。"""

from __future__ import annotations

from unittest.mock import MagicMock

from data_provider.manager import SourceManager
from data_provider.provider import StockDataProvider


def _fetcher(name: str, priority: int, data: dict) -> MagicMock:
    f = MagicMock()
    f.source_name = name
    f.priority = priority
    f.fetch_all.return_value = MagicMock(
        ok=True, error=None, data=data, missing_fields=[]
    )
    return f


def test_merge_golden_tushare1_baostock2():
    ts = _fetcher(
        "tushare",
        1,
        {"revenue": 168.0, "fcf": 59.0, "industry": "白酒"},
    )
    bs = _fetcher(
        "baostock",
        2,
        {"revenue": 100.0, "fcf": 50.0, "current_price": 1400.0, "industry": "食品"},
    )
    stock = StockDataProvider(SourceManager([ts, bs])).get_stock_data("600519")
    assert stock.revenue == 168.0
    assert stock.fcf == 59.0
    assert stock.current_price == 1400.0
    assert stock.industry == "白酒"
    assert stock.field_sources["revenue"] == "tushare"
    assert stock.field_sources["current_price"] == "baostock"


def test_merge_golden_baostock1_tushare2_no_override():
    bs = _fetcher("baostock", 1, {"revenue": 100.0, "current_price": 1400.0})
    ts = _fetcher("tushare", 2, {"revenue": 168.0, "total_assets": 300.0})
    stock = StockDataProvider(SourceManager([bs, ts])).get_stock_data("600519")
    assert stock.revenue == 100.0
    assert stock.field_sources["revenue"] == "baostock"
    assert stock.total_assets == 300.0
