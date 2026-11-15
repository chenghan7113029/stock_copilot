"""R8 A 股撮合约束：封板顺延 / T+1 / 停牌跳过（TC-R08-01..04）。

锚点：spec R8；design §4.1 `OrderAttempt`/`Fill.attempts`/`fill_date`/`delay_days`、
`OrderStatus`（FAILED_LIMIT_SEAL / SKIPPED_SUSPENDED / REJECTED_T1）、§4.2 R8「逐次 attempt 留痕」。
"""

from __future__ import annotations


def _buy(models, signal_date):
    return models.Order(code="000001", signal_date=signal_date, side=models.OrderSide.BUY,
                        requested_amount=10_000.0, requested_qty=None)


def _sell(models, signal_date, qty=1_000):
    return models.Order(code="000001", signal_date=signal_date, side=models.OrderSide.SELL,
                        requested_amount=0.0, requested_qty=qty)


def test_tc_r08_01_limit_up_seal_defers_to_next_tradable_day(load, models, make_bar, cfg):
    """TC-R08-01（R8 Scenario1）：t+1 一字涨停买不进 → 目标日失败，成交顺延到下一可成交日。"""
    broker = load("service.backtest.broker")
    sealed = make_bar("2020-01-06", close=11.0, open_=11.0, high=11.0, low=11.0, limit_up=11.0)
    prices = {"000001": (sealed, make_bar("2020-01-07", close=11.5))}

    fill = broker.execute_orders([_buy(models, "2020-01-03")], prices, cfg=cfg)[0]

    first = fill.attempts[0]
    assert first.attempt_date == "2020-01-06"
    assert first.status is models.OrderStatus.FAILED_LIMIT_SEAL
    assert "封板" in (first.reason or "")
    assert fill.attempts[-1].status is models.OrderStatus.FILLED
    assert fill.fill_date == fill.attempts[-1].attempt_date == "2020-01-07"
    assert fill.delay_days == 1  # 首个目标日（t+1）与成交日的交易日差
    assert fill.fill_price != sealed.close


def test_tc_r08_02_limit_down_seal_defers_sell(load, models, make_bar, cfg):
    """TC-R08-02（R8 Scenario2）：连续 2 日跌停卖不出 → 顺延，delay_days=2 且标注连续封板天数。"""
    broker = load("service.backtest.broker")
    sealed1 = make_bar("2020-01-06", close=9.0, limit_down=9.0)
    sealed2 = make_bar("2020-01-07", close=8.1, limit_down=8.1)
    prices = {"000001": (sealed1, sealed2, make_bar("2020-01-08", close=8.3))}

    fill = broker.execute_orders([_sell(models, "2020-01-03")], prices, cfg=cfg)[0]

    assert fill.attempts[0].status is models.OrderStatus.FAILED_LIMIT_SEAL
    assert fill.delay_days == 2
    assert any("连续封板" in note for note in fill.notes)


def test_tc_r08_03_same_day_sell_rejected_by_t1(load, models, make_bar, cfg):
    """TC-R08-03（R8 Scenario3）：t 日买入、同日卖出 → REJECTED_T1，最早可卖日 t+1。"""
    broker = load("service.backtest.broker")
    prices = {"000001": (make_bar("2020-01-06", close=10.0), make_bar("2020-01-07", close=10.2))}
    orders = [_buy(models, "2020-01-06"), _sell(models, "2020-01-06")]

    fills = broker.execute_orders(orders, prices, cfg=cfg)
    sell_fill = fills[1]

    assert sell_fill.attempts[0].status is models.OrderStatus.REJECTED_T1
    assert sell_fill.fill_date is None
    assert any("T+1" in (attempt.reason or "") or "当日" in (attempt.reason or "")
               for attempt in sell_fill.attempts)


def test_tc_r08_04_suspended_day_skipped(load, models, make_bar, cfg):
    """TC-R08-04（R8 Scenario4）：t+1 停牌 → 不计成交，顺延至复牌后首个可成交日。"""
    broker = load("service.backtest.broker")
    prices = {"000001": (make_bar("2020-01-06", suspended=True), make_bar("2020-01-07", close=10.1))}

    fill = broker.execute_orders([_buy(models, "2020-01-03")], prices, cfg=cfg)[0]

    assert fill.attempts[0].status is models.OrderStatus.SKIPPED_SUSPENDED
    assert fill.fill_date == "2020-01-07"
    assert all(attempt.attempt_date != "2020-01-06"
               for attempt in fill.attempts if attempt.status is models.OrderStatus.FILLED)
