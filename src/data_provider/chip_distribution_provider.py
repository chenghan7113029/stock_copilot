"""筹码分布数据提供者：AKShare 单源 + SQLite 缓存。"""

from __future__ import annotations

from typing import Callable, Protocol

import pandas as pd

from common.exceptions import DataProviderError
from dao.chip_distribution_repo import ChipDistributionRepo
from data_provider.akshare.fetcher import AKShareFetcher


class _ChipDistributionFetcher(Protocol):
    def fetch_chip_distribution(self, code: str) -> pd.DataFrame: ...


class ChipDistributionProvider:
    """获取并缓存 AKShare 服务端计算的日度筹码分布。"""

    def __init__(
        self,
        repo: ChipDistributionRepo,
        akshare_fetcher: _ChipDistributionFetcher | None = None,
    ) -> None:
        self._repo = repo
        self._akshare_fetcher = akshare_fetcher or AKShareFetcher()

    def get_latest(
        self,
        code: str,
        offline: bool = False,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[dict | None, list[str]]:
        """返回最新筹码记录；联网失败时使用本地缓存降级。"""
        cached = self._repo.query_latest(code)
        if offline:
            return (cached, []) if cached is not None else (None, ["无缓存数据"])

        if on_progress:
            on_progress("筹码分布 正在从 AKShare 拉取…")
        try:
            df = self._akshare_fetcher.fetch_chip_distribution(code)
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
