"""Baostock 数据源实现。

参考：ref/daily_stock_analysis/data_provider/baostock_fetcher.py
主要提供：行情（最新收盘价）、季频财务（盈利/成长/现金流/偿债）。

Baostock 特点：
- 免费、无需 token
- 需要显式 login() / logout()
- 财务数据为季频，行情可以到日线

关键差异（相对 daily_stock_analysis 参考）：
- 本项目只需要基本面数据，不需要完整历史 K 线序列
- 缺失字段用 None，不填 0
- 使用上下文管理器管理连接生命周期
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
                # 取最近 5 天，确保非交易日也能拿到最近收盘
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

    # ── 基本面 ────────────────────────────────────────────────────────────────

    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        """获取季频财务数据（盈利/成长/现金流/偿债）。"""
        if exchange == "BJ":
            return FetchResult(code=code, source=self.source_name,
                               error=f"Baostock 不支持北交所代码 {code}")
        data: dict[str, Any] = {}
        missing: list[str] = []

        bs_code = _to_bs_code(code, exchange)

        self._fetch_profit(bs_code, data, missing)
        self._fetch_growth(bs_code, data, missing)
        self._fetch_cashflow(bs_code, data, missing)
        self._fetch_balance(bs_code, data, missing)

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

    # ── 私有：各财务接口 ──────────────────────────────────────────────────────

    def _fetch_profit(self, bs_code: str, data: dict, missing: list) -> None:
        try:
            with self._session() as bs:
                rs = bs.query_profit_data(code=bs_code, year=0, quarter=0)
                if rs.error_code != "0":
                    missing.append("profit_data")
                    return
                rows = []
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
                if not rows:
                    missing.append("profit_data")
                    return
                latest = rows[0]
                for col, field_name in PROFIT_DATA_FIELD_MAP.items():
                    v = _parse_bs_value(latest.get(col))
                    if v is not None:
                        data[field_name] = v
                    else:
                        missing.append(field_name)
        except Exception as exc:
            logger.warning("Baostock profit_data 失败 %s: %s", bs_code, exc)
            missing.append("profit_data")

    def _fetch_growth(self, bs_code: str, data: dict, missing: list) -> None:
        try:
            with self._session() as bs:
                rs = bs.query_growth_data(code=bs_code, year=0, quarter=0)
                if rs.error_code != "0":
                    missing.append("growth_data")
                    return
                rows = []
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
                if not rows:
                    missing.append("growth_data")
                    return
                latest = rows[0]
                for col, field_name in GROWTH_DATA_FIELD_MAP.items():
                    if field_name.startswith("_"):
                        continue
                    v = _parse_bs_value(latest.get(col))
                    if v is not None:
                        data[field_name] = v
        except Exception as exc:
            logger.warning("Baostock growth_data 失败 %s: %s", bs_code, exc)

    def _fetch_cashflow(self, bs_code: str, data: dict, missing: list) -> None:
        try:
            with self._session() as bs:
                rs = bs.query_cash_flow_data(code=bs_code, year=0, quarter=0)
                if rs.error_code != "0":
                    missing.append("cashflow_data")
                    return
                rows = []
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
                if not rows:
                    missing.append("cashflow_data")
                    return
                latest = rows[0]
                for col, field_name in CASHFLOW_DATA_FIELD_MAP.items():
                    if field_name.startswith("_"):
                        continue
                    v = _parse_bs_value(latest.get(col))
                    if v is not None:
                        data[field_name] = v
        except Exception as exc:
            logger.warning("Baostock cashflow_data 失败 %s: %s", bs_code, exc)

    def _fetch_balance(self, bs_code: str, data: dict, missing: list) -> None:
        """偿债能力用于计算资产负债率等，提供辅助校验字段。"""
        try:
            with self._session() as bs:
                rs = bs.query_balance_data(code=bs_code, year=0, quarter=0)
                if rs.error_code != "0":
                    return
                rows = []
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
                if not rows:
                    return
                latest = rows[0]
                # liabilityToAsset 用于存储资产负债率
                v = _parse_bs_value(latest.get("liabilityToAsset"))
                if v is not None:
                    data["_liability_to_asset"] = v
        except Exception as exc:
            logger.warning("Baostock balance_data 失败 %s: %s", bs_code, exc)
