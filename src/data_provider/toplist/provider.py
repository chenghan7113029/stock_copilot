"""龙虎榜数据提供者：市场级日快照拉取 + 交易日覆盖水位 + 本地缓存读取。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, NamedTuple, Protocol, Sequence

import pandas as pd

from common.config_loader import is_data_source_enabled, resolve_tushare_token
from common.exceptions import DataProviderError
from dao.top_list_repo import (
    StockTopInstRepo,
    StockTopListRepo,
    TopListSyncMarkerRepo,
)
from data_provider.toplist.tushare_top_list_fetcher import TushareTopListFetcher

logger = logging.getLogger(__name__)

_NO_SOURCE_MSG = "龙虎榜无可用数据源（当前配置未启用 tushare 或 token 为空）"
_PROBE_BACKOFF_DAYS = 5


class TopListRepos(NamedTuple):
    top_list: StockTopListRepo
    top_inst: StockTopInstRepo
    marker: TopListSyncMarkerRepo


@dataclass
class TopListData:
    """个股龙虎榜近期数据（榜单事件 + 席位 + 覆盖水位）。"""

    code: str
    list_records: list[dict[str, Any]]
    inst_records: list[dict[str, Any]]
    covered_dates: list[str]
    data_timestamp: datetime | None = None


class _TopListFetcher(Protocol):
    source_name: str

    def latest_trade_date(self, lookback_days: int = 10) -> str | None: ...

    def recent_trade_dates(self, days: int) -> list[str]: ...

    def fetch_top_list(self, trade_date: str) -> pd.DataFrame: ...

    def fetch_top_inst(self, trade_date: str) -> pd.DataFrame: ...


class TopListProvider:
    """获取并缓存龙虎榜（market-day 快照语义）。"""

    def __init__(
        self,
        repos: TopListRepos,
        fetchers: Sequence[_TopListFetcher] | None = None,
    ) -> None:
        self._repos = repos
        self._fetchers: list[_TopListFetcher] = list(fetchers or [])

    @classmethod
    def from_config(cls, config: dict[str, Any], repos: TopListRepos) -> "TopListProvider":
        """按配置启用情况构建 Tushare 龙虎榜 fetcher；未启用则不实例化。"""
        if is_data_source_enabled(config, "tushare"):
            token = resolve_tushare_token(config)
            if token:
                return cls(repos, [TushareTopListFetcher(token=token)])
        return cls(repos, [])

    # ---------- 交易日解析 ----------

    def resolve_latest_trade_date(self) -> str | None:
        """最近开市交易日（YYYY-MM-DD）；trade_cal 不可用时返回 None。"""
        if not self._fetchers:
            return None
        raw = self._fetchers[0].latest_trade_date()
        if not raw:
            return None
        raw = str(raw)
        if len(raw) >= 8 and raw[:8].isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw[:10]

    @staticmethod
    def _probe_candidates() -> list[str]:
        today = date.today()
        return [(today - timedelta(days=offset)).isoformat() for offset in range(_PROBE_BACKOFF_DAYS)]

    # ---------- 同步 ----------

    def sync_trade_date(
        self, trade_date: str, on_progress: Callable[[str], None] | None = None
    ) -> list[str]:
        """拉取并落库指定交易日龙虎榜；返回 warnings（不抛异常）。"""
        _, warnings = self._sync_day(trade_date, on_progress)
        return warnings

    def sync_latest(
        self, on_progress: Callable[[str], None] | None = None
    ) -> tuple[str | None, list[str]]:
        """同步最近交易日；已覆盖则跳过。trade_cal 失败时向后探测最多 5 个自然日。"""
        if not self._fetchers:
            return None, [_NO_SOURCE_MSG]
        last = self.resolve_latest_trade_date()
        if last is not None:
            if self._repos.marker.has(last):
                if on_progress:
                    on_progress(f"龙虎榜 {last} 已覆盖，跳过拉取")
                return last, []
            rows, warnings = self._sync_day(last, on_progress)
            if rows > 0:
                return last, warnings
            # 当日数据尚未发布：继续向后探测，避免把「未发布」当成功
            probe_warnings = warnings
        else:
            probe_warnings = ["龙虎榜无法确定最近交易日（trade_cal 不可用），尝试退化探测"]

        for candidate in self._probe_candidates():
            rows, warnings = self._sync_day(candidate, on_progress)
            if rows > 0:
                return candidate, [*probe_warnings, *warnings]
        return None, [*probe_warnings, "龙虎榜退化探测未找到可用交易日"]

    def backfill(
        self, days: int, on_progress: Callable[[str], None] | None = None
    ) -> tuple[int, list[str]]:
        """回填最近 ``days`` 个交易日；已覆盖跳过。返回 (成功日数, warnings)。"""
        if not self._fetchers:
            return 0, [_NO_SOURCE_MSG]
        if days <= 0:
            return 0, [f"龙虎榜回填窗口 {days} <= 0，跳过"]
        trade_dates = self._fetchers[0].recent_trade_dates(days)
        if not trade_dates:
            return 0, ["龙虎榜无法获取交易日历（trade_cal 不可用），跳过回填"]
        ok = 0
        warnings: list[str] = []
        for trade_date in trade_dates:
            if self._repos.marker.has(trade_date):
                continue
            rows, day_warnings = self._sync_day(trade_date, on_progress)
            warnings.extend(day_warnings)
            if rows > 0:
                ok += 1
        return ok, warnings

    def _sync_day(
        self, trade_date: str, on_progress: Callable[[str], None] | None = None
    ) -> tuple[int, list[str]]:
        if not self._fetchers:
            return 0, [_NO_SOURCE_MSG]
        trade_date = str(trade_date)[:10]
        fetcher = self._fetchers[0]
        if on_progress:
            on_progress(f"龙虎榜 {trade_date} 拉取…")
        try:
            df = fetcher.fetch_top_list(trade_date)
        except DataProviderError as exc:
            return 0, [f"龙虎榜 top_list 失败 [{trade_date}]: {exc}"]
        except Exception as exc:  # noqa: BLE001 — 单日失败不阻断调用方
            return 0, [f"龙虎榜 top_list 失败 [{trade_date}]: {exc}"]

        if df is None or df.empty:
            return 0, [f"龙虎榜 {trade_date} 无榜单数据（休市或数据未发布，不写覆盖水位）"]

        records = self._to_list_records(df)
        rows = self._repos.top_list.replace_day(trade_date, records)
        warnings: list[str] = []

        try:
            inst_df = fetcher.fetch_top_inst(trade_date)
        except Exception as exc:  # noqa: BLE001 — 机构席位可缺失（权限/网络）
            inst_df = None
            warnings.append(
                f"龙虎榜机构席位接口不可用 [{trade_date}]: {exc}"
                "（已保留 top_list 数据，机构维度降级）"
            )
        if inst_df is not None:
            if inst_df.empty:
                warnings.append(f"龙虎榜 {trade_date} 无机构席位数据")
            else:
                self._repos.top_inst.replace_day(
                    trade_date, self._to_inst_records(inst_df)
                )

        self._repos.marker.mark(trade_date, source=getattr(fetcher, "source_name", None))
        if on_progress:
            on_progress(f"龙虎榜 {trade_date} 完成（{rows} 条上榜明细）")
        return rows, warnings

    # ---------- 离线读取 ----------

    def get_offline(self, code: str, window_days: int) -> TopListData | None:
        """严格离线读取；窗口内既无榜单记录也无覆盖水位时返回 None。"""
        covered = self.covered_dates(window_days)
        since = _window_start(window_days)
        list_records = self._repos.top_list.query_range(code, since)
        inst_records = self._repos.top_inst.query_range(code, since)
        if not list_records and not covered:
            return None
        data_timestamp = None
        for record in [*list_records, *inst_records]:
            fetched_at = record.get("fetched_at")
            if fetched_at is not None:
                data_timestamp = fetched_at if data_timestamp is None else max(data_timestamp, fetched_at)
        return TopListData(
            code=code,
            list_records=list_records,
            inst_records=inst_records,
            covered_dates=covered,
            data_timestamp=data_timestamp,
        )

    def covered_dates(self, window_days: int) -> list[str]:
        return self._repos.marker.covered_dates(_window_start(window_days))

    # ---------- 记录转换 ----------

    @staticmethod
    def _to_list_records(df: pd.DataFrame) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for _, row in df.iterrows():
            key = (str(row["code"]), str(row["trade_date"]), str(row["reason"]))
            if key in seen:  # 源端完全重复行去重
                continue
            seen.add(key)
            record: dict[str, Any] = {
                "code": key[0],
                "trade_date": key[1],
                "reason": key[2],
            }
            for column in (
                "name",
                "close",
                "pct_change",
                "turnover_rate",
                "amount",
                "l_sell",
                "l_buy",
                "l_amount",
                "net_amount",
                "net_rate",
                "amount_rate",
                "float_values",
            ):
                record[column] = row.get(column)
            records.append(record)
        return records

    @staticmethod
    def _to_inst_records(df: pd.DataFrame) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            record: dict[str, Any] = {
                "code": str(row["code"]),
                "trade_date": str(row["trade_date"]),
            }
            for column in ("side", "exalter", "buy", "buy_rate", "sell", "sell_rate", "net_buy", "reason"):
                record[column] = row.get(column)
            records.append(record)
        return records


def _window_start(window_days: int) -> str:
    return (date.today() - timedelta(days=max(window_days, 0))).isoformat()
