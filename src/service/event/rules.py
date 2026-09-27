"""治理事件面确定性规则：减持聚合、回购状态、解禁窗口、质押、大宗折价、北向净流入。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# 各事实 flag 的时间窗口与阈值（模块内可调常量）
HOLDER_WINDOW_DAYS = 90
REPURCHASE_WINDOW_DAYS = 90
UNLOCK_WINDOW_DAYS = 30
BLOCK_WINDOW_DAYS = 30
NORTHBOUND_WINDOW_DAYS = 5
# 视为「回购进行中/完成」的 proc 状态
REPURCHASE_ACTIVE_PROCS = ("实施", "完成")


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def compute_holder_net_sell(
    records: list[dict[str, Any]], today: date
) -> tuple[float | None, list[str]]:
    """近 90 日股东净减持（股）= 减持方向 change_vol 之和 - 增持方向 change_vol 之和。"""
    cutoff = today - timedelta(days=HOLDER_WINDOW_DAYS)
    sell = buy = 0.0
    found = False
    for r in records:
        d = _to_date(r.get("ann_date"))
        if d is None or d < cutoff:
            continue
        found = True
        vol = r.get("change_vol") or 0.0
        if r.get("in_de") == "DE":
            sell += vol
        elif r.get("in_de") == "IN":
            buy += vol
    if not found:
        return None, ["股东增减持数据不足"]
    return sell - buy, []


def compute_repurchase_active(
    records: list[dict[str, Any]], today: date
) -> tuple[bool, list[str]]:
    """近 90 日是否存在实施/完成状态的回购。"""
    cutoff = today - timedelta(days=REPURCHASE_WINDOW_DAYS)
    for r in records:
        d = _to_date(r.get("ann_date"))
        if d is None or d < cutoff:
            continue
        if r.get("proc") in REPURCHASE_ACTIVE_PROCS:
            return True, []
    return False, []


def compute_upcoming_unlock_30d(
    records: list[dict[str, Any]], today: date
) -> tuple[float | None, list[str]]:
    """未来 30 日解禁占比（%）= 解禁日落在 [today, today+30] 的 float_ratio 之和。"""
    end = today + timedelta(days=UNLOCK_WINDOW_DAYS)
    total_ratio = 0.0
    found = False
    for r in records:
        d = _to_date(r.get("float_date"))
        if d is None or d < today or d > end:
            continue
        found = True
        total_ratio += r.get("float_ratio") or 0.0
    if not found:
        return None, ["未来 30 日无解禁数据"]
    return total_ratio, []


def compute_pledge_ratio(records: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    """最新一条质押比例的 pledge_ratio。"""
    for r in reversed(records):
        pr = r.get("pledge_ratio")
        if pr is not None:
            return pr, []
    return None, ["质押数据不足"]


def compute_block_trade_discount(
    records: list[dict[str, Any]], today: date
) -> tuple[float | None, list[str]]:
    """近 30 日大宗平均折价（%）= discount 列的平均值。"""
    cutoff = today - timedelta(days=BLOCK_WINDOW_DAYS)
    discounts: list[float] = []
    for r in records:
        d = _to_date(r.get("trade_date"))
        if d is None or d < cutoff:
            continue
        disc = r.get("discount")
        if disc is not None:
            discounts.append(disc)
    if not discounts:
        return None, ["近 30 日无大宗交易数据"]
    return sum(discounts) / len(discounts), []


def compute_northbound_net_inflow(
    records: list[dict[str, Any]],
) -> tuple[float | None, list[str]]:
    """北向近 5 日净流入（市场级）= north_money 之和；数据不足 5 日按可用交易日累计。"""
    values = [r.get("north_money") for r in records if r.get("north_money") is not None]
    if not values:
        return None, ["北向资金数据不足"]
    warnings = []
    if len(values) < NORTHBOUND_WINDOW_DAYS:
        warnings.append(f"北向资金数据不足 {NORTHBOUND_WINDOW_DAYS} 日，按 {len(values)} 日累计")
    return sum(values), warnings
