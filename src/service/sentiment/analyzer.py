"""市场情绪确定性分析 Facade。"""

from __future__ import annotations

from typing import Any

from dao.engine import Base, create_db_engine, make_session_factory
from dao.market_sentiment_repo import MarketSentimentRepo
from dao.models import MarketSentimentSnapshot  # noqa: F401
from data_provider.sentiment.provider import MarketSentimentProvider
from service.sentiment.models.sentiment_result import SentimentAnalysisResult
from service.sentiment.scorer import (
    calculate_fear_greed_index,
    calculate_limit_updown_ratio,
    sentiment_status_from_score,
)


class SentimentAnalyzer:
    def __init__(self, provider: MarketSentimentProvider) -> None:
        self._provider = provider

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SentimentAnalyzer":
        engine = create_db_engine(config)
        Base.metadata.create_all(engine)
        session = make_session_factory(engine)()
        return cls(
            MarketSentimentProvider.from_config(config, MarketSentimentRepo(session))
        )

    def analyze(self, code: str) -> SentimentAnalysisResult:
        snapshot = self._provider.fetch_and_persist_today()
        return self._build_result(code, snapshot)

    def analyze_offline(self, code: str) -> SentimentAnalysisResult | None:
        snapshot = self._provider.get_latest_offline()
        if snapshot is None:
            return None
        return self._build_result(code, snapshot)

    @staticmethod
    def _build_result(code: str, snapshot: Any) -> SentimentAnalysisResult:
        get = snapshot.get if isinstance(snapshot, dict) else lambda name: getattr(snapshot, name, None)
        ratio, ratio_warnings = calculate_limit_updown_ratio(
            get("limit_up_count"), get("limit_down_count")
        )
        score, score_warnings = calculate_fear_greed_index(
            ratio, get("margin_balance_change_pct"), get("turnover_percentile")
        )
        status = sentiment_status_from_score(score)
        reasons = [
            f"涨跌停家数比: {ratio:.1%}" if ratio is not None else "涨跌停家数比不可用",
            f"恐慌贪婪代理指数: {score:.1f}" if score is not None else "恐慌贪婪代理指数不可用",
        ]
        warnings = [
            *ratio_warnings,
            *score_warnings,
            "恐慌贪婪指数为自建代理指标，非官方标准，权重未经历史回测校准",
        ]
        return SentimentAnalysisResult(
            code=code,
            market_sentiment_status=status,
            market_sentiment_score=score,
            limit_updown_ratio=ratio,
            reasons=reasons,
            warnings=warnings,
            data_timestamp=get("fetched_at"),
        )
