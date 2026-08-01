from service.sentiment.models.sentiment_result import SentimentStatus
from service.sentiment.scorer import (
    calculate_fear_greed_index,
    calculate_limit_updown_ratio,
    sentiment_status_from_score,
)


def test_calculate_limit_updown_ratio() -> None:
    ratio, warnings = calculate_limit_updown_ratio(50, 10)

    assert ratio == 50 / 60
    assert warnings == []


def test_calculate_limit_updown_ratio_degrades_when_no_limits() -> None:
    ratio, warnings = calculate_limit_updown_ratio(0, 0)

    assert ratio is None
    assert any("涨跌停家数均为 0" in warning for warning in warnings)


def test_calculate_fear_greed_index_with_all_components() -> None:
    score, warnings = calculate_fear_greed_index(0.8, 10.0, 80.0)

    assert score == 86.0
    assert warnings == []


def test_calculate_fear_greed_index_renormalizes_when_component_missing() -> None:
    score, warnings = calculate_fear_greed_index(0.8, None, 80.0)

    assert score == 80.0
    assert any("两融余额分量缺失" in warning for warning in warnings)


def test_calculate_fear_greed_index_returns_none_when_all_missing() -> None:
    score, warnings = calculate_fear_greed_index(None, None, None)

    assert score is None
    assert any("数据不足" in warning for warning in warnings)


def test_sentiment_status_boundaries() -> None:
    assert sentiment_status_from_score(0) == SentimentStatus.EXTREME_FEAR
    assert sentiment_status_from_score(20) == SentimentStatus.FEAR
    assert sentiment_status_from_score(40) == SentimentStatus.NEUTRAL
    assert sentiment_status_from_score(60) == SentimentStatus.GREED
    assert sentiment_status_from_score(80) == SentimentStatus.EXTREME_GREED
    assert sentiment_status_from_score(None) is None
