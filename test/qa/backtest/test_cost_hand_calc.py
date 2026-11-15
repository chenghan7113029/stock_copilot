"""R7 成本与摩擦计入每笔成交（TC-R07-01..04）。

锚点：spec R7；design §4.1 `CostBreakdown`（佣金/印花税/滑点/过户费/total）、
`execute_orders(orders, prices, *, cfg)`、`MissingBacktestConfigError`、§4.2 R7「超限截断标注」。
成本期望值由本文件的独立算式给出（**禁止调用被测成本函数反推**）。
"""

from __future__ import annotations

import json

import pytest


def _buy(models, amount=100_000.0):
    return models.Order(code="000001", signal_date="2020-01-06", side=models.OrderSide.BUY,
                        requested_amount=amount, requested_qty=None)


def _sell(models, qty=10_000):
    return models.Order(code="000001", signal_date="2020-01-07", side=models.OrderSide.SELL,
                        requested_amount=0.0, requested_qty=qty)


def test_tc_r07_01_cost_components_match_hand_calc(load, models, make_bar, cfg, cfg_raw):
    """TC-R07-01（R7 Scenario1）：10 万买 / 11 万卖 → 四项分金额与手算一致。"""
    broker = load("service.backtest.broker")
    prices = {"000001": (make_bar("2020-01-07", close=11.0),)}
    fills = broker.execute_orders([_buy(models), _sell(models)], prices, cfg=cfg)
    buy_cost, sell_cost = fills[0].cost, fills[1].cost

    rate, minimum = cfg_raw["commission"]["rate"], cfg_raw["commission"]["min"]
    exp_buy_comm = max(100_000.0 * rate, minimum)
    exp_sell_comm = max(110_000.0 * rate, minimum)
    exp_stamp = 110_000.0 * cfg_raw["stamp_tax"]["sell_rate"]
    exp_slip_buy = 100_000.0 * cfg_raw["slippage_tiers"][0]["rate"]
    exp_slip_sell = 110_000.0 * cfg_raw["slippage_tiers"][0]["rate"]

    assert buy_cost.commission == pytest.approx(exp_buy_comm, abs=1e-9)
    assert sell_cost.commission == pytest.approx(exp_sell_comm, abs=1e-9)
    assert sell_cost.stamp_tax == pytest.approx(exp_stamp, abs=1e-9)
    assert buy_cost.stamp_tax == 0.0, "买入方向不得收印花税（spec R7 仅卖出）"
    assert buy_cost.slippage == pytest.approx(exp_slip_buy, abs=1e-9)
    assert sell_cost.slippage == pytest.approx(exp_slip_sell, abs=1e-9)
    assert buy_cost.total == pytest.approx(exp_buy_comm + exp_slip_buy, abs=1e-9)
    assert sell_cost.total == pytest.approx(exp_sell_comm + exp_stamp + exp_slip_sell, abs=1e-9)


def test_tc_r07_02_small_trade_hits_minimum_commission(load, models, make_bar, cfg, cfg_raw):
    """TC-R07-02（R7 Scenario2）：费率算出的佣金低于最低额 → 取最低额并标注「触发最低佣金」。"""
    broker = load("service.backtest.broker")
    prices = {"000001": (make_bar("2020-01-07", close=10.0),)}
    fill = broker.execute_orders([_buy(models, amount=10_000.0)], prices, cfg=cfg)[0]

    assert 10_000.0 * cfg_raw["commission"]["rate"] < cfg_raw["commission"]["min"]
    assert fill.cost.commission == pytest.approx(cfg_raw["commission"]["min"], abs=1e-9)
    assert any("最低佣金" in note for note in fill.notes)


def test_tc_r07_03_missing_fee_config_rejected(load, cfg_raw):
    """TC-R07-03（R7 Scenario3）：配置缺印花税率 → MissingBacktestConfigError，不得按 0 继续。"""
    config_mod = load("service.backtest.config")
    raw = json.loads(json.dumps(cfg_raw))
    raw.pop("stamp_tax")

    with pytest.raises(config_mod.MissingBacktestConfigError) as exc:
        config_mod.BacktestConfig.from_config(raw)
    assert "stamp_tax" in str(exc.value), "缺键报错须列出缺失键（design §4.1）"


def test_tc_r07_04_liquidity_cap_truncates_order(load, models, make_bar, cfg, cfg_raw):
    """TC-R07-04（R7 Scenario4）：单笔超过成交额分档上限 → 按上限截断并标注。"""
    broker = load("service.backtest.broker")
    bar = make_bar("2020-01-07", close=10.0, amount=1_000_000.0)
    cap = 1_000_000.0 * cfg_raw["liquidity_cap"]["max_pct_of_avg_amount"]
    fill = broker.execute_orders([_buy(models, amount=50_000.0)], {"000001": (bar,)}, cfg=cfg)[0]

    assert fill.filled_amount == pytest.approx(cap, abs=1e-6)
    assert any("流动性上限" in note for note in fill.notes)
