"""Tushare 个股两融（margin_detail）与主力资金流（moneyflow）获取器。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.base import normalize_stock_code, retry_with_backoff

logger = logging.getLogger(__name__)

# 拉取窗口（自然日）：覆盖约 5 个交易日，供近 5 日变化计算
_FETCH_WINDOW_DAYS = 12


def _to_ts_code(code: str) -> str:
    digits, exchange = normalize_stock_code(code)
    suffix = {"SH": ".SH", "SZ": ".SZ", "BJ": ".BJ"}.get(exchange)
    if suffix is None:
        raise DataProviderError(f"Tushare 不支持交易所 {exchange!r}")
    return f"{digits}{suffix}"


def _recent_window() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=_FETCH_WINDOW_DAYS)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _normalize_trade_date(raw: Any) -> str:
    s = str(raw).strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["trade_date"] = work["trade_date"].map(_normalize_trade_date)
    work = work.sort_values("trade_date").reset_index(drop=True)
    return work


class TushareFundFlowFetcher:
    """基于 margin_detail + moneyflow 的个股资金面获取器。

    均按 start_date/end_date 拉取最近若干交易日（2 次 API 调用），
    返回按 trade_date 升序、trade_date 归一为 YYYY-MM-DD 的 DataFrame。
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

    def fetch_margin_detail(self, code: str) -> pd.DataFrame:
        """拉取个股两融明细（金额单位：元；数量单位：股）。"""
        ts_code = _to_ts_code(code)
        start, end = _recent_window()
        try:
            df = retry_with_backoff(
                self._pro.margin_detail,
                ts_code=ts_code,
                start_date=start,
                end_date=end,
            )
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — 包装为统一数据源异常
            raise DataProviderError(f"Tushare margin_detail 失败 [{code}]: {exc}") from exc
        if df is None or df.empty:
            raise DataProviderError(f"Tushare margin_detail 无数据 [{code}]")
        return _finalize(df)

    def fetch_moneyflow(self, code: str) -> pd.DataFrame:
        """拉取个股主力资金流（金额单位：万元）。"""
        ts_code = _to_ts_code(code)
        start, end = _recent_window()
        try:
            df = retry_with_backoff(
                self._pro.moneyflow,
                ts_code=ts_code,
                start_date=start,
                end_date=end,
            )
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"Tushare moneyflow 失败 [{code}]: {exc}") from exc
        if df is None or df.empty:
            raise DataProviderError(f"Tushare moneyflow 无数据 [{code}]")
        return _finalize(df)
