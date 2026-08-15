"""A 股交易日 V1 测试。"""

from __future__ import annotations

from datetime import date

from common.trading_day import is_a_share_trading_day


def test_weekday_is_trading_day():
    assert is_a_share_trading_day(date(2026, 8, 14), holidays=()) is True


def test_weekend_is_not_trading_day():
    assert is_a_share_trading_day(date(2026, 8, 15), holidays=()) is False


def test_configured_holiday_is_not_trading_day():
    assert is_a_share_trading_day(date(2026, 10, 1), holidays=("2026-10-01",)) is False
