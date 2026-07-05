"""股票原型路由：分类 + method_keys 选择。"""

from __future__ import annotations

from common.models.stock_data import StockData

_CODE_OVERRIDE: dict[str, str] = {
    "601398": "bank",
    "601328": "bank",
    "601939": "bank",
    "600036": "bank",
    "600900": "high_dividend",
    "600519": "value_growth",
}

_PROTOTYPE_METHODS: dict[str, list[str]] = {
    "bank": [
        "pb",
        "residual_income",
        "ddm",
        "two_stage_ddm",
        "graham_number",
        "altman_z",
        "pb_relative",
        "value_trap",
    ],
    "high_dividend": [
        "ddm",
        "two_stage_ddm",
        "epv",
        "owner_earnings",
        "graham_number",
        "altman_z",
        "value_trap",
    ],
    "value_growth": [
        "dcf",
        "epv",
        "owner_earnings",
        "graham_formula",
        "ev_ebitda",
        "pe_relative",
        "piotroski_f",
        "beneish_m",
        "value_trap",
    ],
    "unknown": [
        "graham_number",
        "graham_formula",
        "epv",
        "altman_z",
        "value_trap",
    ],
}


class PrototypeRouter:
    """V1 原型路由：硬编码覆盖 + 财务特征启发。"""

    def route(self, stock: StockData) -> tuple[str, list[str]]:
        prototype = self._classify(stock)
        stock.proto = prototype
        return prototype, list(_PROTOTYPE_METHODS[prototype])

    def _classify(self, stock: StockData) -> str:
        if stock.code in _CODE_OVERRIDE:
            return _CODE_OVERRIDE[stock.code]

        if stock.industry and "银行" in stock.industry:
            return "bank"

        if (
            stock.total_assets is None
            and stock.dividend_yield is None
            and stock.growth_rate is None
        ):
            return "unknown"

        if stock.total_assets and stock.total_liabilities:
            leverage = stock.total_liabilities / stock.total_assets
            if leverage > 0.85:
                return "bank"

        if stock.dividend_yield is not None and stock.dividend_yield > 4.0:
            if stock.growth_rate is not None and stock.growth_rate < 10:
                return "high_dividend"

        return "value_growth"
