"""回测单测夹具（`test/service/backtest/`）。

数值一律是**测试输入**，不是生产默认值（Q4–Q8 / KQ-* 未答复，生产配置留空）。
"""

from __future__ import annotations

import copy

import pytest

from service.backtest.models import BacktestConfig, PriceBar
from service.backtest.registry import ExperimentRegistry

BASE_CONFIG: dict = {
    "results_dir": "results",
    "registry_store_path": "registry.ndjson",
    "segments": ["train", "validation", "out_of_sample"],
    "windows": [20, 60],
    "max_delay_days": 5,
    "min_events": 2,
    "commission": {"rate": 2.5e-4, "min": 5},
    "stamp_tax": {"side": "sell", "rate": 5e-4},
    "transfer_fee": {"rate": 1e-5, "included": False},
    "slippage_tiers": [{"amount_lower": 0, "amount_upper": 1_000_000, "bps": 10}],
    "liquidity_cap": [{"adv_tier": "tier-1", "max_participation": 0.01}],
    "limit_pct": {"board": 0.10, "st": 0.05, "star_chinext": 0.20, "bj": 0.30},
    "seal_definition": "一字板（日终无成交）不可成交；收盘封板但盘中打开可成交且滑点加倍",
    "suspend_source": "tushare",
    "cut_basis": "point_in_time_cross_section",
    "tier_count": 5,
    "recompute_freq": "quarterly",
    "min_group_size": 1,
    "gates": {
        "backtest_pass": {"metric": "excess", "comparator": "gt", "threshold": 0.0},
        "shadow": {"min_months": 6, "max_months": 12, "clock": "natural_month"},
        "direction_agree": {"metric": "excess", "tolerance": 0.0},
        "small_position": {"max_pct": 5},
    },
    "block_length": 5,
    "n_bootstrap": 200,
    "shrink": 0.5,
    "burn_scope": "hypothesis",
    "burn_counts_as_second": ["params", "metrics"],
    "exception_approver": "owner",
    "k_components": ["rule", "param", "cut", "window"],
    "custom_allowed": False,
    "k_cost_per_window": 1,
}


def make_config(**overrides: object) -> dict:
    """深拷贝基础配置并按「a.b」路径覆盖（用于构造缺键变体）。"""
    config = copy.deepcopy(BASE_CONFIG)
    for dotted, value in overrides.items():
        parts = dotted.split(".")
        target = config
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        if value is _DELETE:
            target.pop(parts[-1], None)
        else:
            target[parts[-1]] = value
    return config


class _Delete:
    def __repr__(self) -> str:
        return "<DELETE>"


_DELETE = _Delete()


@pytest.fixture
def config_factory():
    """返回 `make_config(**overrides)`（避免跨测试文件 import conftest）。"""
    return make_config


@pytest.fixture
def trading_date_factory():
    return trading_dates


@pytest.fixture
def cfg_raw() -> dict:
    return make_config()


@pytest.fixture
def cfg(tmp_path) -> BacktestConfig:
    return BacktestConfig.from_config(make_config(), base_dir=tmp_path)


@pytest.fixture
def make_bar():
    def factory(
        code: str = "000001",
        trade_date: str = "2020-01-06",
        close: float = 10.0,
        *,
        amount: float | None = 100_000_000.0,
        avg_amount: float | None = 100_000_000.0,
        limit_up: float | None = 100.0,
        limit_down: float | None = 1.0,
        suspended: bool = False,
        st: bool = False,
        delisted: bool = False,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
    ) -> PriceBar:
        return PriceBar(
            code=code,
            trade_date=trade_date,
            open=close if open_ is None else open_,
            high=close if high is None else high,
            low=close if low is None else low,
            close=close,
            amount=amount,
            avg_amount=avg_amount,
            limit_up_price=limit_up,
            limit_down_price=limit_down,
            suspended=suspended,
            st=st,
            delisted=delisted,
        )

    return factory


@pytest.fixture
def registry(tmp_path):
    return ExperimentRegistry(
        tmp_path / "registry.ndjson",
        clock=lambda: "2026-01-01T00:00:00",
        data_version="test-v1",
        results_dir=tmp_path / "results",
    )


def trading_dates(start: str, count: int) -> list[str]:
    """从 `start` 起连续 `count` 个工作日（交易日历 V1：周一至周五）。"""
    from datetime import date, timedelta

    current = date.fromisoformat(start)
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates
