"""T2.11 纯函数信号 `signal.py`（ConditionSpec + t 日切片 + 越界拒绝 + 可复现）。"""

from __future__ import annotations

import inspect

import pytest

from common.exceptions import FutureDataError, MissingBacktestConfigError
from service.backtest.models import ConditionSpec, PointInTimeSnapshot
from service.backtest.signal import (
    CONDITION_KIND,
    MA_FALLBACK_WINDOW,
    MA_WINDOW,
    evaluate_condition,
)


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


def snapshot_for(make_bar, closes):
    price = bars(make_bar, closes)
    return PointInTimeSnapshot(as_of=price[-1].trade_date, price=price)


def condition(**params):
    merged = {"window": MA_WINDOW}
    merged.update(params)
    return ConditionSpec(condition_id="ma60_breakdown", kind=CONDITION_KIND, params=merged)


def test_ma60_breakdown_emits_event(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * 60 + [9.0])
    signal = evaluate_condition(snapshot, condition())
    assert signal is not None
    assert signal.event_date == snapshot.as_of
    assert signal.condition_id == "ma60_breakdown"


def test_flat_series_has_no_signal(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * 61)
    assert evaluate_condition(snapshot, condition()) is None


def test_pure_function_same_input_same_output(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * 60 + [9.0])
    assert evaluate_condition(snapshot, condition()) == evaluate_condition(
        snapshot, condition()
    )


def test_future_bar_rejected_by_snapshot(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * 61)
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(as_of=snapshot.price[-2].trade_date, price=snapshot.price)


def test_missing_condition_params_rejected(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * 61)
    broken = ConditionSpec(condition_id="ma60_breakdown", kind=CONDITION_KIND, params={})
    with pytest.raises(MissingBacktestConfigError) as exc:
        evaluate_condition(snapshot, broken)
    assert "window" in str(exc.value)


def test_short_history_uses_ma20_substitute(make_bar):
    """不足 MA60 个交易日：沿用 tech 现行口径（MA20 替代，KD-10-03）。"""
    closes = [10.0] * MA_FALLBACK_WINDOW + [9.0]
    snapshot = snapshot_for(make_bar, closes)
    assert evaluate_condition(snapshot, condition()) is not None
    assert len(snapshot.price) < MA_WINDOW


def test_too_short_history_returns_none(make_bar):
    snapshot = snapshot_for(make_bar, [10.0] * (MA_FALLBACK_WINDOW - 1))
    assert evaluate_condition(snapshot, condition()) is None


def test_signal_module_has_no_io_dependency():
    module = inspect.getmodule(evaluate_condition)
    assert module is not None
    module_source = inspect.getsource(module)
    for forbidden in ("data_provider", "dao", "datetime.now", "open("):
        assert forbidden not in module_source
    assert set(inspect.signature(evaluate_condition).parameters) == {"snapshot", "condition"}
