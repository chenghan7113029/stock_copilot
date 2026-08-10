"""Tushare 市场情绪分量获取器（无 AKShare 时的替代路径）。

涨跌停家数为 daily(pct_chg) 聚合近似，不等于 limit_list_d 精确名单。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

from data_provider.base import FetchResult

logger = logging.getLogger(__name__)

# A 股主板近似涨跌停阈值（不含 ST / 科创板 20% 等精细规则）
_LIMIT_PCT = 9.5


class TushareSentimentFetcher:
    """基于 margin + daily 聚合的市场情绪分量。"""

    source_name = "tushare"

    def __init__(self, token: str, *, pro: Any | None = None) -> None:
        token = (token or "").strip()
        if pro is not None:
            self._pro = pro
        else:
            if not token:
                from common.exceptions import DataProviderError

                raise DataProviderError("Tushare token 为空")
            import tushare as ts

            ts.set_token(token)
            self._pro = ts.pro_api()

    def fetch_market_breadth(self) -> FetchResult:
        """用全市场 daily 的 pct_chg 近似涨跌停/涨跌家数。"""
        try:
            trade_date = self._latest_trade_date()
            if trade_date is None:
                raise ValueError("无法确定最近交易日")
            df = self._pro.daily(trade_date=trade_date)
            if df is None or df.empty:
                raise ValueError(f"daily 无数据 trade_date={trade_date}")
            pct = pd.to_numeric(df.get("pct_chg"), errors="coerce").dropna()
            if pct.empty:
                raise ValueError("daily 缺少有效 pct_chg")
            limit_up = int((pct >= _LIMIT_PCT).sum())
            limit_down = int((pct <= -_LIMIT_PCT).sum())
            up_count = int((pct > 0).sum())
            down_count = int((pct < 0).sum())
            return FetchResult(
                source=self.source_name,
                data={
                    "limit_up_count": limit_up,
                    "limit_down_count": limit_down,
                    "up_count": up_count,
                    "down_count": down_count,
                    "_breadth_approximation": True,
                },
            )
        except Exception as exc:
            return FetchResult(
                source=self.source_name,
                error=f"Tushare 市场广度接口不可用: {exc}",
            )

    def fetch_margin_change(self) -> FetchResult:
        """两融余额环比（沪深合计，取最近两个有数据交易日）。"""
        try:
            end = date.today()
            start = end - timedelta(days=14)
            df = self._pro.margin(
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                raise ValueError("margin 无数据")
            work = df.copy()
            if "rzye" not in work.columns:
                raise ValueError("margin 缺少 rzye 列")
            work["rzye"] = pd.to_numeric(work["rzye"], errors="coerce")
            work = work.dropna(subset=["rzye"])
            if "trade_date" in work.columns:
                by_date = work.groupby("trade_date", as_index=False)["rzye"].sum()
                by_date = by_date.sort_values("trade_date")
            else:
                by_date = work.sort_index()
            if len(by_date) < 2:
                raise ValueError("两融余额不足两个交易日")
            current = float(by_date.iloc[-1]["rzye"])
            previous = float(by_date.iloc[-2]["rzye"])
            if previous == 0:
                raise ValueError("上一交易日两融余额为 0")
            return FetchResult(
                source=self.source_name,
                data={"margin_balance_change_pct": (current / previous - 1) * 100},
            )
        except Exception as exc:
            return FetchResult(
                source=self.source_name,
                error=f"Tushare 两融余额接口不可用: {exc}",
            )

    def fetch_turnover_percentile(self) -> FetchResult:
        """Tushare V1 不提供与 AKShare 等价的全 A 换手率分位，显式缺失。"""
        return FetchResult(
            source=self.source_name,
            missing_fields=["turnover_percentile"],
            error="Tushare 情绪路径暂不提供 turnover_percentile（可用 AKShare 或后续扩展）",
        )

    def _latest_trade_date(self) -> Optional[str]:
        end = date.today()
        start = end - timedelta(days=10)
        try:
            cal = self._pro.trade_cal(
                exchange="SSE",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                is_open="1",
            )
            if cal is not None and not cal.empty and "cal_date" in cal.columns:
                opened = cal.sort_values("cal_date")
                return str(opened.iloc[-1]["cal_date"])
        except Exception as exc:
            logger.debug("trade_cal 失败，回退 weekday: %s", exc)
        value = end
        while value.weekday() >= 5:
            value -= timedelta(days=1)
        return value.strftime("%Y%m%d")
