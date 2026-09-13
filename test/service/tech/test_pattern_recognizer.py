"""PatternRecognizer 单元测试。"""

from __future__ import annotations

import pandas as pd

from service.tech.config import PatternParams
from service.tech.models.tech_result import CandlestickPattern, TrendStatus
from service.tech.pattern_recognizer import PatternRecognizer


def _row(
    date: str,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> dict[str, object]:
    return {
        "date": date,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1_000_000.0,
    }


def _df(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _patterns(signals) -> set[CandlestickPattern]:
    return {s.pattern for s in signals}


def test_doji_standard_hit():
    # open=10.00, close=10.02, high=10.30, low=9.70 → body/amp ≈ 3.3%
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.30, 9.70, 10.02),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    assert CandlestickPattern.DOJI in _patterns(signals)


def test_doji_large_body_miss():
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.5, 9.9, 10.4),  # body/amp = 0.4/0.6 ≈ 66%
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    assert CandlestickPattern.DOJI not in _patterns(signals)


def test_doji_zero_amplitude_hit():
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.0, 10.0, 10.0),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    assert CandlestickPattern.DOJI in _patterns(signals)


def test_hammer_in_bear_trend():
    # body=0.2, lower=0.6 (>= 2*body), upper=0.1 (<= body)
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.3, 9.2, 10.2),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.BEAR, PatternParams())
    hammer = [s for s in signals if s.pattern == CandlestickPattern.HAMMER]
    assert len(hammer) == 1
    assert hammer[0].direction == "看多"
    assert CandlestickPattern.HANGING_MAN not in _patterns(signals)


def test_hanging_man_in_bull_trend():
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.3, 9.2, 10.2),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.BULL, PatternParams())
    hanging = [s for s in signals if s.pattern == CandlestickPattern.HANGING_MAN]
    assert len(hanging) == 1
    assert hanging[0].direction == "看空"
    assert CandlestickPattern.HAMMER not in _patterns(signals)


def test_hammer_geometry_skipped_on_consolidation():
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.3, 9.2, 10.2),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    patterns = _patterns(signals)
    assert CandlestickPattern.HAMMER not in patterns
    assert CandlestickPattern.HANGING_MAN not in patterns


def test_hammer_geometry_not_satisfied():
    # short lower shadow
    df = _df(
        _row("2025-01-01", 10.0, 10.2, 9.8, 10.1),
        _row("2025-01-02", 10.0, 10.4, 9.9, 10.3),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.BEAR, PatternParams())
    assert CandlestickPattern.HAMMER not in _patterns(signals)


def test_bullish_engulfing_hit():
    df = _df(
        _row("2025-01-01", 10.5, 10.6, 9.9, 10.0),
        _row("2025-01-02", 9.9, 10.8, 9.8, 10.7),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    bull = [s for s in signals if s.pattern == CandlestickPattern.BULLISH_ENGULFING]
    assert len(bull) == 1
    assert bull[0].direction == "看多"
    assert bull[0].trade_date == "2025-01-02"


def test_bearish_engulfing_hit():
    df = _df(
        _row("2025-01-01", 10.0, 10.6, 9.9, 10.5),
        _row("2025-01-02", 10.6, 10.7, 9.7, 9.8),
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    bear = [s for s in signals if s.pattern == CandlestickPattern.BEARISH_ENGULFING]
    assert len(bear) == 1
    assert bear[0].direction == "看空"


def test_engulfing_not_fully_covering():
    df = _df(
        _row("2025-01-01", 10.5, 10.6, 9.9, 10.0),
        _row("2025-01-02", 10.1, 10.4, 10.0, 10.3),  # 未覆盖前日实体
    )
    signals = PatternRecognizer.recognize(df, TrendStatus.CONSOLIDATION, PatternParams())
    assert CandlestickPattern.BULLISH_ENGULFING not in _patterns(signals)


def test_recognize_returns_empty_when_fewer_than_two_rows():
    df = _df(_row("2025-01-01", 10.0, 10.3, 9.7, 10.02))
    assert PatternRecognizer.recognize(df, TrendStatus.BEAR, PatternParams()) == []
