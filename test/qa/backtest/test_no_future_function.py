"""R10 信号纯函数与成交时点边界（TC-R10-01..03）。

锚点：spec R10；design §4.1 `PointInTimeSnapshot.__post_init__`（越界抛 `FutureDataError`）、
`evaluate_condition(snapshot, condition)`、`execute_orders`（t→t+1）、§4.2 R10「入参被硬裁到 t」。
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest


def test_tc_r10_01_signal_at_t_fill_from_t_plus_one(load, models, make_bar, cfg):
    """TC-R10-01（R10 Scenario1）：t 日信号 → 成交日 ≥ t+1，成交价取 t+1 及之后的价格。"""
    broker = load("service.backtest.broker")
    prices = {"000001": (make_bar("2020-01-06", close=10.0), make_bar("2020-01-07", close=10.4))}
    order = models.Order(code="000001", signal_date="2020-01-06", side=models.OrderSide.BUY,
                         requested_amount=10_000.0, requested_qty=None)

    fill = broker.execute_orders([order], prices, cfg=cfg)[0]

    assert fill.fill_date is not None
    assert fill.fill_date > order.signal_date
    assert fill.fill_price != 10.0, "成交价不得取信号日收盘价（t→t+1）"


def test_tc_r10_02_future_data_raises(models, make_bar, make_financial):
    """TC-R10-02（R10 Scenario2）：快照含 t+1 价格或未来可见财务 → FutureDataError，不静默截断。"""
    with pytest.raises(models.FutureDataError):
        models.PointInTimeSnapshot(as_of="2020-01-06",
                                   price=(make_bar("2020-01-07", close=11.0),), financials=())

    future_financial = make_financial(ann_date="2020-02-28", visible_from="2020-02-28")
    with pytest.raises(models.FutureDataError):
        models.PointInTimeSnapshot(as_of="2020-01-06",
                                   price=(make_bar("2020-01-06", close=10.0),),
                                   financials=(future_financial,))


def test_tc_r10_03_signal_is_pure_and_io_free(load, models, make_bar, make_financial):
    """TC-R10-03（R10 Scenario3）：同输入同输出；且 signal 不接日期、不 import IO 层。"""
    signal = load("service.backtest.signal")
    snapshot = models.PointInTimeSnapshot(
        as_of="2020-01-06", price=(make_bar("2020-01-06", close=10.0),),
        financials=(make_financial(ann_date="2020-01-02", visible_from="2020-01-02"),))
    condition = {"condition_id": "ma60_breakdown", "params": {"ma_days": 60}}

    first = signal.evaluate_condition(snapshot, condition)
    second = signal.evaluate_condition(snapshot, condition)

    assert first == second
    assert set(inspect.signature(signal.evaluate_condition).parameters) == {"snapshot", "condition"}
    source = Path(inspect.getfile(signal.evaluate_condition)).read_text(encoding="utf-8")
    assert "data_provider" not in source and "dao" not in source and "datetime.now" not in source
