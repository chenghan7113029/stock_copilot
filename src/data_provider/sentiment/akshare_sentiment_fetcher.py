"""AKShare 市场情绪分量获取器。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from data_provider.base import FetchResult, retry_with_backoff


class AkshareSentimentFetcher:
    """将 AKShare 的市场级接口归一化为可部分降级的 FetchResult。"""

    source_name = "akshare"

    def __init__(self, akshare_client: Any | None = None) -> None:
        self._akshare_client = akshare_client

    def _get_ak(self) -> Any:
        if self._akshare_client is not None:
            return self._akshare_client
        import akshare as ak

        return ak

    def fetch_market_breadth(self) -> FetchResult:
        try:
            raw = retry_with_backoff(self._get_ak().stock_market_activity_legu, max_attempts=1)
            items = dict(zip(raw["item"].astype(str), raw["value"]))
            aliases = {
                "limit_up_count": ("涨停家数", "涨停数量"),
                "limit_down_count": ("跌停家数", "跌停数量"),
                "up_count": ("上涨家数",),
                "down_count": ("下跌家数",),
            }
            data: dict[str, int] = {}
            for field, candidates in aliases.items():
                value = next((items[name] for name in candidates if name in items), None)
                if value is None:
                    raise ValueError(f"市场活跃度缺少字段: {candidates[0]}")
                data[field] = int(float(str(value).replace(",", "")))
            return FetchResult(source=self.source_name, data=data)
        except Exception as exc:
            try:
                return self._fetch_breadth_from_limit_pools()
            except Exception as fallback_exc:
                return FetchResult(
                    source=self.source_name,
                    error=f"市场广度接口不可用: {exc}; 涨跌停池回退失败: {fallback_exc}",
                )

    def _fetch_breadth_from_limit_pools(self) -> FetchResult:
        """Legu 页面结构变化时，用东方财富涨停/跌停池保住核心分量。"""
        trade_date = self._latest_weekday().strftime("%Y%m%d")
        ak = self._get_ak()
        limit_up = retry_with_backoff(ak.stock_zt_pool_em, date=trade_date)
        limit_down = retry_with_backoff(ak.stock_zt_pool_dtgc_em, date=trade_date)
        return FetchResult(
            source=self.source_name,
            data={
                "limit_up_count": len(limit_up),
                "limit_down_count": len(limit_down),
                "up_count": None,
                "down_count": None,
            },
            missing_fields=["up_count", "down_count"],
        )

    @staticmethod
    def _latest_weekday() -> date:
        value = date.today()
        while value.weekday() >= 5:
            value -= timedelta(days=1)
        return value

    def fetch_margin_change(self) -> FetchResult:
        """从沪深两市两融余额的最近两个交易日计算环比变化。"""
        try:
            ak = self._get_ak()
            sh = retry_with_backoff(ak.macro_china_market_margin_sh)
            sz = retry_with_backoff(ak.macro_china_market_margin_sz)
            current, previous = self._combined_margin_balances(sh, sz)
            if previous == 0:
                raise ValueError("上一交易日两融余额为 0")
            return FetchResult(
                source=self.source_name,
                data={"margin_balance_change_pct": (current / previous - 1) * 100},
            )
        except Exception as exc:
            return FetchResult(source=self.source_name, error=f"两融余额接口不可用: {exc}")

    def fetch_turnover_percentile(self) -> FetchResult:
        """以当日全 A 股换手率横截面计算平均换手率所在的分位。"""
        try:
            raw = retry_with_backoff(self._get_ak().stock_zh_a_spot_em, max_attempts=1)
            turnover = pd.to_numeric(raw["换手率"], errors="coerce").dropna()
            if turnover.empty:
                raise ValueError("实时行情无有效换手率")
            market_mean = turnover.mean()
            percentile = float((turnover <= market_mean).mean() * 100)
            return FetchResult(source=self.source_name, data={"turnover_percentile": percentile})
        except Exception as exc:
            return FetchResult(source=self.source_name, error=f"换手率接口不可用: {exc}")

    @staticmethod
    def _combined_margin_balances(sh: pd.DataFrame, sz: pd.DataFrame) -> tuple[float, float]:
        def balances(frame: pd.DataFrame) -> list[float]:
            col = next((name for name in frame.columns if "融资余额" in str(name)), None)
            if col is None:
                raise ValueError("两融余额数据缺少融资余额列")
            values = pd.to_numeric(frame[col], errors="coerce").dropna().tolist()
            if len(values) < 2:
                raise ValueError("两融余额数据不足两个交易日")
            return [float(values[-1]), float(values[-2])]

        sh_values = balances(sh)
        sz_values = balances(sz)
        return sh_values[0] + sz_values[0], sh_values[1] + sz_values[1]
