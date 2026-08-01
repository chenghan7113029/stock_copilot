"""价值面报告的锚定防御呈现规则。"""

from __future__ import annotations

from dao.kline_repo import KlineRepo


def percentile_band(price_percentile: float) -> str:
    """将估值区间分位映射为定性分档；边界值归入较高一档。"""
    if price_percentile < 20:
        return "历史估值区间低位"
    if price_percentile < 40:
        return "历史估值区间中低位"
    if price_percentile < 60:
        return "历史估值区间中性"
    if price_percentile < 80:
        return "历史估值区间中高位"
    return "历史估值区间高位"


def historical_high(code: str, kline_repo: KlineRepo) -> tuple[float, int] | None:
    """从本地 K 线缓存计算可得数据窗口内的最高价，不触发网络请求。"""
    records = kline_repo.list_by_code(code)
    if not records:
        return None

    prices = [
        price
        for record in records
        for price in (record.get("high"), record.get("close"))
        if price is not None
    ]
    if not prices:
        return None
    return max(prices), len(records)
