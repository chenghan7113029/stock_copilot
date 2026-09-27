"""个股资金面数据提供者：Router 能力链 + 本地缓存降级。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, NamedTuple, Protocol, Sequence

import pandas as pd

from common.config_loader import is_data_source_enabled, resolve_tushare_token
from common.exceptions import DataProviderError
from dao.fund_flow_repo import StockMarginDetailRepo, StockMoneyFlowRepo
from data_provider.fundflow.tushare_fundflow_fetcher import TushareFundFlowFetcher
from data_provider.strategies import FailoverStrategy

logger = logging.getLogger(__name__)

_MARGIN_COLUMNS = ("rzye", "rqye", "rzrqye", "rzmre", "rzche", "rqyl", "rqmcl")
_MONEYFLOW_COLUMNS = (
    "net_mf_amount",
    "buy_elg_amount",
    "sell_elg_amount",
    "buy_lg_amount",
    "sell_lg_amount",
)
_ANALYSIS_WINDOW_DAYS = 5
_NO_SOURCE_MSG = "资金面无可用数据源（当前配置未提供 fetch_margin_detail / fetch_moneyflow）"


class FundFlowRepos(NamedTuple):
    margin: StockMarginDetailRepo
    moneyflow: StockMoneyFlowRepo


@dataclass
class FundFlowData:
    """个股资金面近期数据（按 trade_date 升序，供确定性分析）。"""

    code: str
    margin_records: list[dict[str, Any]]
    moneyflow_records: list[dict[str, Any]]
    data_timestamp: datetime | None = None


class _FundFlowFetcher(Protocol):
    source_name: str

    def fetch_margin_detail(self, code: str) -> pd.DataFrame: ...

    def fetch_moneyflow(self, code: str) -> pd.DataFrame: ...


class FundFlowProvider:
    """获取并缓存个股两融与主力资金流。"""

    def __init__(
        self,
        repos: FundFlowRepos,
        fetchers: Sequence[_FundFlowFetcher] | None = None,
    ) -> None:
        self._repos = repos
        self._fetchers: list[_FundFlowFetcher] = list(fetchers or [])

    @classmethod
    def from_config(
        cls, config: dict[str, Any], repos: FundFlowRepos
    ) -> "FundFlowProvider":
        """按配置启用情况构建 Tushare 资金面 fetcher；未启用则不实例化。

        说明：个股资金面使用独立 `TushareFundFlowFetcher`（标准 Router 只构建价值面
        `TushareFetcher`，不含 `fetch_margin_detail`/`fetch_moneyflow`，无法经
        `fetchers_with_method` 发现），故仿照 `MarketSentimentProvider.from_config`
        按配置启用情况直接实例化，并遵守「阶段 C 不无参构造 AKShare」约束。
        """
        if is_data_source_enabled(config, "tushare"):
            token = resolve_tushare_token(config)
            if token:
                return cls(repos, [TushareFundFlowFetcher(token=token)])
        return cls(repos, [])

    def get_latest(
        self,
        code: str,
        offline: bool = False,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[FundFlowData | None, list[str]]:
        """返回近期资金面数据；联网失败时降级到本地缓存。"""
        cached = self._read_cached(code)
        if offline:
            return (cached, []) if cached is not None else (None, ["无资金面缓存"])

        if not self._fetchers:
            warnings = [_NO_SOURCE_MSG]
            if on_progress:
                on_progress("资金面 无可用源，跳过联网拉取")
            if cached is not None:
                warnings.append("已使用缓存数据")
                return cached, warnings
            return None, warnings

        if on_progress:
            on_progress("资金面 正在按配置源拉取…")
        try:
            result = FailoverStrategy.try_each(
                self._fetchers,
                lambda fetcher: self._fetch_pair(code, fetcher),
                source_name=lambda f: getattr(f, "source_name", type(f).__name__),
            )
            margin_df, moneyflow_df = result.value
            warnings: list[str] = []
            self._repos.margin.upsert_batch(
                self._to_records(code, margin_df, _MARGIN_COLUMNS)
            )
            if moneyflow_df is not None:
                self._repos.moneyflow.upsert_batch(
                    self._to_records(code, moneyflow_df, _MONEYFLOW_COLUMNS)
                )
            else:
                warnings.append("moneyflow 接口失败，主力资金流字段缺失（已保留两融数据）")
            if on_progress:
                on_progress(f"资金面 拉取完成（source={result.source_name}）")
            return self._read_cached(code), warnings
        except (DataProviderError, RuntimeError) as exc:
            warnings = [f"资金面数据不可用: {exc}"]
            if cached is not None:
                warnings.append("资金面拉取失败，已使用缓存数据")
                return cached, warnings
            return None, warnings

    def get_latest_offline(self, code: str) -> FundFlowData | None:
        """严格离线：只读取本地资金面缓存，无缓存返回 None。"""
        return self._read_cached(code)

    def _fetch_pair(
        self, code: str, fetcher: _FundFlowFetcher
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """margin 失败即抛错（触发 failover）；moneyflow 失败降级为 None。"""
        margin_df = fetcher.fetch_margin_detail(code)
        try:
            moneyflow_df = fetcher.fetch_moneyflow(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("moneyflow 失败，降级为仅两融: %s", exc)
            moneyflow_df = None
        return margin_df, moneyflow_df

    def _read_cached(self, code: str) -> FundFlowData | None:
        margin_records = self._repos.margin.query_range(code, _ANALYSIS_WINDOW_DAYS)
        moneyflow_records = self._repos.moneyflow.query_range(code, _ANALYSIS_WINDOW_DAYS)
        if not margin_records and not moneyflow_records:
            return None
        data_timestamp = None
        for rec in reversed(margin_records):
            if rec.get("fetched_at") is not None:
                data_timestamp = rec["fetched_at"]
                break
        if data_timestamp is None:
            for rec in reversed(moneyflow_records):
                if rec.get("fetched_at") is not None:
                    data_timestamp = rec["fetched_at"]
                    break
        return FundFlowData(
            code=code,
            margin_records=margin_records,
            moneyflow_records=moneyflow_records,
            data_timestamp=data_timestamp,
        )

    @staticmethod
    def _to_records(
        code: str, df: pd.DataFrame, columns: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            record: dict[str, Any] = {
                "code": code,
                "trade_date": str(row["trade_date"])[:10],
            }
            for column in columns:
                value = row.get(column)
                record[column] = float(value) if pd.notna(value) else None
            records.append(record)
        return records
