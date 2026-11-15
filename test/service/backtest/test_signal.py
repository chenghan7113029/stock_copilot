"""T2.11 纯函数信号 `signal.py`（t 日切片 + 越界拒绝 + 纯函数可复现）。"""

from __future__ import annotations

import inspect

import pytest

from common.exceptions import FutureDataError, MissingBacktestConfigError
from service.backtest.models import ConditionSpec, PointInTimeSnapshot
from service.backtest.signal import MA_FALLBACK_WINDOW, MA_WINDOW, evaluate_condition


def bars(make_bar, closes):
    from datetime import date, timedelta

    current = date(2020, 1, 1)
    result = []
    for close in closes:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        result.append(make_bar(trade_date=current.isoformat(), close=close))
        current += timedelta(days=1)
    return tuple(result)


def condition(**overrides):
    params = {
        "window": MA_WINDOW,
        "fallback_window": MA_FALLBACK_WINDOW,
        "short_history_policy": "ma20_substitute",
    }
    params.update(overrides)
    return ConditionSpec(condition_id="ma60_breakdown", kind="ma_breakdown", params=params)


def breakout_snapshot(make_bar):
    snapshot = PointInTimeSnapshot(as_of="2020-04-30", price=bars(make_bar, [10.0] * 60 + [9.0]))
    # as_of 必须与最后一根 bar 同日（快照只做 <= 断言，但语义上 as_of = t）
    as_of = snapshot.price[-1].trade_date
    return PointInTimeSnapshot(as_of=as_of, price=snapshot.price)


def test_ma60_breakdown_emits_event(make_bar):
    snapshot = breakout_snapshot(make_bar)
    signal = evaluate_condition(snapshot, condition())
    assert signal is not None
    assert signal.event_date == snapshot.as_of
    assert signal.condition_id == "ma60_breakdown"


def test_flat_series_has_no_signal(make_bar):
    snapshot = PointInTimeSnapshot(as_of="2020-04-30", price=bars(make_bar, [10.0] * 61))
    assert evaluate_condition(snapshot, condition()) is None


def test_pure_function_same_input_same_output(make_bar):
    snapshot = breakout_snapshot(make_bar)
    first = evaluate_condition(snapshot, condition())
    second = evaluate_condition(snapshot, condition())
    assert first == second


def test_future_bar_rejected_by_snapshot(make_bar):
    snapshot = breakout_snapshot(make_bar)
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(
            as_of=snapshot.price[-2].trade_date,
            price=snapshot.price,
        )


def test_missing_condition_params_rejected(make_bar):
    snapshot = breakout_snapshot(make_bar)
    broken = ConditionSpec(condition_id="ma60", kind="ma_breakdown", params={"window": 60})
    with pytest.raises(MissingBacktestConfigError) as exc:
        evaluate_condition(snapshot, broken)
    assert "fallback_window" in str(exc.value)


def test_short_history_policy_exclude_returns_none(make_bar):
    price = bars(make_bar, [10.0] * 25 + [9.0])
    snapshot = PointInTimeSnapshot(as_of=price[-1].trade_date, price=price)
    assert evaluate_condition(snapshot, condition(short_history_policy="exclude")) is None


def test_signal_module_has_no_io_dependency():
    source = inspect.getsource(evaluate_condition)
    module = inspect.getmodule(evaluate_condition)
    assert module is not None
    module_source = inspect.getsource(module)
    for forbidden in ("data_provider", "dao", "datetime.now", "open("):
        assert forbidden not in module_source
    assert set(inspect.signature(evaluate_condition).parameters) == {"snapshot", "condition"}
    assert "snapshot" in source
