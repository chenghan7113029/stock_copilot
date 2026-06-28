"""K 线数据提供者：Baostock 主 + AKShare 备 + SQLite 缓存与空洞回填。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Protocol

import pandas as pd

from common.exceptions import DataProviderError, KlineUnavailableError
from dao.kline_repo import KlineRepo
from data_provider.akshare.fetcher import AKShareFetcher
from data_provider.baostock.fetcher import BaostockFetcher
from data_provider.base import normalize_stock_code
from data_provider.realtime_overlay_provider import RealtimeOverlayProvider

logger = logging.getLogger(__name__)

_GAP_WARNING_THRESHOLD = 5


class _KlineFetcher(Protocol):
    def fetch_kline(
        self, code: str, exchange: str, start_date: str, end_date: str
    ) -> pd.DataFrame: ...


class KlineProvider:
    """K 线统一获取入口，含缓存与空洞检测。"""

    def __init__(
        self,
        repo: KlineRepo,
        baostock_fetcher: _KlineFetcher | None = None,
        akshare_fetcher: _KlineFetcher | None = None,
        realtime_overlay: RealtimeOverlayProvider | None = None,
    ) -> None:
        self._repo = repo
        akshare = akshare_fetcher or AKShareFetcher()
        self._baostock = baostock_fetcher or BaostockFetcher()
        self._akshare = akshare
        quote_fetcher = (
            akshare if hasattr(akshare, "fetch_realtime_quote") else AKShareFetcher()
        )
        self._realtime_overlay = realtime_overlay or RealtimeOverlayProvider(quote_fetcher)

    def get_kline(
        self, code: str, days: int = 90, use_realtime: bool = False
    ) -> tuple[pd.DataFrame, list[str], str]:
        """获取 K 线 DataFrame、warnings 与 quote_mode。"""
        norm_code, exchange = normalize_stock_code(code)
        today = date.today()
        end_date = today.strftime("%Y-%m-%d")
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        cached_rows = self._repo.query_range(norm_code, start_date, end_date)
        cached_dates = {row["trade_date"] for row in cached_rows}
        warnings: list[str] = []

        df_api: pd.DataFrame | None = None
        fetch_error: str | None = None
        try:
            df_api = self._fetch_from_sources(norm_code, exchange, start_date, end_date)
        except KlineUnavailableError as exc:
            fetch_error = str(exc)

        if df_api is not None and not df_api.empty:
            today_str = end_date
            to_cache: list[dict[str, Any]] = []
            for _, row in df_api.iterrows():
                trade_date = str(row["date"])[:10]
                if trade_date >= today_str:
                    continue
                if trade_date not in cached_dates:
                    to_cache.append(
                        {
                            "code": norm_code,
                            "trade_date": trade_date,
                            "open": float(row["open"]) if pd.notna(row["open"]) else None,
                            "high": float(row["high"]) if pd.notna(row["high"]) else None,
                            "low": float(row["low"]) if pd.notna(row["low"]) else None,
                            "close": float(row["close"]) if pd.notna(row["close"]) else None,
                            "volume": float(row["volume"]) if pd.notna(row["volume"]) else None,
                        }
                    )
            if to_cache:
                self._repo.upsert_batch(to_cache)

            merged = self._repo.query_range(norm_code, start_date, end_date)
            df = pd.DataFrame(merged)
            if not df.empty:
                df = df.drop(columns=["trade_date"], errors="ignore")
            else:
                df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

            api_today = df_api[df_api["date"].astype(str).str[:10] == today_str]
            if not api_today.empty:
                today_row = api_today.iloc[-1].to_dict()
                today_row["date"] = today_str
                df = df[df["date"].astype(str) != today_str]
                df = pd.concat([df, pd.DataFrame([today_row])], ignore_index=True)
            elif not df_api.empty:
                last_row = df_api.iloc[-1].to_dict()
                last_row["date"] = str(last_row["date"])[:10]
                last_date = last_row["date"]
                df = df[df["date"].astype(str) != last_date]
                df = pd.concat([df, pd.DataFrame([last_row])], ignore_index=True)

            df = df.sort_values("date").reset_index(drop=True)
            return self._finalize(df, warnings, norm_code, use_realtime)

        if cached_rows:
            gap_count = self._estimate_gap_count(cached_rows, start_date, end_date)
            if gap_count > _GAP_WARNING_THRESHOLD:
                warnings.append("K 线数据存在缺口，指标计算可能不准确")
            if fetch_error:
                warnings.append(f"K 线实时拉取失败，已使用缓存数据: {fetch_error}")
            df = pd.DataFrame(cached_rows).drop(columns=["trade_date"], errors="ignore")
            df = df.sort_values("date").reset_index(drop=True)
            return self._finalize(df, warnings, norm_code, use_realtime)

        raise KlineUnavailableError(fetch_error or "K 线数据不可用")

    def _finalize(
        self,
        df: pd.DataFrame,
        warnings: list[str],
        code: str,
        use_realtime: bool,
    ) -> tuple[pd.DataFrame, list[str], str]:
        quote_mode = "eod"
        if use_realtime:
            df, quote_mode, overlay_warnings = self._realtime_overlay.overlay(df, code)
            warnings.extend(overlay_warnings)
        return df, warnings, quote_mode

    def _fetch_from_sources(
        self,
        code: str,
        exchange: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        errors: list[str] = []
        for fetcher, name in ((self._baostock, "Baostock"), (self._akshare, "AKShare")):
            try:
                df = fetcher.fetch_kline(code, exchange, start_date, end_date)
                logger.debug("%s K线获取成功 %s: %d 行", name, code, len(df))
                return df
            except (DataProviderError, Exception) as exc:
                logger.warning("%s K线获取失败 %s: %s", name, code, exc)
                errors.append(f"{name}: {exc}")
        raise KlineUnavailableError("; ".join(errors))

    @staticmethod
    def _estimate_gap_count(rows: list[dict[str, Any]], start_date: str, end_date: str) -> int:
        if not rows:
            return _GAP_WARNING_THRESHOLD + 1
        dates = sorted(row["trade_date"] for row in rows)
        if dates[0] > start_date or dates[-1] < end_date:
            return _GAP_WARNING_THRESHOLD + 1
        return 0
