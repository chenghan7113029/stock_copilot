"""Tushare 龙虎榜获取器：top_list（每日明细）+ top_inst（机构/营业部席位）。

两个接口都是**市场级日接口**（`trade_date` 必选、无区间参数），故按交易日整日拉取。
`top_inst` 官方标注 5000 积分门槛（本项目 2000 积分档实测可用），调用方必须容忍其失败。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.base import retry_with_backoff

logger = logging.getLogger(__name__)

_TOP_LIST_NUMERIC = (
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
)
_TOP_INST_NUMERIC = ("buy", "buy_rate", "sell", "sell_rate", "net_buy")


def _normalize_trade_date(raw: Any) -> str:
    s = str(raw).strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def _to_code(raw: Any) -> str:
    return str(raw).strip().split(".")[0]


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result


def _safe_str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _finalize(df: pd.DataFrame, numeric: tuple[str, ...]) -> pd.DataFrame:
    work = df.copy()
    work["trade_date"] = work["trade_date"].map(_normalize_trade_date)
    work["code"] = work["ts_code"].map(_to_code)
    for column in numeric:
        if column in work.columns:
            work[column] = work[column].map(_safe_float)
    for column in ("reason", "name", "exalter", "side"):
        if column in work.columns:
            work[column] = work[column].map(_safe_str)
    return work.reset_index(drop=True)


class TushareTopListFetcher:
    """基于 top_list / top_inst 的龙虎榜获取器。"""

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

    def latest_trade_date(self, lookback_days: int = 10) -> str | None:
        """最近开市交易日（YYYYMMDD）；不可用时返回 None，由调用方退化探测。"""
        end = date.today()
        start = end - timedelta(days=lookback_days)
        try:
            cal = self._pro.trade_cal(
                exchange="SSE",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                is_open="1",
            )
        except Exception as exc:  # noqa: BLE001 — 交给调用方退化
            logger.debug("trade_cal 失败: %s", exc)
            return None
        if cal is None or cal.empty or "cal_date" not in cal.columns:
            return None
        opened = cal.sort_values("cal_date")
        return str(opened.iloc[-1]["cal_date"])

    def recent_trade_dates(self, days: int) -> list[str]:
        """最近 ``days`` 个开市交易日（YYYY-MM-DD 升序）；不可用返回空列表。"""
        if days <= 0:
            return []
        end = date.today()
        start = end - timedelta(days=max(days * 2, 14))
        try:
            cal = self._pro.trade_cal(
                exchange="SSE",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                is_open="1",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("trade_cal 失败（recent_trade_dates）: %s", exc)
            return []
        if cal is None or cal.empty or "cal_date" not in cal.columns:
            return []
        opened = sorted(str(value) for value in cal["cal_date"])
        return [_normalize_trade_date(value) for value in opened[-days:]]

    def fetch_top_list(self, trade_date: str) -> pd.DataFrame:
        """拉取指定交易日全市场龙虎榜明细；空结果返回空 DataFrame（非异常）。"""
        day = trade_date.replace("-", "")
        try:
            df = retry_with_backoff(self._pro.top_list, trade_date=day)
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — 包装为统一数据源异常
            raise DataProviderError(f"Tushare top_list 失败 [{trade_date}]: {exc}") from exc
        if df is None or df.empty:
            return pd.DataFrame()
        return _finalize(df, _TOP_LIST_NUMERIC)

    def fetch_top_inst(self, trade_date: str) -> pd.DataFrame:
        """拉取指定交易日全市场龙虎榜席位明细；空结果返回空 DataFrame。"""
        day = trade_date.replace("-", "")
        try:
            df = retry_with_backoff(self._pro.top_inst, trade_date=day)
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"Tushare top_inst 失败 [{trade_date}]: {exc}") from exc
        if df is None or df.empty:
            return pd.DataFrame()
        return _finalize(df, _TOP_INST_NUMERIC)
