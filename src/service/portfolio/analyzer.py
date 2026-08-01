"""严格离线的持仓集中度与行业暴露度粗估。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from service.portfolio.models.portfolio_result import PortfolioAnalysisResult, PositionSummary

PRICE_STALE_DAYS = 7
INDUSTRY_LIMITATION_WARNING = "⚠ 行业分类基于原始文本粗匹配，未做标准化归一，可能低估实际同行业暴露"


class PortfolioAnalyzer:
    """基于 TradeRecord 派生持仓，且仅读取本地价值快照。"""

    def __init__(self, trade_record_repo: Any, stock_snapshot_repo: Any) -> None:
        self._trade_record_repo = trade_record_repo
        self._stock_snapshot_repo = stock_snapshot_repo
        self._last_result: PortfolioAnalysisResult | None = None

    def analyze_offline(self) -> PortfolioAnalysisResult:
        """计算当前持仓市值、集中度与行业分组，不发起网络请求。"""
        positions = self._trade_record_repo.find_open_positions()
        quantities: dict[str, int] = defaultdict(int)
        for position in positions:
            quantities[position.code] += position.quantity
        result = self._build_result(dict(quantities))
        self._last_result = result
        return result

    def industry_exposure(self, code: str) -> float | None:
        """返回目标股票所属行业在当前组合中的市值占比。"""
        result = self._last_result or self.analyze_offline()
        target_industry = self._industry_for(code)
        if not target_industry:
            warning = "⚠ 无法获取行业信息，无法估算行业暴露度"
            if warning not in result.warnings:
                result.warnings.append(warning)
            return None
        return result.industry_exposure.get(target_industry, 0.0)

    def simulate_add(self, code: str, quantity: int) -> PortfolioAnalysisResult:
        """纯内存模拟买入，不写入任何 TradeRecord。"""
        if quantity <= 0:
            raise ValueError("模拟加仓数量必须大于 0")

        positions = self._trade_record_repo.find_open_positions()
        quantities: dict[str, int] = defaultdict(int)
        for position in positions:
            quantities[position.code] += position.quantity
        quantities[code] += quantity

        result = self._build_result(dict(quantities))
        result.warnings.append("以下为模拟计算，不代表任何实际交易操作")
        self._last_result = result
        return result

    def _build_result(self, quantities: dict[str, int]) -> PortfolioAnalysisResult:
        warnings = [INDUSTRY_LIMITATION_WARNING]
        if not quantities:
            return PortfolioAnalysisResult(
                total_value=0.0,
                warnings=["⚠ 当前无持仓记录", *warnings],
            )

        raw_positions: list[tuple[str, int, float, str | None, datetime | None]] = []
        for code, quantity in quantities.items():
            snapshot = self._latest_snapshot(code)
            price = getattr(snapshot, "current_price", None) if snapshot else None
            if price is None or price <= 0:
                warnings.append(f"⚠ {code} 无可用本地价格，未计入组合市值；请先 sync")
                continue
            price_as_of = self._price_as_of(snapshot)
            if self._is_stale(price_as_of):
                warnings.append(f"⚠ {code} 价格数据已过期，建议先 sync")
            raw_positions.append(
                (code, quantity, float(price) * quantity, self._industry_for(code), price_as_of)
            )

        total_value = sum(position[2] for position in raw_positions)
        summaries = [
            PositionSummary(
                code=code,
                quantity=quantity,
                market_value=market_value,
                weight=market_value / total_value if total_value else None,
                industry=industry,
                price_as_of=price_as_of,
            )
            for code, quantity, market_value, industry, price_as_of in raw_positions
        ]
        summaries.sort(key=lambda position: position.market_value, reverse=True)

        weights = {
            position.code: position.weight
            for position in summaries
            if position.weight is not None
        }
        industry_values: dict[str, float] = defaultdict(float)
        for position in summaries:
            if position.industry:
                industry_values[position.industry] += position.market_value
        exposures = {
            industry: value / total_value
            for industry, value in industry_values.items()
        } if total_value else {}

        top_n = {
            n: sum(position.market_value for position in summaries[:n]) / total_value
            for n in (1, 3, 5)
            if summaries and total_value
        }
        return PortfolioAnalysisResult(
            total_value=total_value,
            positions=summaries,
            single_stock_weight=weights,
            top_n_concentration=top_n,
            industry_exposure=exposures,
            warnings=warnings,
        )

    def _latest_snapshot(self, code: str) -> Any | None:
        snapshots = self._stock_snapshot_repo.find_by_code(code)
        priced = [snapshot for snapshot in snapshots if getattr(snapshot, "current_price", None) is not None]
        return max(priced, key=self._snapshot_datetime) if priced else None

    def _industry_for(self, code: str) -> str | None:
        snapshots = self._stock_snapshot_repo.find_by_code(code)
        categorized = [snapshot for snapshot in snapshots if getattr(snapshot, "industry", None)]
        if not categorized:
            return None
        return max(categorized, key=self._snapshot_datetime).industry

    @staticmethod
    def _snapshot_datetime(snapshot: Any) -> datetime:
        return getattr(snapshot, "fetched_at", None) or datetime.min

    @staticmethod
    def _price_as_of(snapshot: Any) -> datetime | None:
        return getattr(snapshot, "data_timestamp", None) or getattr(snapshot, "fetched_at", None)

    @staticmethod
    def _is_stale(price_as_of: datetime | None) -> bool:
        if price_as_of is None:
            return True
        if price_as_of.tzinfo is not None:
            price_as_of = price_as_of.replace(tzinfo=None)
        return price_as_of < datetime.now() - timedelta(days=PRICE_STALE_DAYS)
