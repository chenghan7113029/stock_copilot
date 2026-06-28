"""Tushare Pro 数据源实现。

参考：ref/daily_stock_analysis/data_provider/tushare_fetcher.py（只读）
Token 由 SourceManager 注入；无 Token 时不实例化本类。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.base import BaseFetcher, FetchResult
from data_provider.tushare.field_mapping import (
    BALANCE_SHEET_FIELD_MAP,
    CASHFLOW_FIELD_MAP,
    DAILY_BASIC_FIELD_MAP,
    DAILY_FIELD_MAP,
    DIVIDEND_FIELD_MAP,
    FINA_INDICATOR_FIELD_MAP,
    INCOME_FIELD_MAP,
    SCALE_SHARE_WAN_FIELDS,
    SCALE_WAN_FIELDS,
)

logger = logging.getLogger(__name__)


def _to_ts_code(code: str, exchange: str) -> str:
    suffix = {"SH": ".SH", "SZ": ".SZ", "BJ": ".BJ"}.get(exchange.upper())
    if suffix is None:
        raise DataProviderError(f"Tushare 不支持交易所 {exchange!r}")
    return f"{code}{suffix}"


def _safe_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, float) and pd.isna(raw):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _scale_value(field: str, value: float) -> float:
    if field in SCALE_WAN_FIELDS:
        return value * 10_000
    if field in SCALE_SHARE_WAN_FIELDS:
        return value * 10_000
    return value


def _apply_row_map(
    row: pd.Series,
    field_map: dict[str, str],
    data: dict[str, Any],
    missing: list[str],
) -> None:
    for src_col, dst_field in field_map.items():
        if dst_field.startswith("_"):
            continue
        if dst_field in data and data[dst_field] is not None:
            continue
        v = _safe_float(row.get(src_col))
        if v is None:
            if dst_field not in missing:
                missing.append(dst_field)
        else:
            data[dst_field] = _scale_value(dst_field, v)


class TushareFetcher(BaseFetcher):
    """Tushare Pro 数据源（默认第三源，需 Token）。"""

    source_name = "tushare"
    priority = 3

    def __init__(self, token: str) -> None:
        token = (token or "").strip()
        if not token:
            raise DataProviderError("Tushare token 为空")
        import tushare as ts

        ts.set_token(token)
        self._pro = ts.pro_api()

    def fetch_all(self, code: str, exchange: str) -> FetchResult:
        """合并行情与基本面；任一侧有部分数据即视为成功（适配积分不足的 Token）。"""
        quote = self.fetch_quote(code, exchange)
        fundamentals = self.fetch_fundamentals(code, exchange)

        merged_data = {**fundamentals.data, **quote.data}
        merged_missing = list(
            set(quote.missing_fields + fundamentals.missing_fields) - set(merged_data.keys())
        )

        if merged_data:
            return FetchResult(
                code=code,
                source=self.source_name,
                data=merged_data,
                missing_fields=merged_missing,
            )

        err = quote.error or fundamentals.error or "Tushare 未返回任何字段"
        return FetchResult(
            code=code,
            source=self.source_name,
            missing_fields=merged_missing,
            error=err,
        )

    # ── 行情 ─────────────────────────────────────────────────────────────────

    def fetch_quote(self, code: str, exchange: str) -> FetchResult:
        data: dict[str, Any] = {}
        missing: list[str] = []

        try:
            ts_code = _to_ts_code(code, exchange)
        except DataProviderError as exc:
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        try:
            try:
                daily_row = self._fetch_latest_daily(ts_code)
            except Exception as exc:
                logger.info("Tushare daily 不可用 [%s]，尝试 daily_basic: %s", code, exc)
                daily_row = None

            if daily_row is not None:
                _apply_row_map(daily_row, DAILY_FIELD_MAP, data, missing)
                trade_date = str(daily_row.get("trade_date", ""))
                if trade_date:
                    data["data_timestamp"] = datetime.strptime(trade_date, "%Y%m%d").isoformat()

            basic_row = self._try_fetch("daily_basic", lambda: self._fetch_latest_daily_basic(ts_code))
            if basic_row is not None:
                _apply_row_map(basic_row, DAILY_BASIC_FIELD_MAP, data, missing)
                if "data_timestamp" not in data:
                    trade_date = str(basic_row.get("trade_date", ""))
                    if trade_date:
                        data["data_timestamp"] = datetime.strptime(trade_date, "%Y%m%d").isoformat()
                self._derive_price_from_basic(basic_row, data, missing)
        except Exception as exc:
            logger.warning("Tushare 行情获取失败 [%s]: %s", code, exc)
            if data:
                return FetchResult(
                    code=code,
                    source=self.source_name,
                    data=data,
                    missing_fields=sorted(set(missing) - set(data.keys())),
                )
            return FetchResult(
                code=code,
                source=self.source_name,
                data=data,
                missing_fields=missing,
                error=str(exc),
            )

        if "current_price" not in data:
            missing.append("current_price")

        if not data:
            return FetchResult(
                code=code,
                source=self.source_name,
                missing_fields=missing,
                error="Tushare 行情无可用数据",
            )

        return FetchResult(
            code=code,
            source=self.source_name,
            data=data,
            missing_fields=sorted(set(missing) - set(data.keys())),
        )

    # ── 基本面 ───────────────────────────────────────────────────────────────

    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        data: dict[str, Any] = {}
        missing: list[str] = []

        try:
            ts_code = _to_ts_code(code, exchange)
        except DataProviderError as exc:
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        for label, api_name in (
            ("fina_indicator", "fina_indicator"),
            ("income", "income"),
            ("balancesheet", "balancesheet"),
            ("cashflow", "cashflow"),
        ):
            row = self._try_fetch(label, lambda n=api_name: self._fetch_latest(n, ts_code))
            if row is None:
                continue
            maps = {
                "fina_indicator": FINA_INDICATOR_FIELD_MAP,
                "income": INCOME_FIELD_MAP,
                "balancesheet": BALANCE_SHEET_FIELD_MAP,
                "cashflow": CASHFLOW_FIELD_MAP,
            }[api_name]
            _apply_row_map(row, maps, data, missing)
            if api_name == "cashflow":
                self._derive_fcf(row, data, missing)
            self._set_report_date(data, row)

        dividend = self._try_fetch("dividend", lambda: self._fetch_latest_dividend(ts_code))
        if dividend is not None:
            _apply_row_map(dividend, DIVIDEND_FIELD_MAP, data, missing)

        self._derive_net_debt(data, missing)

        return FetchResult(
            code=code,
            source=self.source_name,
            data=data,
            missing_fields=sorted(set(missing) - set(data.keys())),
        )

    def _try_fetch(self, label: str, fetch_fn) -> Optional[pd.Series]:
        try:
            return fetch_fn()
        except Exception as exc:
            logger.info("Tushare %s 不可用: %s", label, exc)
            return None

    # ── Pro API 封装 ─────────────────────────────────────────────────────────

    def _fetch_latest_daily(self, ts_code: str) -> Optional[pd.Series]:
        end = date.today().strftime("%Y%m%d")
        start = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
        df = self._pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        return df.sort_values("trade_date", ascending=False).iloc[0]

    def _fetch_latest_daily_basic(self, ts_code: str) -> Optional[pd.Series]:
        end = date.today().strftime("%Y%m%d")
        start = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
        df = self._pro.daily_basic(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        return df.sort_values("trade_date", ascending=False).iloc[0]

    def _fetch_latest(self, api_name: str, ts_code: str) -> Optional[pd.Series]:
        fn = getattr(self._pro, api_name)
        df = fn(ts_code=ts_code, limit=8)
        if df is None or df.empty:
            return None
        sort_col = "end_date" if "end_date" in df.columns else "ann_date"
        df = df.sort_values(sort_col, ascending=False)
        if api_name == "income" and "end_date" in df.columns:
            annual = df[df["end_date"].astype(str).str.endswith("1231")]
            if not annual.empty:
                return annual.iloc[0]
        return df.iloc[0]

    def _fetch_latest_dividend(self, ts_code: str) -> Optional[pd.Series]:
        df = self._pro.dividend(ts_code=ts_code, limit=5)
        if df is None or df.empty:
            return None
        sort_col = "end_date" if "end_date" in df.columns else "ann_date"
        return df.sort_values(sort_col, ascending=False).iloc[0]

    @staticmethod
    def _derive_price_from_basic(
        row: pd.Series,
        data: dict[str, Any],
        missing: list[str],
    ) -> None:
        """daily 无权限时，用 total_mv(万元)/total_share(万股) 估算现价。"""
        if data.get("current_price") is not None:
            return
        total_mv = _safe_float(row.get("total_mv"))
        total_share = _safe_float(row.get("total_share"))
        if total_mv and total_share and total_share > 0:
            data["current_price"] = total_mv / total_share
            if "current_price" in missing:
                missing.remove("current_price")

    @staticmethod
    def _set_report_date(data: dict[str, Any], row: pd.Series) -> None:
        if data.get("fundamental_report_date"):
            return
        raw = row.get("end_date") or row.get("ann_date")
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return
        s = str(raw).strip()
        if len(s) >= 8:
            data["fundamental_report_date"] = date(int(s[:4]), int(s[4:6]), int(s[6:8]))

    @staticmethod
    def _derive_net_debt(data: dict[str, Any], missing: list[str]) -> None:
        if data.get("net_debt") is not None:
            return
        cash = data.get("cash")
        if cash is None:
            missing.append("net_debt")
            return
        st_debt = data.get("short_term_debt") or 0
        lt_debt = data.get("long_term_debt") or 0
        data["net_debt"] = st_debt + lt_debt - cash
        if "net_debt" in missing:
            missing.remove("net_debt")

    @staticmethod
    def _derive_fcf(row: pd.Series, data: dict[str, Any], missing: list[str]) -> None:
        if data.get("fcf") is not None:
            return
        ocf = _safe_float(row.get("n_cashflow_act"))
        capex = _safe_float(row.get("c_pay_acq_const_fiolta"))
        if ocf is None:
            missing.append("fcf")
            return
        if capex is not None:
            data["fcf"] = ocf - abs(capex)
        else:
            data["fcf"] = ocf
