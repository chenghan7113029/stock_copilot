"""将实时报价叠加到 K 线 DataFrame 末端（Router failover，禁止默认绑 AKShare）。"""

from __future__ import annotations

import math
from typing import Protocol, Sequence

import pandas as pd

from data_provider.strategies import FailoverStrategy


class _RealtimeQuoteFetcher(Protocol):
    def fetch_realtime_quote(self, code: str) -> dict[str, float | str]: ...


def _is_baostock(fetcher: object) -> bool:
    return getattr(fetcher, "source_name", "") == "baostock"


class RealtimeOverlayProvider:
    """将当日实时报价注入 K 线末端，失败时安全降级。"""

    def __init__(
        self,
        fetcher: _RealtimeQuoteFetcher | None = None,
        *,
        fetchers: Sequence[_RealtimeQuoteFetcher] | None = None,
    ) -> None:
        if fetchers is not None:
            self._fetchers: list[_RealtimeQuoteFetcher] = list(fetchers)
        elif fetcher is not None:
            self._fetchers = [fetcher]
        else:
            # 禁止无参默认 AKShareFetcher()
            self._fetchers = []

    @classmethod
    def from_fetchers(cls, fetchers: Sequence[_RealtimeQuoteFetcher]) -> "RealtimeOverlayProvider":
        return cls(fetchers=fetchers)

    def overlay(self, df: pd.DataFrame, code: str) -> tuple[pd.DataFrame, str, list[str]]:
        warnings: list[str] = []
        if df is None or df.empty:
            warnings.append("K 线为空，无法叠加实时报价")
            return df, "eod_fallback", warnings

        if not self._fetchers:
            warnings.append(
                "无可用实时报价数据源（需 rt_k/实时接口，禁止用历史日线冒充），已降级为 EOD"
            )
            return df.copy(), "eod_fallback", warnings

        try:
            result = FailoverStrategy.try_each(
                self._fetchers,
                lambda f: f.fetch_realtime_quote(code),
                skip=_is_baostock,
            )
            quote = result.value
        except RuntimeError as exc:
            warnings.append(
                f"实时报价获取失败（rt_k/实时接口；未开通权限或接口失败时不会用 daily 冒充），"
                f"已降级为 EOD: {exc}"
            )
            return df.copy(), "eod_fallback", warnings

        close = quote.get("close")
        if close is None or not isinstance(close, (int, float)) or close <= 0 or math.isnan(close):
            warnings.append("实时报价无效（价格为 0 或 NaN），已降级为 EOD")
            return df.copy(), "eod_fallback", warnings

        today = str(quote["date"])[:10]
        row = {
            "date": today,
            "open": float(quote["open"]),
            "high": float(quote["high"]),
            "low": float(quote["low"]),
            "close": float(quote["close"]),
            "volume": float(quote["volume"]),
        }

        work = df.sort_values("date").copy().reset_index(drop=True)
        work["date"] = work["date"].astype(str).str[:10]

        if not work.empty and work.iloc[-1]["date"] == today:
            for col, val in row.items():
                work.at[work.index[-1], col] = val
        else:
            work = pd.concat([work, pd.DataFrame([row])], ignore_index=True)

        return work, "realtime", warnings
