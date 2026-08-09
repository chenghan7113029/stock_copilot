"""Baostock 数据源实现。

参考：ref/daily_stock_analysis/data_provider/baostock_fetcher.py
主要提供：行情（最新收盘价）、季频财务（盈利/成长/现金流/偿债）。

关键修复（fix-value-data-pipeline-e2e）：
- `query_*_data(year=0, quarter=0)` 被 Baostock API 拒绝；改为计算上一完整季度，
  失败时向前回溯最多 4 季，彻底解决 "仅落行情" 问题。
- fetch_fundamentals 合并为单次 _session，减少 login/logout 次数（4→1）。

fix-baostock-data-quality：
- net_income TTM = epsTTM × shares_outstanding（退化单季 netProfit）
- historical_pe = 季末收盘价 / epsTTM（最近 2 年）
- FCF 三级推导链（operCashTTM → CFOToOR×revenue → net_income×fcf_rate）
- growth_rate = 2 年 epsTTM CAGR（退化 YOYNI）
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Generator, Optional

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.baostock.field_mapping import (
    CASHFLOW_DATA_FIELD_MAP,
    GROWTH_DATA_FIELD_MAP,
    PROFIT_DATA_FIELD_MAP,
)
from data_provider.base import BaseFetcher, FetchResult
from data_provider.provider import FINANCIAL_STATEMENT_FIELDS

logger = logging.getLogger(__name__)


def _strip_financial_statement_fields(data: dict[str, Any], missing: list[str]) -> None:
    """阶段 B：Baostock 不向外产出低可信财报字段，避免污染多源 merge。"""
    for field in FINANCIAL_STATEMENT_FIELDS:
        if field in data:
            data.pop(field, None)
        if field not in missing:
            missing.append(field)

_DEFAULT_FCF_RATE = 0.85
_CAGR_MIN = -50.0
_CAGR_MAX = 100.0
_PE_MAX = 200.0
_HISTORICAL_PE_MIN_POINTS = 3
_HISTORICAL_PE_QUARTERS = 8


def _parse_bs_value(raw: Any) -> Optional[float]:
    """Baostock 返回字符串，解析为 float；空字符串/异常返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("", "--", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_bs_code(code: str, exchange: str) -> str:
    """将 6 位代码 + 交易所转换为 Baostock 格式（sh.600519）。"""
    prefix = exchange.lower()
    if prefix not in ("sh", "sz"):
        raise DataProviderError(f"Baostock 不支持交易所 {exchange}（仅支持 SH/SZ）")
    return f"{prefix}.{code}"


def _recent_quarters(n: int = 5) -> list[tuple[int, int]]:
    """返回从最近一个完整季度往前 n 个 (year, quarter) 列表。"""
    today = date.today()
    year = today.year
    completed_quarter = (today.month - 1) // 3
    if completed_quarter == 0:
        year -= 1
        completed_quarter = 4

    quarters = []
    q, y = completed_quarter, year
    for _ in range(n):
        quarters.append((y, q))
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return quarters


def _quarter_end_date(year: int, quarter: int) -> date:
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    month, day = month_day[quarter]
    return date(year, month, day)


def _compute_cagr_2y(eps_now: float, eps_2y_ago: float) -> Optional[float]:
    """2 年 epsTTM CAGR（百分比）。"""
    if eps_now <= 0 or eps_2y_ago <= 0:
        return None
    raw = ((eps_now / eps_2y_ago) ** 0.5 - 1) * 100
    if raw < _CAGR_MIN or raw > _CAGR_MAX:
        logger.warning("growth_rate clamped from %.2f%% to [%.0f, %.0f]", raw, _CAGR_MIN, _CAGR_MAX)
        return max(_CAGR_MIN, min(_CAGR_MAX, raw))
    return raw


def _sample_quarter_end_close(
    close_by_date: dict[str, float],
    year: int,
    quarter: int,
    window_days: int = 3,
) -> Optional[float]:
    """取季末 ±window_days 内最近交易日的收盘价。"""
    target = _quarter_end_date(year, quarter)
    best_close: Optional[float] = None
    best_delta = window_days + 1

    for ds, close in close_by_date.items():
        if close is None:
            continue
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
        except ValueError:
            continue
        delta = abs((d - target).days)
        if delta <= window_days and delta < best_delta:
            best_delta = delta
            best_close = close
    return best_close


def _compute_historical_pe(
    eps_by_quarter: dict[tuple[int, int], float],
    closes_by_quarter: dict[tuple[int, int], float],
) -> list[float]:
    """从季末价格与 epsTTM 计算历史 PE 序列。"""
    pes: list[float] = []
    for key, eps in eps_by_quarter.items():
        close = closes_by_quarter.get(key)
        if close is None or eps <= 0:
            continue
        pe = close / eps
        if pe <= 0 or pe > _PE_MAX:
            logger.debug("historical_pe filtered: quarter=%s pe=%.2f", key, pe)
            continue
        pes.append(pe)
    return pes


def _estimate_revenue_ttm(data: dict[str, Any]) -> Optional[float]:
    """估算 TTM 营收：优先 MBRevenue，否则 net_income / margin。"""
    revenue = data.get("revenue")
    if revenue is not None and revenue > 0:
        return revenue

    net_income = data.get("net_income")
    margin = data.get("operating_margin")
    if net_income and margin and margin > 0:
        return net_income / (margin / 100)
    return None


def derive_fcf(data: dict[str, Any], fcf_rate: float = _DEFAULT_FCF_RATE) -> tuple[Optional[float], Optional[str]]:
    """FCF 三级推导：operCashTTM → CFOToOR×revenue → net_income×fcf_rate。"""
    ocf_ttm = data.get("_operating_cashflow_ttm")
    if ocf_ttm is not None and ocf_ttm > 0:
        return ocf_ttm, None

    cfo_to_or = data.get("_cfo_to_or")
    revenue_ttm = _estimate_revenue_ttm(data)
    if cfo_to_or is not None and cfo_to_or > 0 and revenue_ttm and revenue_ttm > 0:
        return (
            cfo_to_or * revenue_ttm,
            "FCF derived from CFOToOR × revenue (operCashTTM unavailable)",
        )

    net_income = data.get("net_income")
    if net_income is not None and net_income > 0:
        return (
            net_income * fcf_rate,
            f"FCF estimated from net_income × {fcf_rate} (config fallback, low confidence)",
        )

    return None, None


class BaostockFetcher(BaseFetcher):
    """Baostock 数据源（第二源）。

    优先级：2
    覆盖范围：SH / SZ（北交所 BJ 不支持，抛 DataProviderError）
    """

    source_name = "baostock"
    priority = 2

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._bs: Any = None
        self._config = config or {}
        value_cfg = self._config.get("value_analysis", {})
        self._fcf_rate = float(value_cfg.get("fcf_rate", _DEFAULT_FCF_RATE))

    def _get_bs(self) -> Any:
        if self._bs is None:
            import baostock as bs
            self._bs = bs
        return self._bs

    @contextmanager
    def _session(self) -> Generator:
        """连接上下文管理器，保证 login/logout 对称。"""
        bs = self._get_bs()
        try:
            lg = bs.login()
            if lg.error_code != "0":
                raise DataProviderError(f"Baostock 登录失败: {lg.error_msg}")
            logger.debug("Baostock 登录成功")
            yield bs
        finally:
            try:
                bs.logout()
            except Exception as e:
                logger.warning("Baostock 登出异常: %s", e)

    def fetch_all(self, code: str, exchange: str) -> FetchResult:
        """行情 + 基本面合并为单次 Baostock 会话（减少 login/logout）。"""
        if exchange == "BJ":
            return FetchResult(
                code=code,
                source=self.source_name,
                error=f"Baostock 不支持北交所代码 {code}",
            )

        data: dict[str, Any] = {}
        missing: list[str] = []
        bs_code = _to_bs_code(code, exchange)

        try:
            with self._session() as bs:
                self._fetch_quote_in_session(bs, bs_code, data, missing)
                self._fetch_profit_in_session(bs, bs_code, data, missing)
                self._fetch_growth_in_session(bs, bs_code, data, missing)
                self._fetch_cashflow_in_session(bs, bs_code, data, missing)
                self._fetch_balance_in_session(bs, bs_code, data, missing)
                self._fetch_historical_pe_in_session(bs, bs_code, data, missing)
                self._derive_fcf_in_session(data, missing)
        except DataProviderError:
            raise
        except Exception as exc:
            logger.warning("Baostock fetch_all 失败 %s: %s", code, exc)
            if data:
                _strip_financial_statement_fields(data, missing)
                return FetchResult(
                    code=code,
                    source=self.source_name,
                    data=data,
                    missing_fields=sorted(set(missing) - set(data.keys())),
                    error=str(exc),
                )
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        if not data:
            return FetchResult(
                code=code,
                source=self.source_name,
                missing_fields=missing,
                error="Baostock 未返回任何字段",
            )

        _strip_financial_statement_fields(data, missing)
        return FetchResult(
            code=code,
            source=self.source_name,
            data=data,
            missing_fields=sorted(set(missing) - set(data.keys())),
        )

    # ── 行情 ─────────────────────────────────────────────────────────────────

    def _fetch_quote_in_session(
        self,
        bs: Any,
        bs_code: str,
        data: dict[str, Any],
        missing: list[str],
    ) -> None:
        """在已有 session 内获取最近一个交易日收盘价。"""
        today = date.today().strftime("%Y-%m-%d")
        rs = bs.query_history_k_data_plus(
            code=bs_code,
            fields="date,close",
            start_date=(date.today().replace(day=1)).strftime("%Y-%m-%d"),
            end_date=today,
            frequency="d",
            adjustflag="3",
        )
        if rs.error_code != "0":
            missing.append("current_price")
            return

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            missing.append("current_price")
            return

        last_row = rows[-1]
        close_idx = rs.fields.index("close") if "close" in rs.fields else 1
        v = _parse_bs_value(last_row[close_idx])
        if v is not None:
            data["current_price"] = v
        else:
            missing.append("current_price")

    def fetch_quote(self, code: str, exchange: str) -> FetchResult:
        """获取最近一个交易日收盘价。"""
        if exchange == "BJ":
            return FetchResult(code=code, source=self.source_name,
                               error=f"Baostock 不支持北交所代码 {code}")
        data: dict[str, Any] = {}
        missing: list[str] = []

        try:
            bs_code = _to_bs_code(code, exchange)
            with self._session() as bs:
                self._fetch_quote_in_session(bs, bs_code, data, missing)

        except DataProviderError:
            raise
        except Exception as exc:
            logger.warning("Baostock quote 失败 %s: %s", code, exc)
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

    def fetch_kline(
        self,
        code: str,
        exchange: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """获取日 K 线 OHLCV（前复权）。"""
        if exchange == "BJ":
            raise DataProviderError(f"Baostock 不支持北交所代码 {code}")

        bs_code = _to_bs_code(code, exchange)
        with self._session() as bs:
            rs = bs.query_history_k_data_plus(
                code=bs_code,
                fields="date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )
            if rs.error_code != "0":
                raise DataProviderError(f"Baostock K线查询失败: {rs.error_msg}")

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())

        if not rows:
            raise DataProviderError(f"Baostock 未查询到 {code} 的 K 线数据")

        df = pd.DataFrame(rows, columns=rs.fields)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = df["date"].astype(str)
        return df[["date", "open", "high", "low", "close", "volume"]]

    # ── 基本面（单次 session，减少 login 次数）───────────────────────────────

    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        """获取季频财务数据（盈利/成长/现金流/偿债），单次 Baostock 会话完成。"""
        if exchange == "BJ":
            return FetchResult(code=code, source=self.source_name,
                               error=f"Baostock 不支持北交所代码 {code}")
        data: dict[str, Any] = {}
        missing: list[str] = []

        bs_code = _to_bs_code(code, exchange)

        try:
            with self._session() as bs:
                self._fetch_profit_in_session(bs, bs_code, data, missing)
                self._fetch_growth_in_session(bs, bs_code, data, missing)
                self._fetch_cashflow_in_session(bs, bs_code, data, missing)
                self._fetch_balance_in_session(bs, bs_code, data, missing)
                self._fetch_historical_pe_in_session(bs, bs_code, data, missing)
                self._derive_fcf_in_session(data, missing)
        except DataProviderError:
            raise
        except Exception as exc:
            logger.warning("Baostock fundamentals 失败 %s: %s", bs_code, exc)
            _strip_financial_statement_fields(data, missing)
            return FetchResult(
                code=code,
                source=self.source_name,
                data=data,
                missing_fields=sorted(set(missing) - set(data.keys())),
                error=str(exc),
            )

        _strip_financial_statement_fields(data, missing)
        return FetchResult(
            code=code,
            source=self.source_name,
            data=data,
            missing_fields=sorted(set(missing) - set(data.keys())),
        )

    # ── 私有：在已有 session 内查询各财务接口 ─────────────────────────────────

    def _query_profit_row(
        self,
        bs: Any,
        bs_code: str,
        year: int,
        quarter: int,
    ) -> Optional[dict]:
        """查询指定季度的 profit_data 单行。"""
        try:
            rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
            if rs.error_code != "0":
                return None
            rows = []
            while rs.next():
                rows.append(dict(zip(rs.fields, rs.get_row_data())))
            return rows[0] if rows else None
        except Exception as e:
            logger.debug("query_profit_data year=%d quarter=%d 异常: %s", year, quarter, e)
            return None

    def _query_with_quarter_fallback(
        self,
        bs: Any,
        query_fn_name: str,
        bs_code: str,
    ) -> tuple[Optional[dict], Optional[tuple[int, int]]]:
        """对 Baostock 季频接口，按最近季度回溯直到取到数据。"""
        for year, quarter in _recent_quarters(5):
            try:
                rs = getattr(bs, query_fn_name)(
                    code=bs_code, year=year, quarter=quarter
                )
                if rs.error_code != "0":
                    logger.debug("%s year=%d quarter=%d 失败: %s",
                                 query_fn_name, year, quarter, rs.error_msg)
                    continue
                rows = []
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
                if rows:
                    logger.debug("%s 命中 year=%d quarter=%d", query_fn_name, year, quarter)
                    return rows[0], (year, quarter)
            except Exception as e:
                logger.debug("%s year=%d quarter=%d 异常: %s", query_fn_name, year, quarter, e)
                continue
        return None, None

    def _fetch_profit_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row, hit_yq = self._query_with_quarter_fallback(bs, "query_profit_data", bs_code)
        if row is None:
            missing.append("profit_data")
            return

        if hit_yq is not None:
            data["_profit_quarter"] = hit_yq

        for col, field_name in PROFIT_DATA_FIELD_MAP.items():
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data[field_name] = v
            elif not field_name.startswith("_"):
                missing.append(field_name)

        eps = data.get("eps")
        shares = data.get("shares_outstanding")
        if eps is not None and shares is not None and shares > 0:
            data["net_income"] = eps * shares
        elif data.get("_quarterly_net_profit") is not None:
            data["net_income"] = data["_quarterly_net_profit"]
            logger.debug(
                "net_income fallback to quarterly netProfit (shares_outstanding unavailable)"
            )

    def _fetch_growth_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        eps_now = data.get("eps")
        profit_q = data.get("_profit_quarter")

        if eps_now is not None and profit_q is not None:
            y, q = profit_q
            row_2y = self._query_profit_row(bs, bs_code, y - 2, q)
            if row_2y is not None:
                eps_2y = _parse_bs_value(row_2y.get("epsTTM"))
                if eps_2y is not None:
                    cagr = _compute_cagr_2y(eps_now, eps_2y)
                    if cagr is not None:
                        data["growth_rate"] = cagr
                        return
                    logger.warning("growth_rate CAGR unavailable (eps_2y <= 0), fallback to YOYNI")

        row, _ = self._query_with_quarter_fallback(bs, "query_growth_data", bs_code)
        if row is None:
            return
        for col, field_name in GROWTH_DATA_FIELD_MAP.items():
            if field_name.startswith("_"):
                continue
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data["growth_rate"] = v

    def _fetch_cashflow_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row, _ = self._query_with_quarter_fallback(bs, "query_cash_flow_data", bs_code)
        if row is None:
            return
        for col, field_name in CASHFLOW_DATA_FIELD_MAP.items():
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data[field_name] = v

    def _fetch_balance_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row, _ = self._query_with_quarter_fallback(bs, "query_balance_data", bs_code)
        if row is None:
            return
        v = _parse_bs_value(row.get("liabilityToAsset"))
        if v is not None:
            data["_liability_to_asset"] = v

    def _fetch_historical_pe_in_session(
        self,
        bs: Any,
        bs_code: str,
        data: dict,
        missing: list,
    ) -> None:
        """从季末收盘价与 epsTTM 计算 historical_pe（最近 2 年）。"""
        quarters = _recent_quarters(_HISTORICAL_PE_QUARTERS)
        eps_by_quarter: dict[tuple[int, int], float] = {}

        for y, q in quarters:
            row = self._query_profit_row(bs, bs_code, y, q)
            if row is None:
                continue
            eps = _parse_bs_value(row.get("epsTTM"))
            if eps is not None and eps > 0:
                eps_by_quarter[(y, q)] = eps

        if len(eps_by_quarter) < _HISTORICAL_PE_MIN_POINTS:
            missing.append("historical_pe")
            return

        today = date.today()
        start = date(today.year - 2, today.month, min(today.day, 28)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        rs = bs.query_history_k_data_plus(
            code=bs_code,
            fields="date,close",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="3",
        )
        if rs.error_code != "0":
            missing.append("historical_pe")
            return

        close_by_date: dict[str, float] = {}
        while rs.next():
            row_data = rs.get_row_data()
            if len(row_data) >= 2:
                close = _parse_bs_value(row_data[1])
                if close is not None:
                    close_by_date[str(row_data[0])] = close

        closes_by_quarter: dict[tuple[int, int], float] = {}
        for yq in eps_by_quarter:
            close = _sample_quarter_end_close(close_by_date, yq[0], yq[1])
            if close is not None:
                closes_by_quarter[yq] = close

        pes = _compute_historical_pe(eps_by_quarter, closes_by_quarter)
        if len(pes) >= _HISTORICAL_PE_MIN_POINTS:
            data["historical_pe"] = pes
        else:
            missing.append("historical_pe")

    def _derive_fcf_in_session(self, data: dict, missing: list) -> None:
        fcf, warning = derive_fcf(data, self._fcf_rate)
        if fcf is not None:
            data["fcf"] = fcf
            if warning:
                logger.debug(warning)
                data["_fcf_warning"] = warning
        else:
            missing.append("fcf")
