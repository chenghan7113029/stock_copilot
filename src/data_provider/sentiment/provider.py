"""市场情绪数据的联网同步与离线读取 Facade。"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from common.exceptions import DataProviderError
from dao.models import MarketSentimentSnapshot
from data_provider.router import DataFetcherRouter
from data_provider.sentiment.akshare_sentiment_fetcher import AkshareSentimentFetcher
from service.sentiment.scorer import calculate_fear_greed_index, calculate_limit_updown_ratio

_NO_SOURCE_MSG = "市场情绪同步无可用数据源（请在 data_sources.enabled 中配置支持情绪的源）"


class _MarketSentimentRepo(Protocol):
    def upsert(self, snapshot_data: dict[str, Any]) -> MarketSentimentSnapshot: ...

    def get_latest(self) -> MarketSentimentSnapshot | None: ...


class MarketSentimentProvider:
    def __init__(
        self,
        repo: _MarketSentimentRepo,
        fetcher: AkshareSentimentFetcher | None = None,
        *,
        use_akshare: bool = True,
    ) -> None:
        self._repo = repo
        self._use_akshare = use_akshare
        self._fetcher: AkshareSentimentFetcher | None = None
        if use_akshare:
            self._fetcher = fetcher or AkshareSentimentFetcher()

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: _MarketSentimentRepo) -> "MarketSentimentProvider":
        """经 Router 判断是否启用 akshare；未启用则不实例化情绪 fetcher。"""
        router = DataFetcherRouter.from_config(config)
        has_akshare = any(f.source_name == "akshare" for f in router.fetchers)
        return cls(repo, use_akshare=has_akshare)

    def fetch_and_persist_today(self) -> dict[str, Any]:
        """联网获取可用分量；市场广度失败时拒绝写入残缺快照。"""
        if not self._use_akshare or self._fetcher is None:
            raise DataProviderError(_NO_SOURCE_MSG)
        breadth = self._fetcher.fetch_market_breadth()
        if not breadth.ok:
            raise DataProviderError(breadth.error or "市场广度接口不可用")

        margin = self._fetcher.fetch_margin_change()
        turnover = self._fetcher.fetch_turnover_percentile()
        ratio, _ = calculate_limit_updown_ratio(
            breadth.data.get("limit_up_count"), breadth.data.get("limit_down_count")
        )
        score, _ = calculate_fear_greed_index(
            ratio,
            margin.data.get("margin_balance_change_pct") if margin.ok else None,
            turnover.data.get("turnover_percentile") if turnover.ok else None,
        )
        snapshot = {
            "trade_date": date.today().isoformat(),
            **breadth.data,
            "margin_balance_change_pct": margin.data.get("margin_balance_change_pct") if margin.ok else None,
            "turnover_percentile": turnover.data.get("turnover_percentile") if turnover.ok else None,
            "fear_greed_index": score,
        }
        self._repo.upsert(snapshot)
        return snapshot

    def get_latest_offline(self) -> MarketSentimentSnapshot | None:
        """严格离线：只读取本地市场级快照。"""
        return self._repo.get_latest()
