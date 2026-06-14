"""Baostock 数据源实现。

参考：ref/daily_stock_analysis/data_provider/baostock_fetcher.py
主要提供：行情（最新收盘价）、季频财务（盈利/成长/现金流/偿债）。

关键修复（fix-value-data-pipeline-e2e）：
- `query_*_data(year=0, quarter=0)` 被 Baostock API 拒绝；改为计算上一完整季度，
  失败时向前回溯最多 4 季，彻底解决 "仅落行情" 问题。
- fetch_fundamentals 合并为单次 _session，减少 login/logout 次数（4→1）。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date
from typing import Any, Generator, Optional

from common.exceptions import DataProviderError
from data_provider.baostock.field_mapping import (
    CASHFLOW_DATA_FIELD_MAP,
    GROWTH_DATA_FIELD_MAP,
    PROFIT_DATA_FIELD_MAP,
)
from data_provider.base import BaseFetcher, FetchResult

logger = logging.getLogger(__name__)


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
    """返回从最近一个完整季度往前 n 个 (year, quarter) 列表。

    Baostock API 要求 quarter 取 1–4，不接受 0。
    调用时按顺序尝试，直到取到数据为止。
    """
    today = date.today()
    year = today.year
    # 当前月份对应已完成的季度
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


class BaostockFetcher(BaseFetcher):
    """Baostock 数据源（第二源）。

    优先级：2
    覆盖范围：SH / SZ（北交所 BJ 不支持，抛 DataProviderError）
    """

    source_name = "baostock"
    priority = 2

    def __init__(self) -> None:
        self._bs: Any = None

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

    # ── 行情 ─────────────────────────────────────────────────────────────────

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
                    return FetchResult(code=code, source=self.source_name,
                                       error=f"Baostock query 失败: {rs.error_msg}")

                rows = []
                while rs.next():
                    rows.append(rs.get_row_data())

                if not rows:
                    missing.append("current_price")
                else:
                    last_row = rows[-1]
                    close_idx = rs.fields.index("close") if "close" in rs.fields else 1
                    v = _parse_bs_value(last_row[close_idx])
                    if v is not None:
                        data["current_price"] = v
                    else:
                        missing.append("current_price")

        except DataProviderError:
            raise
        except Exception as exc:
            logger.warning("Baostock quote 失败 %s: %s", code, exc)
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

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
        except DataProviderError:
            raise
        except Exception as exc:
            logger.warning("Baostock fundamentals 失败 %s: %s", bs_code, exc)
            return FetchResult(code=code, source=self.source_name,
                               data=data, missing_fields=missing, error=str(exc))

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

    # ── 私有：在已有 session 内查询各财务接口 ─────────────────────────────────

    def _query_with_quarter_fallback(
        self,
        bs: Any,
        query_fn_name: str,
        bs_code: str,
    ) -> Optional[dict]:
        """对 Baostock 季频接口，按最近季度回溯直到取到数据。

        返回第一条有效行数据的字典，无数据返回 None。
        """
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
                    return rows[0]
            except Exception as e:
                logger.debug("%s year=%d quarter=%d 异常: %s", query_fn_name, year, quarter, e)
                continue
        return None

    def _fetch_profit_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row = self._query_with_quarter_fallback(bs, "query_profit_data", bs_code)
        if row is None:
            missing.append("profit_data")
            return
        for col, field_name in PROFIT_DATA_FIELD_MAP.items():
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data[field_name] = v
            else:
                missing.append(field_name)

    def _fetch_growth_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row = self._query_with_quarter_fallback(bs, "query_growth_data", bs_code)
        if row is None:
            return
        for col, field_name in GROWTH_DATA_FIELD_MAP.items():
            if field_name.startswith("_"):
                continue
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data[field_name] = v

    def _fetch_cashflow_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row = self._query_with_quarter_fallback(bs, "query_cash_flow_data", bs_code)
        if row is None:
            return
        for col, field_name in CASHFLOW_DATA_FIELD_MAP.items():
            if field_name.startswith("_"):
                continue
            v = _parse_bs_value(row.get(col))
            if v is not None:
                data[field_name] = v

    def _fetch_balance_in_session(self, bs: Any, bs_code: str, data: dict, missing: list) -> None:
        row = self._query_with_quarter_fallback(bs, "query_balance_data", bs_code)
        if row is None:
            return
        v = _parse_bs_value(row.get("liabilityToAsset"))
        if v is not None:
            data["_liability_to_asset"] = v
