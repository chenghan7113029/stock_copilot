"""估值假设参数配置与推导。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.models.stock_data import StockData

_DEFAULT_BETA_BY_PROTO: dict[str, float] = {
    "value_growth": 0.6,
    "high_dividend": 0.5,
    "bank": 0.9,
    "growth_manufacturing": 0.8,
    "cashflow_ad_cycle": 0.85,
    "defense_orders": 1.0,
}
_DEFAULT_GROWTH_RATE_FLOOR_BY_PROTO: dict[str, float] = {
    "value_growth": 8.0,
    "high_dividend": 3.0,
    "bank": 5.0,
    "growth_manufacturing": 6.0,
    "cashflow_ad_cycle": 4.0,
    "defense_orders": 3.0,
}


@dataclass
class AssumptionDefaults:
    china_10y_yield: float = 1.80
    equity_risk_premium: float = 6.0
    aaa_corporate_yield: float = 5.30
    discount_rate: float = 10.0
    tax_rate: float = 25.0
    dividend_growth_rate: float = 3.0
    growth_rate_1_5: float = 5.0
    growth_rate_6_10: float = 3.0
    terminal_growth: float = 2.0
    ev_ebitda_multiple: float = 12.0
    beta_by_proto: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_BETA_BY_PROTO))
    growth_rate_floor_by_proto: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_GROWTH_RATE_FLOOR_BY_PROTO)
    )


class AssumptionProvider:
    """集中提供估值宏观经济假设，优先级：StockData > 构造覆盖 > config > 默认值。"""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        overrides: AssumptionDefaults | None = None,
    ):
        self._config = config or {}
        self._defaults = overrides or AssumptionDefaults()
        value_cfg = self._config.get("value_analysis", {})
        self.china_10y_yield = float(
            value_cfg.get("china_10y_yield", self._defaults.china_10y_yield)
        )
        self.equity_risk_premium = float(
            value_cfg.get("equity_risk_premium", self._defaults.equity_risk_premium)
        )
        self.aaa_corporate_yield = float(
            value_cfg.get("aaa_corporate_yield", self._defaults.aaa_corporate_yield)
        )
        self.discount_rate = float(
            value_cfg.get("discount_rate", self._defaults.discount_rate)
        )
        self.tax_rate = float(value_cfg.get("tax_rate", self._defaults.tax_rate))
        self.dividend_growth_rate = float(
            value_cfg.get("dividend_growth_rate", self._defaults.dividend_growth_rate)
        )
        self.growth_rate_1_5 = float(
            value_cfg.get("growth_rate_1_5", self._defaults.growth_rate_1_5)
        )
        self.growth_rate_6_10 = float(
            value_cfg.get("growth_rate_6_10", self._defaults.growth_rate_6_10)
        )
        self.terminal_growth = float(
            value_cfg.get("terminal_growth", self._defaults.terminal_growth)
        )
        self.ev_ebitda_multiple = float(
            value_cfg.get("ev_ebitda_multiple", self._defaults.ev_ebitda_multiple)
        )
        self.beta_by_proto = {
            **self._defaults.beta_by_proto,
            **(value_cfg.get("beta_by_proto") or {}),
        }
        self.growth_rate_floor_by_proto = {
            **self._defaults.growth_rate_floor_by_proto,
            **(value_cfg.get("growth_rate_floor_by_proto") or {}),
        }

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def get_discount_rate(self, stock: StockData) -> float:
        proto = getattr(stock, "proto", "") or ""
        beta = self.beta_by_proto.get(proto)
        if beta is not None:
            return self.china_10y_yield + beta * self.equity_risk_premium
        return self.discount_rate

    def get_growth_rate_1_5(self, stock: StockData) -> float:
        proto = getattr(stock, "proto", "") or ""
        floor = self.growth_rate_floor_by_proto.get(proto, 0.0)
        if stock.growth_rate is not None:
            return max(stock.growth_rate, floor)
        return max(self.growth_rate_1_5, floor)

    def get_growth_rate_6_10(self, stock: StockData) -> float:
        return self.growth_rate_6_10

    def get_terminal_growth(self, stock: StockData) -> float:
        return self.terminal_growth

    def get_ev_ebitda_multiple(self, stock: StockData) -> float:
        return self.ev_ebitda_multiple

    def get_tax_rate(self, stock: StockData) -> float:
        if stock.tax_rate is not None:
            return stock.tax_rate
        return self.tax_rate

    def get_dividend_growth_rate(self, stock: StockData) -> float | None:
        if stock.dividend_growth_rate is not None:
            return stock.dividend_growth_rate
        return self.dividend_growth_rate

    def get_risk_free_rate(self, stock: StockData, currency: str = "CNY") -> float:
        if currency == "USD":
            return 4.30
        return self.china_10y_yield
