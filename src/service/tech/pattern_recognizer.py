"""K 线形态识别（纯规则，无 IO，不参与打分）。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from service.tech.config import PatternParams
from service.tech.models.tech_result import (
    CandlestickPattern,
    PatternSignal,
    TrendStatus,
)

_BEARISH_TRENDS = frozenset(
    {TrendStatus.WEAK_BEAR, TrendStatus.BEAR, TrendStatus.STRONG_BEAR}
)
_BULLISH_TRENDS = frozenset(
    {TrendStatus.WEAK_BULL, TrendStatus.BULL, TrendStatus.STRONG_BULL}
)


def _trade_date(row: Any) -> str:
    if "date" not in getattr(row, "index", []):
        return ""
    return str(row["date"])[:10]


class PatternRecognizer:
    """基于 OHLC 几何规则识别经典 K 线形态。"""

    @classmethod
    def recognize(
        cls,
        df: pd.DataFrame,
        trend_status: TrendStatus,
        params: PatternParams,
    ) -> list[PatternSignal]:
        if df is None or len(df) < 2:
            return []

        latest = df.iloc[-1]
        prev_two = df.iloc[-2:]
        signals: list[PatternSignal] = []

        doji = cls._detect_doji(latest, params)
        if doji is not None:
            signals.append(doji)

        hammer = cls._detect_hammer_or_hanging_man(latest, trend_status, params)
        if hammer is not None:
            signals.append(hammer)

        engulfing = cls._detect_engulfing(prev_two, params)
        if engulfing is not None:
            signals.append(engulfing)

        return signals

    @staticmethod
    def _detect_doji(latest_row: Any, params: PatternParams) -> PatternSignal | None:
        o = float(latest_row["open"])
        h = float(latest_row["high"])
        low = float(latest_row["low"])
        c = float(latest_row["close"])
        amplitude = h - low
        body = abs(c - o)
        if amplitude == 0 or body / amplitude <= params.doji_body_ratio_max:
            return PatternSignal(
                pattern=CandlestickPattern.DOJI,
                direction="中性",
                trade_date=_trade_date(latest_row),
                description="实体占振幅比例较小，多空均衡",
            )
        return None

    @staticmethod
    def _detect_hammer_or_hanging_man(
        latest_row: Any,
        trend_status: TrendStatus,
        params: PatternParams,
    ) -> PatternSignal | None:
        o = float(latest_row["open"])
        h = float(latest_row["high"])
        low = float(latest_row["low"])
        c = float(latest_row["close"])
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - low

        if lower < body * params.hammer_shadow_ratio_min:
            return None
        if upper > body * params.hammer_upper_shadow_ratio_max:
            return None

        trade_date = _trade_date(latest_row)
        if trend_status in _BEARISH_TRENDS:
            return PatternSignal(
                pattern=CandlestickPattern.HAMMER,
                direction="看多",
                trade_date=trade_date,
                description="下跌趋势中出现长下影线，疑似看多反转",
            )
        if trend_status in _BULLISH_TRENDS:
            return PatternSignal(
                pattern=CandlestickPattern.HANGING_MAN,
                direction="看空",
                trade_date=trade_date,
                description="上涨趋势中出现长下影线，疑似看空反转",
            )
        return None

    @staticmethod
    def _detect_engulfing(
        latest_two_rows: pd.DataFrame,
        params: PatternParams,
    ) -> PatternSignal | None:
        del params  # 阈值预留，V1 吞没判定不依赖 PatternParams
        if len(latest_two_rows) < 2:
            return None

        prev = latest_two_rows.iloc[0]
        curr = latest_two_rows.iloc[1]
        prev_o = float(prev["open"])
        prev_c = float(prev["close"])
        curr_o = float(curr["open"])
        curr_c = float(curr["close"])
        trade_date = _trade_date(curr)

        prev_bearish = prev_c < prev_o
        prev_bullish = prev_c > prev_o
        curr_bullish = curr_c > curr_o
        curr_bearish = curr_c < curr_o

        if (
            curr_bullish
            and prev_bearish
            and curr_o <= prev_c
            and curr_c >= prev_o
        ):
            return PatternSignal(
                pattern=CandlestickPattern.BULLISH_ENGULFING,
                direction="看多",
                trade_date=trade_date,
                description="阳线实体完全覆盖前日阴线实体",
            )

        if (
            curr_bearish
            and prev_bullish
            and curr_o >= prev_c
            and curr_c <= prev_o
        ):
            return PatternSignal(
                pattern=CandlestickPattern.BEARISH_ENGULFING,
                direction="看空",
                trade_date=trade_date,
                description="阴线实体完全覆盖前日阳线实体",
            )

        return None
