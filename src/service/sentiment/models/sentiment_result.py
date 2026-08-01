"""情绪面确定性分析结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SentimentStatus(Enum):
    EXTREME_FEAR = "极度恐慌"
    FEAR = "恐慌"
    NEUTRAL = "中性"
    GREED = "贪婪"
    EXTREME_GREED = "极度贪婪"


@dataclass
class SentimentAnalysisResult:
    code: str
    market_sentiment_status: SentimentStatus | None
    market_sentiment_score: float | None
    limit_updown_ratio: float | None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
