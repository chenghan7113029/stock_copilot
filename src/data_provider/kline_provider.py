"""K 线数据提供者：Router failover + SQLite 缓存与空洞回填。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable, Protocol, Sequence

import pandas as pd

from common.exceptions import KlineUnavailableError
from dao.kline_repo import KlineRepo
from data_provider.base import normalize_stock_code
from data_provider.realtime_overlay_provider import RealtimeOverlayProvider
from data_provider.router import DataFetcherRouter
from data_provider.strategies import FailoverStrategy

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
        kline_fetchers: Sequence[tuple[_KlineFetcher, str]] | None = None,
    ) -> None:
        self._repo = repo
        self._realtime_overlay: RealtimeOverlayProvider | None = realtime_overlay
        self._last_kline_source: str | None = None

        if kline_fetchers is not None:
            self._kline_sources: list[tuple[_KlineFetcher, str]] = list(kline_fetchers)
            self._use_akshare = any(name == "akshare" for _, name in self._kline_sources)
        else:
            # 单测兼容路径：可注入 mock；未注入时仍可构造 Baostock（仅测试/遗留）
            from data_provider.baostock.fetcher import BaostockFetcher

            baostock = baostock_fetcher or BaostockFetcher()
            sources: list[tuple[_KlineFetcher, str]] = [
                (baostock, getattr(baostock, "source_name", "baostock") or "baostock")
            ]
            self._use_akshare = use_akshare
            if use_akshare:
                if akshare_fetcher is not None:
                    sources.append(
                        (
                            akshare_fetcher,
                            getattr(akshare_fetcher, "source_name", "akshare") or "akshare",
                        )
                    )
                else:
                    from data_provider.akshare.fetcher import AKShareFetcher

                    ak = AKShareFetcher()
                    sources.append((ak, "akshare"))
                if self._realtime_overlay is None:
                    quote_fetcher = sources[-1][0]
                    if hasattr(quote_fetcher, "fetch_realtime_quote"):
                        self._realtime_overlay = RealtimeOverlayProvider(quote_fetcher)
            self._kline_sources = sources

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: KlineRepo) -> "KlineProvider":
        """按 Router 的 enabled+priority 构建 K 线 failover 链与实时叠加链。"""
        router = DataFetcherRouter.from_config(config)
        kline_sources: list[tuple[_KlineFetcher, str]] = []
        for fetcher in router.fetchers_with_method("fetch_kline"):
            kline_sources.append((fetcher, fetcher.source_name))

        quote_fetchers = router.fetchers_with_method("fetch_realtime_quote")
        overlay = (
            RealtimeOverlayProvider.from_fetchers(quote_fetchers) if quote_fetchers else None
        )
        return cls(
            repo,
            kline_fetchers=kline_sources,
            realtime_overlay=overlay,
            use_akshare=any(n == "akshare" for _, n in kline_sources),
        )

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
                src = self._last_kline_source or "?"
                on_progress(f"K线 拉取完成，共 {len(df)} 行（kline_source={src}）")
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
                warnings.append("无可用实时报价数据源，已使用 EOD")
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
        if not self._kline_sources:
            raise KlineUnavailableError("无可用 K 线数据源（请检查 data_sources.enabled）")

        def _call(pair: tuple[_KlineFetcher, str]) -> pd.DataFrame:
            fetcher, name = pair
            if on_progress:
                on_progress(f"K线 正在从 {name} 拉取…")
            df = fetcher.fetch_kline(code, exchange, start_date, end_date)
            if on_progress:
                on_progress(f"K线 {name} 完成（{len(df)} 行）")
            return df

        try:
            result = FailoverStrategy.try_each(
                self._kline_sources,
                _call,
                source_name=lambda pair: pair[1],
            )
        except RuntimeError as exc:
            raise KlineUnavailableError(str(exc)) from exc

        self._last_kline_source = result.source_name
        logger.debug("K线命中源 kline_source=%s code=%s", result.source_name, code)
        return result.value

    @staticmethod
    def _estimate_gap_count(rows: list[dict[str, Any]], start_date: str, end_date: str) -> int:
        if not rows:
            return _GAP_WARNING_THRESHOLD + 1
        dates = sorted(row["trade_date"] for row in rows)
        if dates[0] > start_date or dates[-1] < end_date:
            return _GAP_WARNING_THRESHOLD + 1
        return 0
