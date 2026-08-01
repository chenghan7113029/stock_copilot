"""市场情绪 V1 的确定性评分函数。"""

from __future__ import annotations

from service.sentiment.models.sentiment_result import SentimentStatus

_WEIGHTS = {"breadth": 0.5, "margin": 0.3, "turnover": 0.2}


def calculate_limit_updown_ratio(
    limit_up_count: int | None, limit_down_count: int | None
) -> tuple[float | None, list[str]]:
    """计算涨停占全部涨跌停的比例，避免将缺失数据误作 0。"""
    up = limit_up_count or 0
    down = limit_down_count or 0
    if up + down == 0:
        return None, ["涨跌停家数均为 0，无法计算涨跌停家数比"]
    return up / (up + down), []


def _margin_score(change_pct: float) -> float:
    """将两融余额环比变化裁剪到 [-10%, 10%] 后映射为 0–100。"""
    return max(0.0, min(100.0, 50.0 + max(-10.0, min(10.0, change_pct)) * 5.0))


def calculate_fear_greed_index(
    limit_updown_ratio: float | None,
    margin_balance_change_pct: float | None,
    turnover_percentile: float | None,
) -> tuple[float | None, list[str]]:
    """按可用分量重新归一化计算 0–100 的恐慌贪婪代理指数。"""
    components = {
        "breadth": None if limit_updown_ratio is None else limit_updown_ratio * 100,
        "margin": None if margin_balance_change_pct is None else _margin_score(margin_balance_change_pct),
        "turnover": turnover_percentile,
    }
    available = {key: value for key, value in components.items() if value is not None}
    if not available:
        return None, ["恐慌贪婪指数数据不足，所有分量均缺失"]

    warnings = []
    labels = {"breadth": "涨跌停家数比", "margin": "两融余额", "turnover": "换手率分位"}
    for key in components:
        if key not in available:
            warnings.append(f"{labels[key]}分量缺失，指数基于部分分量计算")

    total_weight = sum(_WEIGHTS[key] for key in available)
    score = sum(float(value) * _WEIGHTS[key] / total_weight for key, value in available.items())
    return round(max(0.0, min(100.0, score)), 2), warnings


def sentiment_status_from_score(score: float | None) -> SentimentStatus | None:
    if score is None:
        return None
    if score < 20:
        return SentimentStatus.EXTREME_FEAR
    if score < 40:
        return SentimentStatus.FEAR
    if score < 60:
        return SentimentStatus.NEUTRAL
    if score < 80:
        return SentimentStatus.GREED
    return SentimentStatus.EXTREME_GREED
