"""治理事件与北向资金数据提供者：Router 能力链 + 逐接口降级 + 离线缓存。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, NamedTuple, Protocol, Sequence

import pandas as pd

from common.config_loader import is_data_source_enabled, resolve_tushare_token
from common.exceptions import DataProviderError
from dao.event_repo import (
    BlockTradeRepo,
    HolderTradeRepo,
    NorthboundFlowRepo,
    PledgeStatRepo,
    RepurchaseRepo,
    ShareFloatRepo,
)
from data_provider.event.tushare_event_fetcher import TushareEventFetcher

logger = logging.getLogger(__name__)

_HOLDER_COLUMNS = ("holder_name", "holder_type", "in_de", "change_vol", "change_ratio")
_REPURCHASE_COLUMNS = ("proc", "vol", "amount")
_SHARE_FLOAT_COLUMNS = ("ann_date", "float_share", "float_ratio")
_PLEDGE_COLUMNS = ("pledge_ratio", "unrest_pledge", "total_share")
_BLOCK_COLUMNS = ("price", "vol", "amount", "discount")

_QUERY_DAYS = 200  # 足够覆盖近 90 日事件窗口
_NORTHBOUND_DAYS = 5
_NO_SOURCE_MSG = "治理事件无可用数据源（当前配置未启用 tushare）"


class EventRepos(NamedTuple):
    holder_trade: HolderTradeRepo
    repurchase: RepurchaseRepo
    share_float: ShareFloatRepo
    pledge_stat: PledgeStatRepo
    block_trade: BlockTradeRepo
    northbound: NorthboundFlowRepo


@dataclass
class EventData:
    """个股治理事件 + 市场级北向资金的近期数据集合。"""

    code: str
    holder_trade_records: list[dict[str, Any]]
    repurchase_records: list[dict[str, Any]]
    share_float_records: list[dict[str, Any]]
    pledge_records: list[dict[str, Any]]
    block_trade_records: list[dict[str, Any]]
    northbound_records: list[dict[str, Any]]
    data_timestamp: datetime | None = None


class _EventFetcher(Protocol):
    source_name: str

    def fetch_holder_trade(self, code: str) -> pd.DataFrame: ...

    def fetch_repurchase(self, code: str) -> pd.DataFrame: ...

    def fetch_share_float(self, code: str) -> pd.DataFrame: ...

    def fetch_pledge_stat(self, code: str) -> pd.DataFrame: ...

    def fetch_block_trade(self, code: str) -> pd.DataFrame: ...

    def fetch_northbound_flow(self) -> pd.DataFrame: ...


class EventProvider:
    """获取并缓存个股治理事件与市场级北向资金。"""

    def __init__(
        self,
        repos: EventRepos,
        fetchers: Sequence[_EventFetcher] | None = None,
    ) -> None:
        self._repos = repos
        self._fetchers: list[_EventFetcher] = list(fetchers or [])

    @classmethod
    def from_config(
        cls, config: dict[str, Any], repos: EventRepos
    ) -> "EventProvider":
        """按配置启用情况构建 Tushare 治理事件 fetcher；未启用则不实例化。

        说明：治理事件使用独立 `TushareEventFetcher`（标准 Router 只构建价值面
        `TushareFetcher`，不含各治理接口，无法经 `fetchers_with_method` 发现），
        故仿照 `MarketSentimentProvider.from_config` 直接实例化。
        """
        if is_data_source_enabled(config, "tushare"):
            token = resolve_tushare_token(config)
            if token:
                return cls(repos, [TushareEventFetcher(token=token)])
        return cls(repos, [])

    def sync(self, code: str, on_progress: Callable[[str], None] | None = None) -> list[str]:
        """逐接口拉取该股治理事件并落库；单接口失败降级，返回 warnings。"""
        if not self._fetchers:
            return [_NO_SOURCE_MSG]
        fetcher = self._fetchers[0]
        warnings: list[str] = []
        tasks = (
            ("股东增减持", fetcher.fetch_holder_trade, self._repos.holder_trade, "ann_date", _HOLDER_COLUMNS),
            ("回购", fetcher.fetch_repurchase, self._repos.repurchase, "ann_date", _REPURCHASE_COLUMNS),
            ("解禁", fetcher.fetch_share_float, self._repos.share_float, "float_date", _SHARE_FLOAT_COLUMNS),
            ("质押", fetcher.fetch_pledge_stat, self._repos.pledge_stat, "end_date", _PLEDGE_COLUMNS),
            ("大宗", fetcher.fetch_block_trade, self._repos.block_trade, "trade_date", _BLOCK_COLUMNS),
        )
        for label, fetch_fn, repo, date_field, columns in tasks:
            if on_progress:
                on_progress(f"治理事件 {label} 拉取…")
            try:
                df = fetch_fn(code)
                records = self._to_records(code, df, date_field, columns)
                repo.upsert_batch(records)
            except DataProviderError as exc:
                warnings.append(f"{label} 接口失败: {exc}")
            except Exception as exc:  # noqa: BLE001 — 单接口失败不阻断其余
                warnings.append(f"{label} 接口失败: {exc}")
        return warnings

    def fetch_northbound_flow(self) -> list[str]:
        """拉取市场级北向资金并落库；失败返回 warnings。"""
        if not self._fetchers:
            return [_NO_SOURCE_MSG]
        fetcher = self._fetchers[0]
        try:
            df = fetcher.fetch_northbound_flow()
            records: list[dict[str, Any]] = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "trade_date": str(row["trade_date"])[:10],
                        "north_money": _safe_float(row.get("north_money")),
                        "south_money": _safe_float(row.get("south_money")),
                    }
                )
            self._repos.northbound.upsert_batch(records)
            return []
        except Exception as exc:  # noqa: BLE001
            return [f"北向资金接口失败: {exc}"]

    def get_latest(
        self,
        code: str,
        offline: bool = False,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[EventData | None, list[str]]:
        cached = self.get_latest_offline(code)
        if offline:
            return (cached, []) if cached is not None else (None, ["无治理事件缓存"])
        if not self._fetchers:
            warnings = [_NO_SOURCE_MSG]
            if cached is not None:
                warnings.append("已使用缓存数据")
                return cached, warnings
            return None, warnings
        warnings = self.sync(code, on_progress=on_progress)
        data = self.get_latest_offline(code)
        return data, warnings

    def get_latest_offline(self, code: str) -> EventData | None:
        holder = self._repos.holder_trade.query_range(code, _QUERY_DAYS)
        repurchase = self._repos.repurchase.query_range(code, _QUERY_DAYS)
        share_float = self._repos.share_float.query_range(code, _QUERY_DAYS)
        pledge = self._repos.pledge_stat.query_range(code, _QUERY_DAYS)
        block = self._repos.block_trade.query_range(code, _QUERY_DAYS)
        northbound = self._repos.northbound.query_northbound(_NORTHBOUND_DAYS)
        if not any((holder, repurchase, share_float, pledge, block)):
            return None
        data_timestamp = None
        for rec in reversed(holder + repurchase + share_float + pledge + block):
            if rec.get("fetched_at") is not None:
                data_timestamp = rec["fetched_at"]
                break
        return EventData(
            code=code,
            holder_trade_records=holder,
            repurchase_records=repurchase,
            share_float_records=share_float,
            pledge_records=pledge,
            block_trade_records=block,
            northbound_records=northbound,
            data_timestamp=data_timestamp,
        )

    @staticmethod
    def _to_records(
        code: str, df: pd.DataFrame, date_field: str, columns: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            record: dict[str, Any] = {
                "code": code,
                date_field: str(row[date_field])[:10],
            }
            for column in columns:
                value = row.get(column)
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    record[column] = None
                elif isinstance(value, (int, float, bool)):
                    record[column] = float(value)
                else:
                    record[column] = str(value)
            records.append(record)
        return records


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
