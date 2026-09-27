"""Tushare 治理事件与北向资金获取器。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.base import normalize_stock_code, retry_with_backoff

logger = logging.getLogger(__name__)

# 治理事件拉取窗口（自然日，覆盖近 90 日）
_EVENT_WINDOW_DAYS = 90
# 北向资金拉取窗口（自然日，覆盖约 5 个交易日）
_NORTHBOUND_WINDOW_DAYS = 12


def _to_ts_code(code: str) -> str:
    digits, exchange = normalize_stock_code(code)
    suffix = {"SH": ".SH", "SZ": ".SZ", "BJ": ".BJ"}.get(exchange)
    if suffix is None:
        raise DataProviderError(f"Tushare 不支持交易所 {exchange!r}")
    return f"{digits}{suffix}"


def _recent_window(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _normalize_date(raw: Any) -> str:
    s = str(raw).strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def _finalize(df: pd.DataFrame, date_cols: tuple[str, ...]) -> pd.DataFrame:
    work = df.copy()
    for col in date_cols:
        if col in work.columns:
            work[col] = work[col].map(_normalize_date)
    return work.reset_index(drop=True)


class TushareEventFetcher:
    """基于 Tushare 的治理事件（增减持/回购/解禁/质押/大宗）+ 北向资金获取器。

    治理接口按 start_date/end_date 拉取近 90 日窗口；返回按事件日期升序、
    日期归一为 YYYY-MM-DD 的 DataFrame。接口无数据时返回空 DataFrame（不视为错误）。
    """

    source_name = "tushare"

    def __init__(self, token: str = "", *, pro: Any | None = None) -> None:
        token = (token or "").strip()
        if pro is not None:
            self._pro = pro
        else:
            if not token:
                raise DataProviderError("Tushare token 为空")
            import tushare as ts

            # 直接用 pro_api(token)，避免 set_token 写 ~/tk.csv
            self._pro = ts.pro_api(token)

    def _fetch_empty_ok(self, name: str, call) -> pd.DataFrame:
        try:
            df = retry_with_backoff(call)
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"Tushare {name} 失败: {exc}") from exc
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def fetch_holder_trade(self, code: str) -> pd.DataFrame:
        ts_code = _to_ts_code(code)
        start, end = _recent_window(_EVENT_WINDOW_DAYS)
        df = self._fetch_empty_ok(
            "stk_holdertrade",
            lambda: self._pro.stk_holdertrade(ts_code=ts_code, start_date=start, end_date=end),
        )
        return _finalize(df, ("ann_date",)) if not df.empty else df

    def fetch_repurchase(self, code: str) -> pd.DataFrame:
        ts_code = _to_ts_code(code)
        start, end = _recent_window(_EVENT_WINDOW_DAYS)
        df = self._fetch_empty_ok(
            "repurchase",
            lambda: self._pro.repurchase(ts_code=ts_code, start_date=start, end_date=end),
        )
        return _finalize(df, ("ann_date", "end_date")) if not df.empty else df

    def fetch_share_float(self, code: str) -> pd.DataFrame:
        ts_code = _to_ts_code(code)
        start, end = _recent_window(_EVENT_WINDOW_DAYS)
        df = self._fetch_empty_ok(
            "share_float",
            lambda: self._pro.share_float(ts_code=ts_code, start_date=start, end_date=end),
        )
        return _finalize(df, ("ann_date", "float_date")) if not df.empty else df

    def fetch_pledge_stat(self, code: str) -> pd.DataFrame:
        ts_code = _to_ts_code(code)
        df = self._fetch_empty_ok("pledge_stat", lambda: self._pro.pledge_stat(ts_code=ts_code))
        return _finalize(df, ("end_date",)) if not df.empty else df

    def fetch_block_trade(self, code: str) -> pd.DataFrame:
        ts_code = _to_ts_code(code)
        start, end = _recent_window(_EVENT_WINDOW_DAYS)
        df = self._fetch_empty_ok(
            "block_trade",
            lambda: self._pro.block_trade(ts_code=ts_code, start_date=start, end_date=end),
        )
        if df.empty:
            return df
        df = _finalize(df, ("trade_date",))
        # 用 daily 收盘价推导相对收盘价折溢价：discount = (close - price) / close * 100
        try:
            daily = self._pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily 收盘价不可用，discount 置 None: %s", exc)
            daily = None
        close_map: dict[str, float] = {}
        if daily is not None and not daily.empty:
            for _, row in daily.iterrows():
                close_map[_normalize_date(row.get("trade_date"))] = float(row.get("close"))
        discounts: list[float | None] = []
        for _, row in df.iterrows():
            close = close_map.get(row["trade_date"])
            price = row.get("price")
            if close and price:
                discounts.append((close - price) / close * 100)
            else:
                discounts.append(None)
        df["discount"] = discounts
        return df

    def fetch_northbound_flow(self) -> pd.DataFrame:
        """拉取近若干交易日市场级北向资金（无 code）。"""
        start, end = _recent_window(_NORTHBOUND_WINDOW_DAYS)
        df = self._fetch_empty_ok(
            "moneyflow_hsgt",
            lambda: self._pro.moneyflow_hsgt(start_date=start, end_date=end),
        )
        if df.empty:
            return df
        work = _finalize(df, ("trade_date",))
        for col in ("north_money", "south_money"):
            work[col] = pd.to_numeric(work[col], errors="coerce")
        return work.sort_values("trade_date").reset_index(drop=True)
