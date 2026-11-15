"""T2.3 后复权/分段复权适配器（前复权拒绝 + 分红日收益连续 + 缺口报错）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError, InvalidAdjustModeError
from data_provider.backtest.adjust_price import BacktestPriceAdapter, parse_adjust_mode


def row(day: str, close: float, factor: float, **extra) -> dict:
    return {
        "code": "000001",
        "trade_date": day,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "factor": factor,
        **extra,
    }


def test_qfq_rejected_with_reason():
    with pytest.raises(InvalidAdjustModeError) as exc:
        parse_adjust_mode("qfq")
    assert "前复权" in str(exc.value)
    with pytest.raises(InvalidAdjustModeError):
        parse_adjust_mode("forward")


def test_unknown_adjust_rejected():
    with pytest.raises(InvalidAdjustModeError):
        parse_adjust_mode("weird")


def test_no_source_reports_gap():
    with pytest.raises(BacktestDataGapError):
        BacktestPriceAdapter().load_rows(["000001"], "2020-01-01", "2020-12-31", "hfq")


def test_hfq_factor_keeps_dividend_return_continuous():
    rows = [
        row("2020-01-02", 10.0, 1.0),
        # 除权日：原始价 9.0（跌 10%），后复权因子 10/9 → 复权价 10.0，收益连续
        row("2020-01-03", 9.0, 10.0 / 9.0),
    ]
    adapter = BacktestPriceAdapter(fetch=lambda **kwargs: rows)
    series = adapter.load_rows(["000001"], "2020-01-02", "2020-01-03", "hfq")["000001"]
    assert series[0]["close"] == 10.0
    assert series[1]["close"] == pytest.approx(10.0, abs=1e-12)
    holding_return = series[1]["close"] / series[0]["close"] - 1.0
    assert holding_return == pytest.approx(0.0, abs=1e-12)


def test_missing_factor_reports_gap():
    rows = [{"code": "000001", "trade_date": "2020-01-02", "open": 10, "high": 10, "low": 10, "close": 10}]
    adapter = BacktestPriceAdapter(fetch=lambda **kwargs: rows)
    with pytest.raises(BacktestDataGapError) as exc:
        adapter.load_rows(["000001"], "2020-01-02", "2020-01-02", "hfq")
    assert "factor" in str(exc.value)


def test_segmented_hfq_supported():
    rows = [row("2020-01-02", 10.0, 1.0)]
    adapter = BacktestPriceAdapter(fetch=lambda **kwargs: rows)
    series = adapter.load_rows(["000001"], "2020-01-02", "2020-01-02", "segmented_hfq")["000001"]
    assert series[0]["adjust_mode"] == "segmented_hfq"
