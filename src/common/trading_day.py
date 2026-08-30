"""A 股交易日判断 V1：周一至周五，且不在可配置休市日。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable


def is_a_share_trading_day(
    day: date | datetime | None = None,
    holidays: Iterable[str] = (),
) -> bool:
    if day is None:
        day = date.today()
    if isinstance(day, datetime):
        day = day.date()
    if day.weekday() >= 5:
        return False
    holiday_set = {str(item).strip() for item in holidays if str(item).strip()}
    return day.isoformat() not in holiday_set
