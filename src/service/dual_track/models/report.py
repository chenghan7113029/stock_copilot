"""双轨分析输出契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from service.tech.models.tech_result import TechAnalysisResult
from service.value.models.analysis_result import ValueAnalysisResult
from service.sentiment.models.sentiment_result import SentimentAnalysisResult


class CombinedSignal(Enum):
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    WAIT = "观望"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"


class ValueRating(Enum):
    UNDERVALUED = "低估"
    FAIR = "合理"
    OVERVALUED = "高估"
    UNKNOWN = "未知"


@dataclass
class DualTrackReport:
    code: str
    value_result: ValueAnalysisResult | None = None
    tech_result: TechAnalysisResult | None = None
    sentiment_result: SentimentAnalysisResult | None = None
    combined_signal: CombinedSignal = CombinedSignal.WAIT
    value_rating: ValueRating | None = None
    analysis_summary: str = ""
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
