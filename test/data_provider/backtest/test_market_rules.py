"""T2.4 撮合市场数据适配器（成交额/涨跌停/停牌，缺字段即缺口）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError
from data_provider.backtest.market_rules import MarketRulesAdapter, merge_market_fields


def market_row(**overrides):
    payload = {
        "code": "000001",
        "trade_date": "2020-01-06",
        "amount": 1_000_000.0,
        "limit_up_price": 11.0,
        "limit_down_price": 9.0,
        "suspended": False,
    }
    payload.update(overrides)
    return payload


def test_no_source_reports_gap():
    with pytest.raises(BacktestDataGapError):
        MarketRulesAdapter().load_rows(["000001"], "2020-01-01", "2020-01-31")


@pytest.mark.parametrize("field", ["amount", "limit_up_price", "limit_down_price", "suspended"])
def test_missing_field_reports_gap(field):
    rows = [market_row()]
    rows[0].pop(field)
    adapter = MarketRulesAdapter(fetch=lambda **kwargs: rows)
    with pytest.raises(BacktestDataGapError) as exc:
        adapter.load_rows(["000001"], "2020-01-01", "2020-01-31")
    assert field in str(exc.value)


def test_merge_market_fields():
    price_rows = {"000001": ({"code": "000001", "trade_date": "2020-01-06", "close": 10.0},)}
    merged = merge_market_fields(price_rows, {"000001": (market_row(),)})
    assert merged["000001"][0]["amount"] == 1_000_000.0
    assert merged["000001"][0]["close"] == 10.0


def test_merge_reports_gap_when_date_missing():
    price_rows = {"000001": ({"code": "000001", "trade_date": "2020-01-07", "close": 10.0},)}
    with pytest.raises(BacktestDataGapError):
        merge_market_fields(price_rows, {"000001": (market_row(),)})
