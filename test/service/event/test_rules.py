"""治理事件面确定性规则单元测试。"""

from __future__ import annotations

from datetime import date

import pytest

from service.event.rules import (
    compute_block_trade_discount,
    compute_holder_net_sell,
    compute_northbound_net_inflow,
    compute_pledge_ratio,
    compute_repurchase_active,
    compute_upcoming_unlock_30d,
)

TODAY = date(2026, 9, 24)


def test_holder_net_sell_aggregates_directions() -> None:
    records = [
        {"ann_date": "2026-09-01", "in_de": "DE", "change_vol": 50000.0},
        {"ann_date": "2026-09-02", "in_de": "DE", "change_vol": 50000.0},
        {"ann_date": "2026-09-03", "in_de": "IN", "change_vol": 30000.0},
    ]
    net, warnings = compute_holder_net_sell(records, TODAY)
    assert net == 70000.0  # 净减持 7 万股
    assert warnings == []


def test_holder_net_sell_ignores_out_of_window() -> None:
    records = [{"ann_date": "2026-01-01", "in_de": "DE", "change_vol": 50000.0}]
    net, warnings = compute_holder_net_sell(records, TODAY)
    assert net is None
    assert any("不足" in w for w in warnings)


def test_repurchase_active() -> None:
    records = [{"ann_date": "2026-09-10", "proc": "实施"}]
    active, _ = compute_repurchase_active(records, TODAY)
    assert active is True

    records2 = [{"ann_date": "2026-09-10", "proc": "董事会预案"}]
    active2, _ = compute_repurchase_active(records2, TODAY)
    assert active2 is False


def test_upcoming_unlock_30d() -> None:
    records = [
        {"float_date": "2026-10-10", "float_ratio": 1.5},
        {"float_date": "2026-12-01", "float_ratio": 2.0},  # 超出 30 日窗口
    ]
    ratio, _ = compute_upcoming_unlock_30d(records, TODAY)
    assert ratio == 1.5


def test_pledge_ratio_reads_latest() -> None:
    records = [
        {"end_date": "2026-09-23", "pledge_ratio": 51.0},
        {"end_date": "2026-09-24", "pledge_ratio": 52.0},
    ]
    ratio, _ = compute_pledge_ratio(records)
    assert ratio == 52.0


def test_pledge_ratio_no_data_degrades() -> None:
    ratio, warnings = compute_pledge_ratio([])
    assert ratio is None
    assert any("不足" in w for w in warnings)


def test_block_trade_discount_average() -> None:
    records = [
        {"trade_date": "2026-09-10", "discount": -2.5},
        {"trade_date": "2026-09-11", "discount": -1.5},
    ]
    discount, _ = compute_block_trade_discount(records, TODAY)
    assert discount == pytest.approx(-2.0)


def test_northbound_net_inflow_sum() -> None:
    records = [{"north_money": v} for v in (20.0, -5.0, 10.0, 8.0, -3.0)]
    total, _ = compute_northbound_net_inflow(records)
    assert total == 30.0


def test_northbound_net_inflow_insufficient_data() -> None:
    records = [{"north_money": 20.0}, {"north_money": -5.0}]
    total, warnings = compute_northbound_net_inflow(records)
    assert total == 15.0
    assert any("不足" in w for w in warnings)
