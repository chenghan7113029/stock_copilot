"""回测专用数据适配子域（design §6.2）。

四个适配器各自守一类数据缺口；本模块把它们组合成 service 侧注入的 `loader`：

- `load_price_rows(codes, start, end, adjust)` → 后复权价行（含撮合字段，若已接通）
- `load_financial_rows(codes, as_of)` → 财务行（已按公告日对齐）
- `load_members(as_of, universe_spec)` / `load_flags(codes, as_of)` → 历史成分 / 退市 ST
- `load_universe_codes(as_of)` → 校准题所需的全 A 名单（缺口即报错）

默认全部未接通 → 任何取数都抛 `BacktestDataGapError`，这是**有意的**：本机三源均为
前复权、无成交额、无表级公告日（proposal `## Impact` / knowledge-delta §13）。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from common.exceptions import BacktestDataGapError
from data_provider.backtest.adjust_price import BacktestPriceAdapter
from data_provider.backtest.financial_timing import FinancialTimingAdapter
from data_provider.backtest.market_rules import MarketRulesAdapter, merge_market_fields
from data_provider.backtest.universe import UniverseAdapter

__all__ = [
    "BacktestDataLoader",
    "BacktestPriceAdapter",
    "FinancialTimingAdapter",
    "MarketRulesAdapter",
    "UniverseAdapter",
]


class BacktestDataLoader:
    def __init__(
        self,
        *,
        prices: BacktestPriceAdapter | None = None,
        market: MarketRulesAdapter | None = None,
        universe: UniverseAdapter | None = None,
        financials: FinancialTimingAdapter | None = None,
    ) -> None:
        self.prices = prices or BacktestPriceAdapter()
        self.market = market or MarketRulesAdapter()
        self.universe = universe or UniverseAdapter()
        self.financials = financials or FinancialTimingAdapter()

    def load_price_rows(
        self, codes: Sequence[str], start: str, end: str, adjust: Any
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        price_rows = self.prices.load_rows(codes, start, end, adjust)
        if self.market.has_source:
            market_rows = self.market.load_rows(codes, start, end)
            return merge_market_fields(price_rows, market_rows)
        return price_rows

    def load_financial_rows(
        self, codes: Sequence[str], as_of: str
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        return self.financials.load_rows(codes, as_of)

    def load_members(self, as_of: str, universe_spec: Mapping[str, Any]) -> tuple[str, ...]:
        return self.universe.load_members(as_of, universe_spec)

    def load_flags(self, codes: Sequence[str], as_of: str) -> dict[str, dict[str, Any]]:
        return self.universe.load_flags(codes, as_of)

    def load_universe_codes(self, as_of: str) -> tuple[str, ...]:
        if not self.universe.has_source:
            raise BacktestDataGapError("全 A 名单缺失：校准题无法取全域样本（R18/R12）")
        return self.universe.load_members(as_of, {"kind": "all_a"})
