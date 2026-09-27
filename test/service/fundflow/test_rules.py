"""资金面确定性规则单元测试。"""

from __future__ import annotations

import pytest

from service.fundflow.models.fund_flow_result import LeverageDirection
from service.fundflow.rules import (
    compute_main_net_inflow_5d,
    compute_margin_change_pct,
    compute_short_change_pct,
    leverage_direction,
    short_spike_reason,
)


def _margin(pairs: list[tuple[float, float]]) -> list[dict]:
    return [
        {"trade_date": f"2026-09-{20 + i:02d}", "rzrqye": rzrqye, "rqye": rqye}
        for i, (rzrqye, rqye) in enumerate(pairs)
    ]


def test_margin_change_normal() -> None:
    records = _margin([(1.0e8, 1.0e6)] * 5 + [(1.1e8, 1.0e6)])
    change, warnings = compute_margin_change_pct(records)
    assert change == pytest.approx(10.0)
    assert warnings == []


def test_margin_change_zero_base_degrades() -> None:
    records = _margin([(0.0, 1.0e6), (1.1e8, 1.0e6)])
    change, warnings = compute_margin_change_pct(records)
    assert change is None
    assert any("基期值为 0" in w for w in warnings)


def test_margin_change_insufficient_data_degrades() -> None:
    records = _margin([(1.0e8, 1.0e6)])
    change, warnings = compute_margin_change_pct(records)
    assert change is None
    assert any("数据不足" in w for w in warnings)


def test_short_change_uses_rqye_field() -> None:
    records = _margin([(1.0e8, 1.0e6)] * 5 + [(1.1e8, 1.8e6)])
    change, warnings = compute_short_change_pct(records)
    assert change == pytest.approx(80.0)
    assert warnings == []


def test_main_net_inflow_5d_sum() -> None:
    records = [{"net_mf_amount": v} for v in [1000.0, -200.0, 300.0, 500.0, -100.0]]
    inflow, warnings = compute_main_net_inflow_5d(records)
    assert inflow == 1500.0
    assert warnings == []


def test_main_net_inflow_no_data_degrades() -> None:
    inflow, warnings = compute_main_net_inflow_5d([])
    assert inflow is None
    assert any("不足" in w for w in warnings)


def test_short_spike_threshold_boundary() -> None:
    assert short_spike_reason(80.0) == "融券余额较 5 个交易日前增加 80%"
    assert short_spike_reason(50.0) is not None
    assert short_spike_reason(49.9) is None
    assert short_spike_reason(None) is None


def test_leverage_direction() -> None:
    assert leverage_direction(10.0) == LeverageDirection.ADD_LEVERAGE
    assert leverage_direction(-10.0) == LeverageDirection.DELEVERAGE
    assert leverage_direction(0.0) == LeverageDirection.STABLE
    assert leverage_direction(None) is None
