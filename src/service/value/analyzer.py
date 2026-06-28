"""价值面分析 Facade：编排数据获取、路由、估值与聚合。"""

from __future__ import annotations

from typing import Any

from data_provider.provider import StockDataProvider
from service.value.aggregator import ValuationAggregator
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.router import PrototypeRouter
from service.value.valuation.engine import ValuationEngine, default_engine


class ValueAnalyzer:
    """价值面分析单一入口。"""

    def __init__(
        self,
        provider: StockDataProvider,
        engine: ValuationEngine | None = None,
        router: PrototypeRouter | None = None,
        aggregator: ValuationAggregator | None = None,
    ) -> None:
        self._provider = provider
        self._engine = engine or default_engine()
        self._router = router or PrototypeRouter()
        self._aggregator = aggregator or ValuationAggregator()

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: Any = None) -> "ValueAnalyzer":
        provider = StockDataProvider.from_config(config, repo=repo)
        return cls(provider)

    def analyze(self, code: str) -> ValueAnalysisResult:
        stock = self._provider.get_stock_data(code)
        return self._analyze_stock(stock)

    def analyze_offline(self, code: str) -> ValueAnalysisResult | None:
        stock = self._provider.get_stock_data_offline(code)
        if stock is None:
            return None
        return self._analyze_stock(stock)

    def _analyze_stock(self, stock) -> ValueAnalysisResult:
        prototype, method_keys = self._router.route(stock)

        warnings: list[str] = []
        if prototype == "unknown":
            warnings.append("原型未识别，使用通用方法集，置信度低")

        results = self._engine.run_selected(method_keys, stock)
        agg = self._aggregator.aggregate(results, stock.current_price)
        warnings.extend(agg.warnings)

        return ValueAnalysisResult(
            code=stock.code,
            name=stock.name,
            current_price=stock.current_price,
            prototype=prototype,
            method_keys_used=method_keys,
            fair_value_range=agg.fair_value_range,
            margin_of_safety=agg.margin_of_safety,
            price_percentile=agg.price_percentile,
            assessment=agg.assessment,
            confidence=agg.confidence,
            method_results=results,
            warnings=warnings,
            data_timestamp=stock.data_timestamp,
            fundamental_report_date=stock.fundamental_report_date,
            value_score=None,
        )
