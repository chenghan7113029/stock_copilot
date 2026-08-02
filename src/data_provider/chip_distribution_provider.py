"""筹码分布数据提供者：AKShare 单源 + SQLite 缓存。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, Protocol

import pandas as pd

from common.config_loader import is_data_source_enabled
from common.exceptions import DataProviderError
from dao.chip_distribution_repo import ChipDistributionRepo

# AKShare stock_cyq_em 偶发长时间无响应；超时后降级，避免拖死整次 sync 事务
_CHIP_FETCH_TIMEOUT_SEC = 45
_AKSHARE_DISABLED_MSG = (
    "筹码分布依赖 AKShare，当前未在 data_sources.enabled 中启用，已跳过联网拉取"
)


class _ChipDistributionFetcher(Protocol):
    def fetch_chip_distribution(self, code: str) -> pd.DataFrame: ...


class ChipDistributionProvider:
    """获取并缓存 AKShare 服务端计算的日度筹码分布。"""

    def __init__(
        self,
        repo: ChipDistributionRepo,
        akshare_fetcher: _ChipDistributionFetcher | None = None,
        *,
        use_akshare: bool = True,
    ) -> None:
        self._repo = repo
        self._use_akshare = use_akshare
        self._akshare_fetcher: _ChipDistributionFetcher | None = None
        if use_akshare:
            if akshare_fetcher is not None:
                self._akshare_fetcher = akshare_fetcher
            else:
                from data_provider.akshare.fetcher import AKShareFetcher

                self._akshare_fetcher = AKShareFetcher()

    @classmethod
    def from_config(
        cls, config: dict[str, Any], repo: ChipDistributionRepo
    ) -> "ChipDistributionProvider":
        """按 data_sources.enabled 决定是否联网拉取筹码（仅 AKShare 支持）。"""
        return cls(repo, use_akshare=is_data_source_enabled(config, "akshare"))

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

        if not self._use_akshare or self._akshare_fetcher is None:
            warnings = [_AKSHARE_DISABLED_MSG]
            if on_progress:
                on_progress("筹码分布 AKShare 未启用，跳过联网拉取")
            if cached is not None:
                warnings.append("已使用缓存数据")
                return cached, warnings
            return None, warnings

        if on_progress:
            on_progress("筹码分布 正在从 AKShare 拉取…")
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._akshare_fetcher.fetch_chip_distribution, code)
                try:
                    df = future.result(timeout=_CHIP_FETCH_TIMEOUT_SEC)
                except FuturesTimeout as exc:
                    future.cancel()
                    raise DataProviderError(
                        f"AKShare 筹码分布超时（>{_CHIP_FETCH_TIMEOUT_SEC}s）"
                    ) from exc
            records = self._to_records(code, df)
            self._repo.upsert_batch(records)
            latest = self._repo.query_latest(code)
            if on_progress:
                on_progress(f"筹码分布 拉取完成，共 {len(records)} 行")
            return latest, []
        except DataProviderError as exc:
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
