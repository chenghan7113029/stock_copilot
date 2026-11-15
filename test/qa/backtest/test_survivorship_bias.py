"""R12 生存偏差：退市、ST 与历史成分（TC-R12-01..04）。

锚点：spec R12；design §4.1 `build_universe(as_of, universe_spec, *, provider)`、
`PriceBar.delisted/st`（「按时点，不回填」）、`BacktestDataGapError`（名单不可得 → 报缺口并停止）、§4.2 R12。
provider 形态：`provider(as_of) -> dict{constituents, delisted, st}`（取数适配器契约见 design §4.1/§6.2）。
"""

from __future__ import annotations

import pytest


def _provider(constituents, delisted=(), st=(), *, calls=None):
    def _provider(as_of):
        if calls is not None:
            calls.append(as_of)
        return {"constituents": list(constituents), "delisted": list(delisted), "st": list(st)}

    return _provider


def test_tc_r12_01_delisted_stock_counted_before_delisting(load, make_bar):
    """TC-R12-01（R12 Scenario1）：2017–2019 含 2019 退市股；退市日之后不再成交。"""
    universe_mod = load("service.backtest.universe")
    spec = {"index": "all_a", "include_delisted": True, "st_mode": "point_in_time"}

    members = universe_mod.build_universe(
        "2018-06-29", spec, provider=_provider(["000001", "600001"], delisted=["600001"]))

    assert "600001" in members, "退市股在退市前必须计入样本（生存偏差）"
    delisted_bar = make_bar("2019-07-01", code="600001", delisted=True)
    assert delisted_bar.delisted is True
    assert make_bar("2019-06-28", code="600001", delisted=False).delisted is False


def test_tc_r12_02_st_status_is_point_in_time(load, make_bar):
    """TC-R12-02（R12 Scenario2）：评估 2015–2020 用当时 ST 名单，不得用今日标签回填。"""
    universe_mod = load("service.backtest.universe")
    calls = []
    spec = {"index": "all_a", "include_delisted": True, "st_mode": "point_in_time"}

    members = universe_mod.build_universe(
        "2016-06-30", spec, provider=_provider(["000001", "600002"], st=["600002"], calls=calls))

    assert calls == ["2016-06-30"], "provider 必须按当时时点调用（不得用今日名单回看历史）"
    assert "600002" in members
    assert make_bar("2016-06-30", code="600002", st=True).st is True
    assert make_bar("2016-06-30", code="000001", st=False).st is False


def test_tc_r12_03_historical_index_constituents(load):
    """TC-R12-03（R12 Scenario3）：2016 年沪深 300 用 2016 成分名单，不用当前成分。"""
    universe_mod = load("service.backtest.universe")
    spec = {"index": "hs300", "include_delisted": True, "st_mode": "point_in_time"}
    historical = ["600001", "600009"]

    members = universe_mod.build_universe("2016-06-30", spec, provider=_provider(historical))

    assert list(members) == historical, "必须使用历史时点成分（R12 Scenario3）"
    assert "300750" not in members, "不得把今日成分回填到 2016"


def test_tc_r12_04_missing_lists_report_gap(load, models):
    """TC-R12-04（R12 Scenario4）：退市/ST 名单不可得 → BacktestDataGapError，不得静默剔除。"""
    universe_mod = load("service.backtest.universe")

    def _provider(as_of):
        raise models.BacktestDataGapError("退市名单缺失；影响范围：R12 生存偏差")

    with pytest.raises(models.BacktestDataGapError) as exc:
        universe_mod.build_universe("2019-12-31",
                                    {"index": "all_a", "include_delisted": True,
                                     "st_mode": "point_in_time"}, provider=_provider)

    message = str(exc.value)
    assert "退市" in message and "影响" in message
    assert "剔除" not in message, "缺口不得降级为「剔除」（spec R12 Scenario4）"
