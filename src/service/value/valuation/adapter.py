"""StockData → 估值方法 duck-type 输入适配。"""

from __future__ import annotations

from typing import Any

from common.models.stock_data import StockData

from .assumptions import AssumptionProvider


class StockDataAdapter:
    """包装 StockData，补齐 valueinvest Stock 风格的计算属性。"""

    def __init__(
        self,
        data: StockData,
        assumptions: AssumptionProvider | None = None,
    ):
        self._data = data
        self._assumptions = assumptions or AssumptionProvider()

    @property
    def data(self) -> StockData:
        return self._data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._data, name)

    @property
    def cost_of_capital(self) -> float:
        return self._assumptions.get_discount_rate(self._data)

    @property
    def discount_rate(self) -> float:
        return self.cost_of_capital

    @property
    def aaa_corporate_yield(self) -> float:
        return self._assumptions.aaa_corporate_yield

    @property
    def china_10y_yield(self) -> float:
        return self._assumptions.china_10y_yield

    @property
    def currency(self) -> str:
        return "CNY"

    @property
    def market_cap(self) -> float | None:
        if self._data.market_cap is not None:
            return self._data.market_cap
        if (
            self._data.current_price is not None
            and self._data.shares_outstanding is not None
        ):
            return self._data.current_price * self._data.shares_outstanding
        return None

    @property
    def enterprise_value(self) -> float | None:
        mc = self.market_cap
        if mc is None:
            return None
        net_debt = self._data.net_debt if self._data.net_debt is not None else 0.0
        return mc + net_debt

    @property
    def pe_ratio(self) -> float:
        if self._data.eps and self._data.eps > 0 and self._data.current_price:
            return self._data.current_price / self._data.eps
        return 0.0

    @property
    def pb_ratio(self) -> float:
        if self._data.bvps and self._data.bvps > 0 and self._data.current_price:
            return self._data.current_price / self._data.bvps
        return 0.0

    @property
    def payout_ratio(self) -> float:
        if self._data.dividend_payout_ratio is not None:
            return self._data.dividend_payout_ratio
        if (
            self._data.dividend_per_share is not None
            and self._data.eps is not None
            and self._data.eps > 0
        ):
            return self._data.dividend_per_share / self._data.eps * 100
        return 0.0

    @property
    def dividend_growth_rate(self) -> float:
        val = self._assumptions.get_dividend_growth_rate(self._data)
        return val if val is not None else self._assumptions.dividend_growth_rate

    @property
    def tax_rate(self) -> float | None:
        if self._data.tax_rate is not None:
            return self._data.tax_rate
        return self._assumptions.get_tax_rate(self._data)

    @property
    def extra(self) -> dict[str, Any]:
        return {}
