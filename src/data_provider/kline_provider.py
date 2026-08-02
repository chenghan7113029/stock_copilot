"""K 线数据提供者：Baostock 主 +（可选）AKShare 备 + SQLite 缓存与空洞回填。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable, Protocol

import pandas as pd

from common.config_loader import is_data_source_enabled
from common.exceptions import DataProviderError, KlineUnavailableError
from dao.kline_repo import KlineRepo
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
        *,
        use_akshare: bool = True,
    ) -> None:
        self._repo = repo
        self._baostock = baostock_fetcher or BaostockFetcher()
        self._use_akshare = use_akshare
        self._akshare: _KlineFetcher | None = None
        self._realtime_overlay: RealtimeOverlayProvider | None = realtime_overlay

        if use_akshare:
            if akshare_fetcher is not None:
                self._akshare = akshare_fetcher
            else:
                from data_provider.akshare.fetcher import AKShareFetcher

                self._akshare = AKShareFetcher()
            if self._realtime_overlay is None:
                quote_fetcher = (
                    self._akshare
                    if hasattr(self._akshare, "fetch_realtime_quote")
                    else None
                )
                if quote_fetcher is None:
                    from data_provider.akshare.fetcher import AKShareFetcher

                    quote_fetcher = AKShareFetcher()
                self._realtime_overlay = RealtimeOverlayProvider(quote_fetcher)

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: KlineRepo) -> "KlineProvider":
        """按 data_sources.enabled 决定是否启用 AKShare 备源 / 实时叠加。"""
        return cls(repo, use_akshare=is_data_source_enabled(config, "akshare"))

    def get_kline(
        self,
        code: str,
        days: int = 90,
        use_realtime: bool = False,
        offline: bool = False,
        persist_today: bool = False,
        *,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[pd.DataFrame, list[str], str]:
        """获取 K 线 DataFrame、warnings 与 quote_mode。"""
        norm_code, exchange = normalize_stock_code(code)
        today = date.today()
        end_date = today.strftime("%Y-%m-%d")
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        if offline:
            return self._get_kline_offline(norm_code, start_date, end_date)

        cached_rows = self._repo.query_range(norm_code, start_date, end_date)
        cached_dates = {row["trade_date"] for row in cached_rows}
        warnings: list[str] = []

        if on_progress:
            on_progress(f"K线 正在拉取 {start_date} ~ {end_date}…")

        df_api: pd.DataFrame | None = None
        fetch_error: str | None = None
        try:
            df_api = self._fetch_from_sources(
                norm_code, exchange, start_date, end_date, on_progress=on_progress
            )
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
            if on_progress:
                on_progress(f"K线 拉取完成，共 {len(df)} 行")
            return self._finalize(df, warnings, norm_code, use_realtime, persist_today)

        if cached_rows:
            gap_count = self._estimate_gap_count(cached_rows, start_date, end_date)
            if gap_count > _GAP_WARNING_THRESHOLD:
                warnings.append("K 线数据存在缺口，指标计算可能不准确")
            if fetch_error:
                warnings.append(f"K 线实时拉取失败，已使用缓存数据: {fetch_error}")
            if on_progress:
                on_progress(f"K线 使用缓存（{len(cached_rows)} 行）")
            df = pd.DataFrame(cached_rows).drop(columns=["trade_date"], errors="ignore")
            df = df.sort_values("date").reset_index(drop=True)
            return self._finalize(df, warnings, norm_code, use_realtime, persist_today)

        raise KlineUnavailableError(fetch_error or "K 线数据不可用")

    def _get_kline_offline(
        self,
        norm_code: str,
        start_date: str,
        end_date: str,
    ) -> tuple[pd.DataFrame, list[str], str]:
        """仅读 SQLite 缓存，不触发任何外部 API。"""
        warnings: list[str] = []
        cached_rows = self._repo.query_range(norm_code, start_date, end_date)
        if not cached_rows:
            warnings.append("无K线缓存")
            empty = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            return empty, warnings, "eod"
        df = pd.DataFrame(cached_rows).drop(columns=["trade_date"], errors="ignore")
        df = df.sort_values("date").reset_index(drop=True)
        return df, warnings, "eod"

    def _finalize(
        self,
        df: pd.DataFrame,
        warnings: list[str],
        code: str,
        use_realtime: bool,
        persist_today: bool = False,
    ) -> tuple[pd.DataFrame, list[str], str]:
        quote_mode = "eod"
        if use_realtime:
            if self._realtime_overlay is None:
                warnings.append("实时报价依赖 AKShare，当前未启用，已使用 EOD")
                quote_mode = "eod_fallback"
            else:
                df, quote_mode, overlay_warnings = self._realtime_overlay.overlay(df, code)
                warnings.extend(overlay_warnings)
        if persist_today and use_realtime and not df.empty:
            self._persist_today_row(df, code)
        return df, warnings, quote_mode

    def _persist_today_row(self, df: pd.DataFrame, code: str) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        today_rows = df[df["date"].astype(str).str[:10] == today_str]
        if today_rows.empty:
            return
        row = today_rows.iloc[-1]
        self._repo.upsert_batch(
            [
                {
                    "code": code,
                    "trade_date": today_str,
                    "open": float(row["open"]) if pd.notna(row["open"]) else None,
                    "high": float(row["high"]) if pd.notna(row["high"]) else None,
                    "low": float(row["low"]) if pd.notna(row["low"]) else None,
                    "close": float(row["close"]) if pd.notna(row["close"]) else None,
                    "volume": float(row["volume"]) if pd.notna(row["volume"]) else None,
                }
            ]
        )

    def _fetch_from_sources(
        self,
        code: str,
        exchange: str,
        start_date: str,
        end_date: str,
        *,
        on_progress: Callable[[str], None] | None = None,
    ) -> pd.DataFrame:
        errors: list[str] = []
        sources: list[tuple[_KlineFetcher, str]] = [(self._baostock, "Baostock")]
        if self._akshare is not None:
            sources.append((self._akshare, "AKShare"))
        elif on_progress and not self._use_akshare:
            on_progress("K线 AKShare 未启用，跳过备源")

        for fetcher, name in sources:
            if on_progress:
                on_progress(f"K线 正在从 {name} 拉取…")
            try:
                df = fetcher.fetch_kline(code, exchange, start_date, end_date)
                logger.debug("%s K线获取成功 %s: %d 行", name, code, len(df))
                if on_progress:
                    on_progress(f"K线 {name} 完成（{len(df)} 行）")
                return df
            except (DataProviderError, Exception) as exc:
                logger.warning("%s K线获取失败 %s: %s", name, code, exc)
                if on_progress:
                    on_progress(f"K线 {name} 失败：{exc}")
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
