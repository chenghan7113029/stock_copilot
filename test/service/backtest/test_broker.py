"""T2.9/T2.10 撮合：成本四分量 + A 股约束（T+1 / 封板顺延 / 停牌 / 流动性上限）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError, MissingBacktestConfigError
from service.backtest.broker import CostCalculator, LiquidityRules, execute_orders, next_tradable_day
from service.backtest.models import BacktestConfig, Order, OrderSide, OrderStatus


def order(side=OrderSide.BUY, signal_date="2020-01-03", amount=100_000.0, code="000001"):
    return Order(code=code, signal_date=signal_date, side=side, requested_amount=amount)


def test_cost_four_components_hand_calc(cfg):
    calculator = CostCalculator.from_config(cfg)
    buy, buy_notes = calculator.cost(100_000.0, OrderSide.BUY)
    sell, _ = calculator.cost(110_000.0, OrderSide.SELL)
    assert buy.commission == pytest.approx(25.0, abs=1e-9)
    assert buy.slippage == pytest.approx(100.0, abs=1e-9)
    assert buy.stamp_tax == 0.0
    assert buy.total == pytest.approx(125.0, abs=1e-9)
    assert buy_notes == ()
    assert sell.commission == pytest.approx(27.5, abs=1e-9)
    assert sell.stamp_tax == pytest.approx(55.0, abs=1e-9)
    assert sell.slippage == pytest.approx(110.0, abs=1e-9)
    assert sell.total == pytest.approx(192.5, abs=1e-9)


def test_minimum_commission_flagged(cfg):
    calculator = CostCalculator.from_config(cfg)
    cost, notes = calculator.cost(10_000.0, OrderSide.BUY)
    assert cost.commission == pytest.approx(5.0)
    assert "触发最低佣金" in notes


def test_missing_stamp_tax_rejected(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(**{"stamp_tax": {"side": "sell", "rate": None}}), base_dir=tmp_path
    )
    with pytest.raises(MissingBacktestConfigError):
        CostCalculator.from_config(cfg)


def test_liquidity_cap_truncates(cfg):
    rules = LiquidityRules.from_config(cfg)
    assert rules.limit_for(1_000_000.0) == pytest.approx(10_000.0)


def test_limit_up_seal_rolls_over(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(
                trade_date="2020-01-06",
                close=11.0,
                open_=11.0,
                high=11.0,
                low=11.0,
                limit_up=11.0,
            ),
            make_bar(trade_date="2020-01-07", close=11.5, limit_up=12.65),
        )
    }
    fill = execute_orders([order()], prices, cfg=cfg)[0]
    assert fill.attempts[0].attempt_date == "2020-01-06"
    assert fill.attempts[0].status is OrderStatus.FAILED_LIMIT_SEAL
    assert "封板" in (fill.attempts[0].reason or "")
    assert fill.attempts[-1].status is OrderStatus.FILLED
    assert fill.fill_date == "2020-01-07"
    assert fill.delay_days == 1
    assert fill.fill_price == 11.5


def test_suspended_day_skipped(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(trade_date="2020-01-06", close=10.0, suspended=True),
            make_bar(trade_date="2020-01-07", close=10.2),
        )
    }
    fill = execute_orders([order()], prices, cfg=cfg)[0]
    assert fill.attempts[0].status is OrderStatus.SKIPPED_SUSPENDED
    assert fill.fill_date == "2020-01-07"


def test_t1_rejected_same_batch(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(trade_date="2020-01-06", close=10.1),
        )
    }
    buy = order(OrderSide.BUY)
    sell = order(OrderSide.SELL, amount=10_000.0)
    buy_fill, sell_fill = execute_orders([buy, sell], prices, cfg=cfg)
    assert buy_fill.fill_date == "2020-01-06"
    assert sell_fill.attempts[0].status is OrderStatus.REJECTED_T1
    assert sell_fill.fill_date is None
    assert any("T+1" in note or "当日" in note for note in sell_fill.notes)


def test_liquidity_cap_uses_avg_amount(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(
                trade_date="2020-01-06", close=10.0, amount=1_000_000.0, avg_amount=1_000_000.0
            ),
        )
    }
    fill = execute_orders([order(amount=50_000.0)], prices, cfg=cfg)[0]
    assert fill.filled_amount == pytest.approx(10_000.0)  # 1_000_000 × 0.01
    assert "触及流动性上限" in fill.notes
    assert fill.attempts[-1].status is OrderStatus.CAPPED_LIQUIDITY


def test_missing_avg_amount_reports_gap(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(trade_date="2020-01-06", close=10.0, avg_amount=None),
        )
    }
    with pytest.raises(BacktestDataGapError) as exc:
        execute_orders([order()], prices, cfg=cfg)
    assert "avg_amount" in str(exc.value)


def test_liquidity_cap_unconfigured_rejected(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(**{"liquidity_cap": []}), base_dir=tmp_path
    )
    with pytest.raises(MissingBacktestConfigError):
        LiquidityRules.from_config(cfg)


def test_multi_tier_liquidity_does_not_degrade(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(
            **{
                "liquidity_cap": [
                    {"adv_tier": "small", "max_participation": 0.01},
                    {"adv_tier": "large", "max_participation": 0.05},
                ]
            }
        ),
        base_dir=tmp_path,
    )
    with pytest.raises(BacktestDataGapError):
        LiquidityRules.from_config(cfg)


def test_max_delay_cap_fails_order(cfg, make_bar):
    bars = [make_bar(trade_date="2020-01-03", close=10.0)]
    for day in ("2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10", "2020-01-13"):
        bars.append(
            make_bar(
                trade_date=day,
                close=11.0,
                open_=11.0,
                high=11.0,
                low=11.0,
                limit_up=11.0,
            )
        )
    fill = execute_orders([order()], {"000001": tuple(bars)}, cfg=cfg)[0]
    assert fill.fill_date is None
    assert fill.attempts[-1].status is not OrderStatus.FILLED
    assert "上限" in (fill.attempts[-1].reason or "")


def test_missing_market_fields_reports_gap(cfg, make_bar):
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(trade_date="2020-01-06", close=10.0, amount=None),
        )
    }
    with pytest.raises(BacktestDataGapError):
        execute_orders([order()], prices, cfg=cfg)


def test_next_tradable_day_skips_weekend():
    def is_trading(day: str) -> bool:
        from datetime import date

        return date.fromisoformat(day).weekday() < 5

    assert next_tradable_day("2020-01-03", calendar=is_trading) == "2020-01-06"


def test_max_delay_missing_rejected(tmp_path, config_factory, make_bar):
    cfg = BacktestConfig.from_config(
        config_factory(**{"max_delay_days": None}), base_dir=tmp_path
    )
    prices = {
        "000001": (
            make_bar(trade_date="2020-01-03", close=10.0),
            make_bar(trade_date="2020-01-06", close=10.0),
        )
    }
    with pytest.raises(MissingBacktestConfigError) as exc:
        execute_orders([order()], prices, cfg=cfg)
    assert "max_delay_days" in str(exc.value)


def test_missing_transfer_fee_rejected(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(**{"transfer_fee": {"rate": None, "included": None}}), base_dir=tmp_path
    )
    with pytest.raises(MissingBacktestConfigError):
        CostCalculator.from_config(cfg)


def test_slippage_last_tier_is_unbounded(tmp_path, config_factory):
    """§9.3 滑点三档：<1亿 20bps / 1–5亿 10bps / ≥5亿 5bps（最后一档 amount_upper=null）。"""
    cfg = BacktestConfig.from_config(
        config_factory(
            **{
                "slippage_tiers": [
                    {"amount_lower": 0, "amount_upper": 100_000_000, "bps": 20},
                    {"amount_lower": 100_000_000, "amount_upper": 500_000_000, "bps": 10},
                    {"amount_lower": 500_000_000, "amount_upper": None, "bps": 5},
                ]
            }
        ),
        base_dir=tmp_path,
    )
    calculator = CostCalculator.from_config(cfg)
    assert calculator.slippage_rate(10_000_000) == pytest.approx(20 / 10000)
    assert calculator.slippage_rate(200_000_000) == pytest.approx(10 / 10000)
    assert calculator.slippage_rate(1_000_000_000) == pytest.approx(5 / 10000)
