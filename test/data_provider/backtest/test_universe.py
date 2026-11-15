"""T2.5 退市/ST/历史成分适配器（R12：名单不可得即缺口）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError
from data_provider.backtest.universe import UniverseAdapter


def members_fetch(**kwargs):
    return [{"code": "000002"}, {"code": "000001"}, {"code": "000001"}]


def flags_fetch(**kwargs):
    return [
        {"code": "000001", "delisted": False, "delist_date": None, "st": False},
        {"code": "000002", "delisted": True, "delist_date": "2019-06-30", "st": True},
    ]


def test_no_source_reports_gap():
    with pytest.raises(BacktestDataGapError):
        UniverseAdapter().load_members("2020-01-02", {"kind": "all_a"})
    with pytest.raises(BacktestDataGapError):
        UniverseAdapter().load_flags(["000001"], "2020-01-02")


def test_members_sorted_and_deduplicated():
    adapter = UniverseAdapter(fetch=members_fetch)
    assert adapter.load_members("2020-01-02", {"kind": "all_a"}) == ("000001", "000002")


def test_empty_members_reports_gap():
    adapter = UniverseAdapter(fetch=lambda **kwargs: [])
    with pytest.raises(BacktestDataGapError):
        adapter.load_members("2020-01-02", {"kind": "all_a"})


def test_flags_keep_point_in_time_st_and_delist_date():
    adapter = UniverseAdapter(fetch=flags_fetch)
    flags = adapter.load_flags(["000001", "000002"], "2020-01-02")
    assert flags["000001"]["st"] is False
    assert flags["000002"]["delisted"] is True
    assert flags["000002"]["delist_date"] == "2019-06-30"


def test_missing_flags_reports_gap():
    adapter = UniverseAdapter(fetch=lambda **kwargs: [])
    with pytest.raises(BacktestDataGapError):
        adapter.load_flags(["000001"], "2020-01-02")


def dispatch_fetch(*, kind, **kwargs):
    if kind == "constituents":
        return [{"code": "000001"}, {"code": "000002"}]
    if kind == "delisted":
        return [{"code": "000002"}]
    if kind == "st":
        return [{"code": kwargs["code"], "st": kwargs["code"] == "000001"}]
    raise AssertionError(f"unexpected kind: {kind}")


def test_protocol_historical_constituents():
    adapter = UniverseAdapter(fetch=dispatch_fetch)
    assert adapter.historical_constituents("2020-01-02", "csi300") == ("000001", "000002")


def test_protocol_empty_constituents_is_legal():
    adapter = UniverseAdapter(fetch=lambda **kwargs: [])
    assert adapter.historical_constituents("2020-01-02", "all_a") == ()


def test_protocol_delisted_codes():
    adapter = UniverseAdapter(fetch=dispatch_fetch)
    assert adapter.delisted_codes("2020-01-02") == ("000002",)


def test_protocol_st_status_point_in_time():
    adapter = UniverseAdapter(fetch=dispatch_fetch)
    assert adapter.st_status("000001", "2020-01-02") is True
    assert adapter.st_status("000002", "2020-01-02") is False


def test_protocol_st_status_missing_reports_gap():
    adapter = UniverseAdapter(fetch=lambda **kwargs: [])
    with pytest.raises(BacktestDataGapError):
        adapter.st_status("000001", "2020-01-02")


def test_protocol_without_source_reports_gap():
    adapter = UniverseAdapter()
    with pytest.raises(BacktestDataGapError):
        adapter.historical_constituents("2020-01-02", "all_a")
    with pytest.raises(BacktestDataGapError):
        adapter.delisted_codes("2020-01-02")
    with pytest.raises(BacktestDataGapError):
        adapter.st_status("000001", "2020-01-02")
