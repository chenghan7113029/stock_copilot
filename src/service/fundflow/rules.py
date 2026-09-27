"""资金面确定性规则：变化率、主力净流入累计、融券突增与杠杆方向判断。"""

from __future__ import annotations

from typing import Any

from service.fundflow.models.fund_flow_result import LeverageDirection

# 融券余额变化率阈值（默认 +50%），超过则追加「融券余额显著增加」事实陈述
SHORT_SPIKE_THRESHOLD_PCT = 50.0
# 杠杆方向判定阈值：|变化率| <= 该值视为平稳
LEVERAGE_STABLE_THRESHOLD_PCT = 5.0
# 变化率与净流入累计窗口（交易日）
CHANGE_WINDOW_DAYS = 5
MAIN_INFLOW_WINDOW_DAYS = 5


def _change_pct(records: list[dict[str, Any]], field: str) -> tuple[float | None, list[str]]:
    """最新交易日相对 5 个交易日前的变化率（%）；数据不足则退化为最近两日。"""
    if len(records) < 2:
        return None, ["数据不足（少于两个交易日）"]
    latest = records[-1].get(field)
    base_record = records[-CHANGE_WINDOW_DAYS - 1] if len(records) > CHANGE_WINDOW_DAYS else records[-2]
    base = base_record.get(field)
    if latest is None or base is None:
        return None, ["数据不足（缺失历史值）"]
    if base == 0:
        return None, ["数据不足（基期值为 0，无法计算变化率）"]
    return (latest - base) / base * 100, []


def compute_margin_change_pct(margin_records: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    """两融余额（rzrqye）近 5 日变化率（%）。"""
    return _change_pct(margin_records, "rzrqye")


def compute_short_change_pct(margin_records: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    """融券余额（rqye）近 5 日变化率（%）。"""
    return _change_pct(margin_records, "rqye")


def compute_main_net_inflow_5d(
    moneyflow_records: list[dict[str, Any]],
) -> tuple[float | None, list[str]]:
    """主力资金近 5 个交易日净流入累计（万元）。"""
    window = moneyflow_records[-MAIN_INFLOW_WINDOW_DAYS:]
    values = [r.get("net_mf_amount") for r in window if r.get("net_mf_amount") is not None]
    if not values:
        return None, ["主力资金数据不足"]
    return sum(values), []


def leverage_direction(margin_change_pct: float | None) -> LeverageDirection | None:
    """两融余额变化率 → 加杠杆 / 去杠杆 / 平稳。"""
    if margin_change_pct is None:
        return None
    if margin_change_pct > LEVERAGE_STABLE_THRESHOLD_PCT:
        return LeverageDirection.ADD_LEVERAGE
    if margin_change_pct < -LEVERAGE_STABLE_THRESHOLD_PCT:
        return LeverageDirection.DELEVERAGE
    return LeverageDirection.STABLE


def short_spike_reason(short_change_pct: float | None) -> str | None:
    """融券余额突增时返回事实陈述（仅陈述变化幅度，不作方向结论）。"""
    if short_change_pct is not None and short_change_pct >= SHORT_SPIKE_THRESHOLD_PCT:
        return f"融券余额较 5 个交易日前增加 {short_change_pct:.0f}%"
    return None
