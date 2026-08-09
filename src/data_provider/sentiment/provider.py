"""市场情绪数据的联网同步与离线读取 Facade。"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from common.exceptions import DataProviderError
from common.config_loader import resolve_tushare_token
from dao.models import MarketSentimentSnapshot
from data_provider.router import DataFetcherRouter
from data_provider.sentiment.akshare_sentiment_fetcher import AkshareSentimentFetcher
from data_provider.sentiment.tushare_sentiment_fetcher import TushareSentimentFetcher
from service.sentiment.scorer import calculate_fear_greed_index, calculate_limit_updown_ratio

_NO_SOURCE_MSG = "市场情绪同步无可用数据源（请在 data_sources.enabled 中配置 akshare 或 tushare）"


class _MarketSentimentRepo(Protocol):
    def upsert(self, snapshot_data: dict[str, Any]) -> MarketSentimentSnapshot: ...

    def get_latest(self) -> MarketSentimentSnapshot | None: ...


class _SentimentFetcher(Protocol):
    source_name: str

    def fetch_market_breadth(self) -> Any: ...

    def fetch_margin_change(self) -> Any: ...

    def fetch_turnover_percentile(self) -> Any: ...


class MarketSentimentProvider:
    def __init__(
        self,
        repo: _MarketSentimentRepo,
        fetcher: _SentimentFetcher | None = None,
        *,
        use_akshare: bool = True,
    ) -> None:
        self._repo = repo
        self._use_akshare = use_akshare
        self._fetcher: _SentimentFetcher | None = fetcher
        if fetcher is None and use_akshare:
            self._fetcher = AkshareSentimentFetcher()

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: _MarketSentimentRepo) -> "MarketSentimentProvider":
        """按 Router 启用情况选择 akshare 或 tushare 情绪源（优先 akshare）。"""
        router = DataFetcherRouter.from_config(config)
        names = {f.source_name for f in router.fetchers}
        if "akshare" in names:
            return cls(repo, use_akshare=True)
        if "tushare" in names:
            token = resolve_tushare_token(config) or ""
            return cls(repo, TushareSentimentFetcher(token=token), use_akshare=False)
        return cls(repo, use_akshare=False)

    def fetch_and_persist_today(self) -> dict[str, Any]:
        """联网获取可用分量；市场广度失败时拒绝写入残缺快照。"""
        if self._fetcher is None:
            raise DataProviderError(_NO_SOURCE_MSG)
        breadth = self._fetcher.fetch_market_breadth()
        if not breadth.ok:
            raise DataProviderError(breadth.error or "市场广度接口不可用")

        warnings: list[str] = []
        if getattr(self._fetcher, "source_name", "") == "tushare" or breadth.data.get(
            "_breadth_approximation"
        ):
            warnings.append(
                "涨跌停家数为 Tushare daily(pct_chg) 聚合近似，不等同于 limit_list_d 精确名单"
            )

        margin = self._fetcher.fetch_margin_change()
        turnover = self._fetcher.fetch_turnover_percentile()
        if not margin.ok:
            warnings.append(margin.error or "两融分量缺失")
        if not turnover.ok:
            warnings.append(turnover.error or "换手率分位缺失")

        ratio, _ = calculate_limit_updown_ratio(
            breadth.data.get("limit_up_count"), breadth.data.get("limit_down_count")
        )
        score, _ = calculate_fear_greed_index(
            ratio,
            margin.data.get("margin_balance_change_pct") if margin.ok else None,
            turnover.data.get("turnover_percentile") if turnover.ok else None,
        )
        breadth_data = {
            k: v for k, v in breadth.data.items() if not str(k).startswith("_")
        }
        snapshot = {
            "trade_date": date.today().isoformat(),
            **breadth_data,
            "margin_balance_change_pct": margin.data.get("margin_balance_change_pct") if margin.ok else None,
            "turnover_percentile": turnover.data.get("turnover_percentile") if turnover.ok else None,
            "fear_greed_index": score,
            "warnings": warnings,
            "source": getattr(self._fetcher, "source_name", ""),
        }
        self._repo.upsert(snapshot)
        return snapshot

    def get_latest_offline(self) -> MarketSentimentSnapshot | None:
        """严格离线：只读取本地市场级快照。"""
        return self._repo.get_latest()
