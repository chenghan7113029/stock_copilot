"""筹码分布数据提供者：Router 能力链 + SQLite 缓存。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, Protocol, Sequence

import pandas as pd

from common.exceptions import DataProviderError
from dao.chip_distribution_repo import ChipDistributionRepo
from data_provider.router import DataFetcherRouter
from data_provider.strategies import FailoverStrategy

# AKShare stock_cyq_em 偶发长时间无响应；超时后降级，避免拖死整次 sync 事务
_CHIP_FETCH_TIMEOUT_SEC = 45
_NO_SOURCE_MSG = "筹码分布无可用数据源（当前配置未提供 fetch_chip_distribution），已跳过联网拉取"


class _ChipDistributionFetcher(Protocol):
    def fetch_chip_distribution(self, code: str) -> pd.DataFrame: ...


class ChipDistributionProvider:
    """获取并缓存日度筹码分布。"""

    def __init__(
        self,
        repo: ChipDistributionRepo,
        akshare_fetcher: _ChipDistributionFetcher | None = None,
        *,
        use_akshare: bool = True,
        chip_fetchers: Sequence[_ChipDistributionFetcher] | None = None,
    ) -> None:
        self._repo = repo
        if chip_fetchers is not None:
            self._fetchers: list[_ChipDistributionFetcher] = list(chip_fetchers)
        elif use_akshare:
            if akshare_fetcher is not None:
                self._fetchers = [akshare_fetcher]
            else:
                from data_provider.akshare.fetcher import AKShareFetcher

                self._fetchers = [AKShareFetcher()]
        else:
            self._fetchers = []

    @classmethod
    def from_config(
        cls, config: dict[str, Any], repo: ChipDistributionRepo
    ) -> "ChipDistributionProvider":
        """按 Router 收集支持筹码的 fetcher；未启用则不实例化 AKShare。"""
        router = DataFetcherRouter.from_config(config)
        fetchers = router.fetchers_with_method("fetch_chip_distribution")
        return cls(repo, chip_fetchers=fetchers)

    def get_latest(
        self,
        code: str,
        offline: bool = False,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[dict | None, list[str]]:
        """返回最新筹码记录；联网失败时使用本地缓存降级。"""
        cached = self._repo.query_latest(code)
        if offline:
            return (cached, []) if cached is not None else (None, ["无筹码分布缓存"])

        if not self._fetchers:
            warnings = [_NO_SOURCE_MSG]
            if on_progress:
                on_progress("筹码分布 无可用源，跳过联网拉取")
            if cached is not None:
                warnings.append("已使用缓存数据")
                return cached, warnings
            return None, warnings

        if on_progress:
            on_progress("筹码分布 正在按配置源拉取…")
        try:

            def _call(fetcher: _ChipDistributionFetcher) -> pd.DataFrame:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(fetcher.fetch_chip_distribution, code)
                    try:
                        return future.result(timeout=_CHIP_FETCH_TIMEOUT_SEC)
                    except FuturesTimeout as exc:
                        future.cancel()
                        raise DataProviderError(
                            f"筹码分布超时（>{_CHIP_FETCH_TIMEOUT_SEC}s）"
                        ) from exc

            result = FailoverStrategy.try_each(
                self._fetchers,
                _call,
                source_name=lambda f: getattr(f, "source_name", type(f).__name__),
            )
            df = result.value
            records = self._to_records(code, df)
            self._repo.upsert_batch(records)
            latest = self._repo.query_latest(code)
            if on_progress:
                on_progress(
                    f"筹码分布 拉取完成，共 {len(records)} 行（source={result.source_name}）"
                )
            return latest, []
        except (DataProviderError, RuntimeError) as exc:
            warnings = [f"筹码分布数据不可用: {exc}"]
            if cached is not None:
                warnings.append("筹码分布拉取失败，已使用缓存数据")
                return cached, warnings
            return None, warnings

    @staticmethod
    def _to_records(code: str, df: pd.DataFrame) -> list[dict]:
        numeric_columns = (
            "winner_ratio",
            "avg_cost",
            "concentration_90",
            "concentration_70",
            "cost_90_low",
            "cost_90_high",
            "cost_70_low",
            "cost_70_high",
        )
        records: list[dict] = []
        for _, row in df.iterrows():
            record = {"code": code, "trade_date": str(row["trade_date"])[:10]}
            for column in numeric_columns:
                value = row.get(column)
                record[column] = float(value) if pd.notna(value) else None
            records.append(record)
        return records
