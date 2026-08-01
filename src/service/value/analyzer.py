"""价值面分析 Facade：编排数据获取、路由、估值与聚合。"""

from __future__ import annotations

from typing import Any

from dao.prototype_override_repo import PrototypeOverrideRepo
from data_provider.provider import StockDataProvider
from service.value.aggregator import ValuationAggregator
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.router import PrototypeRouter, describe_unimplemented_industry
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.engine import ValuationEngine, default_engine


class ValueAnalyzer:
    """价值面分析单一入口。"""

    def __init__(
        self,
        provider: StockDataProvider,
        engine: ValuationEngine | None = None,
        router: PrototypeRouter | None = None,
        aggregator: ValuationAggregator | None = None,
        override_repo: PrototypeOverrideRepo | None = None,
    ) -> None:
        self._provider = provider
        self._engine = engine or default_engine()
        self._router = router or PrototypeRouter()
        self._aggregator = aggregator or ValuationAggregator()
        self._override_repo = override_repo

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        repo: Any = None,
        override_repo: PrototypeOverrideRepo | None = None,
    ) -> "ValueAnalyzer":
        provider = StockDataProvider.from_config(config, repo=repo)
        assumptions = AssumptionProvider(config)
        engine = default_engine(assumptions=assumptions)
        return cls(provider, engine=engine, override_repo=override_repo)

    def analyze(self, code: str) -> ValueAnalysisResult:
        stock = self._provider.get_stock_data(code)
        return self._analyze_stock(stock)

    def analyze_offline(self, code: str) -> ValueAnalysisResult | None:
        stock = self._provider.get_stock_data_offline(code)
        if stock is None:
            return None
        return self._analyze_stock(stock)

    def _analyze_stock(self, stock) -> ValueAnalysisResult:
        warnings: list[str] = []
        override_record = (
            self._override_repo.get_by_code(stock.code)
            if self._override_repo is not None
            else None
        )
        if override_record is not None:
            prototype, method_keys = self._router.route(stock, override=override_record.prototype)
            warnings.append(
                f"原型已人工覆盖为 {override_record.prototype}（原因：{override_record.reason}）"
            )
        else:
            prototype, method_keys = self._router.route(stock)

        if prototype == "unknown":
            industry_detail = describe_unimplemented_industry(stock.industry)
            if industry_detail is not None:
                label, gap_note = industry_detail
                warnings.append(f"检测到{label}行业，{gap_note}，当前使用通用方法，结果参考性有限")
            else:
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
            value_trap_alert=agg.value_trap_alert,
        )
