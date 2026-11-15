"""T2.7 数据对齐 `data.py`（时点视图 + 公告日对齐 + 口径拒绝）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError, FutureDataError, InvalidAdjustModeError
from service.backtest.data import (
    build_point_in_time,
    load_financials_point_in_time,
    load_price_series,
)
from service.backtest.models import AdjustMode


class FakeLoader:
    def __init__(self, price_rows, financial_rows=None):
        self.price_rows = price_rows
        self.financial_rows = financial_rows or {}

    def load_price_rows(self, codes, start, end, adjust):
        return {code: self.price_rows.get(code, ()) for code in codes}

    def load_financial_rows(self, codes, as_of):
        return {code: self.financial_rows.get(code, ()) for code in codes}


def price_row(trade_date="2020-01-06", close=10.0, code="000001"):
    return {
        "code": code,
        "trade_date": trade_date,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "factor": 1.0,
        "amount": 1_000_000.0,
        "limit_up_price": 100.0,
        "limit_down_price": 1.0,
        "suspended": False,
    }


def test_qfq_request_rejected():
    loader = FakeLoader({"000001": (price_row(),)})
    with pytest.raises(InvalidAdjustModeError):
        load_price_series(["000001"], "2020-01-01", "2020-01-31", "qfq", loader=loader)


def test_load_price_series_maps_bars():
    loader = FakeLoader({"000001": (price_row(close=10.5),)})
    series = load_price_series(["000001"], "2020-01-01", "2020-01-31", AdjustMode.HFQ, loader=loader)
    assert series["000001"][0].close == 10.5
    assert series["000001"][0].amount == 1_000_000.0


def test_missing_rows_reports_gap():
    loader = FakeLoader({"000001": ()})
    with pytest.raises(BacktestDataGapError):
        load_price_series(["000001"], "2020-01-01", "2020-01-31", AdjustMode.HFQ, loader=loader)


def test_build_point_in_time_rejects_future_bar():
    loader = FakeLoader({"000001": (price_row("2020-01-07"),)})
    with pytest.raises(FutureDataError):
        build_point_in_time(["000001"], "2020-01-06", loader=loader)


def test_build_point_in_time_keeps_as_of_rows():
    loader = FakeLoader({"000001": (price_row("2020-01-06"), price_row("2020-01-03"))})
    snapshot = build_point_in_time(["000001"], "2020-01-06", loader=loader)
    assert [bar.trade_date for bar in snapshot.price] == ["2020-01-03", "2020-01-06"]


def test_financial_alignment_by_ann_date():
    rows = {
        "000001": (
            {
                "code": "000001",
                "report_period": "20191231",
                "ann_date": "2020-02-28",
                "end_date": "2019-12-31",
                "visible_from": "2020-02-28",
                "ann_date_fallback": False,
            },
        )
    }
    loader = FakeLoader({}, rows)
    before = load_financials_point_in_time(["000001"], "2020-02-27", loader=loader)
    after = load_financials_point_in_time(["000001"], "2020-02-28", loader=loader)
    assert before["000001"] == ()
    assert len(after["000001"]) == 1
    assert after["000001"][0].visible_from == "2020-02-28"


def test_financial_missing_ann_date_falls_back_and_flags():
    rows = {
        "000001": (
            {
                "code": "000001",
                "report_period": "20191231",
                "ann_date": None,
                "end_date": "2019-12-31",
            },
        )
    }
    loader = FakeLoader({}, rows)
    result = load_financials_point_in_time(["000001"], "2020-04-30", loader=loader)
    record = result["000001"][0]
    assert record.ann_date_fallback is True
    assert record.visible_from == "2020-04-30"
