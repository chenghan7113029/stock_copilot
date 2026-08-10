"""价值面分析 Facade：编排数据获取、路由、估值与聚合。"""

from __future__ import annotations

from typing import Any

from dao.prototype_override_repo import PrototypeOverrideRepo
from data_provider.provider import StockDataProvider
from service.value.aggregator import ValuationAggregator
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.router import (
    describe_honesty_gap,
    is_implemented_prototype,
    PrototypeRouter,
)
from service.value.valuation.assumptions import AssumptionProvider
from service.value.valuation.base import ValuationResult
from service.value.valuation.cycle_config import apply_cycle_inputs
from service.value.valuation.defense_config import apply_defense_order_inputs
from service.value.valuation.insurance_config import apply_insurance_inputs
from service.value.valuation.engine import ValuationEngine, default_engine

_GROWTH_MFG_SCENARIO_FAIL = (
    "检测到「成长+制造周期」特征，浅情景 DCF 假设不足或无法计算；"
    "通用方法得出的低估/高估不应用于买卖决策，当前结果参考性有限，不能作为买卖依据"
)

_CASHFLOW_AD_CYCLE_FAIL = (
    "检测到「现金流+广告周期」特征，缺周期位置或周期调整估值无法计算；"
    "轻资产高现金流在景气期易被静态外推过高、下行期过低，"
    "通用方法得出的低估/高估不应用于买卖决策，当前结果参考性有限，不能作为买卖依据"
)

_DEFENSE_ORDERS_FAIL = (
    "检测到「军工·订单驱动」特征，在手订单输入不足或无法计算；"
    "专用估值方法论（在手订单驱动 + 资产重估模型）暂缺或输入不足，"
    "通用方法得出的低估/高估不应用于买卖决策，当前结果参考性有限，不能作为买卖依据"
)

_INSURANCE_EV_FAIL = (
    "检测到「保险」特征，内含价值 EV/NBV 输入不足或无法计算；"
    "专用估值方法论（内含价值 EV/NBV 模型）暂缺或输入不足，"
    "通用方法得出的低估/高估不应用于买卖决策，当前结果参考性有限，不能作为买卖依据"
)


def _scenario_dcf_usable(result: ValuationResult | None) -> bool:
    if result is None:
        return False
    if result.error is not None or result.applicability == "Not Applicable":
        return False
    if result.fair_value <= 0:
        return False
    details = result.details or {}
    return details.get("output_type") == "scenario" and bool(details.get("scenarios"))


def _cyclical_method_usable(result: ValuationResult | None) -> bool:
    if result is None:
        return False
    if result.error is not None or result.applicability == "Not Applicable":
        return False
    if result.fair_value <= 0:
        return False
    details = result.details or {}
    return details.get("output_type") == "cyclical" and bool(details.get("cycle_position"))


def _defense_orders_usable(result: ValuationResult | None) -> bool:
    if result is None:
        return False
    if result.error is not None or result.applicability == "Not Applicable":
        return False
    if result.fair_value <= 0:
        return False
    details = result.details or {}
    return details.get("output_type") == "defense_orders"


def _insurance_ev_usable(result: ValuationResult | None) -> bool:
    if result is None:
        return False
    if result.error is not None or result.applicability == "Not Applicable":
        return False
    if result.fair_value <= 0:
        return False
    details = result.details or {}
    return details.get("output_type") == "insurance_ev"


def _pick_cyclical_primary(
    results: dict[str, ValuationResult],
) -> ValuationResult | None:
    """分众轻资产优先 FCF，其次 PE。"""
    for key in ("cyclical_fcf", "cyclical_pe"):
        result = results.get(key)
        if _cyclical_method_usable(result):
            return result
    return None


class ValueAnalyzer:
    """价值面分析单一入口。"""

    def __init__(
        self,
        provider: StockDataProvider,
        engine: ValuationEngine | None = None,
        router: PrototypeRouter | None = None,
        aggregator: ValuationAggregator | None = None,
        override_repo: PrototypeOverrideRepo | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._provider = provider
        self._engine = engine or default_engine()
        self._router = router or PrototypeRouter()
        self._aggregator = aggregator or ValuationAggregator()
        self._override_repo = override_repo
        self._config = config or {}

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
        return cls(
            provider,
            engine=engine,
            override_repo=override_repo,
            config=config,
        )

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

        honesty = describe_honesty_gap(stock.code, stock.industry)
        override_exempt = (
            override_record is not None and is_implemented_prototype(override_record.prototype)
        )
        apply_honesty = honesty is not None and not override_exempt

        if apply_honesty:
            assert honesty is not None
            warnings.insert(
                0,
                (
                    f"检测到「{honesty.label}」特征，{honesty.methodology_gap}，"
                    "当前使用通用方法，结果参考性有限，不能作为买卖依据"
                ),
            )
        elif prototype == "unknown":
            warnings.append("原型未识别，使用通用方法集，置信度低")
        elif prototype == "growth_tech":
            warnings.append(
                "原型为成长科技（growth_tech）：优先 PEG/GARP/Rule of 40，非 value_growth 静默替代"
            )

        if prototype == "cashflow_ad_cycle":
            for note in apply_cycle_inputs(stock, self._config):
                warnings.append(note)
        elif prototype == "defense_orders":
            for note in apply_defense_order_inputs(stock, self._config):
                warnings.append(note)
        elif prototype == "insurance":
            for note in apply_insurance_inputs(stock, self._config):
                warnings.append(note)

        results = self._engine.run_selected(method_keys, stock)
        agg = self._aggregator.aggregate(results, stock.current_price, prototype=prototype)
        warnings.extend(agg.warnings)

        assessment = agg.assessment
        confidence = agg.confidence
        methodology_applicable = True
        fair_value_range = agg.fair_value_range
        margin_of_safety = agg.margin_of_safety
        price_percentile = agg.price_percentile

        if apply_honesty:
            methodology_applicable = False
            assessment = "方法暂不适用"
            if confidence != "不可信":
                confidence = "Low"
        elif prototype == "growth_manufacturing":
            scenario = results.get("scenario_dcf")
            if _scenario_dcf_usable(scenario):
                assert scenario is not None
                methodology_applicable = True
                assessment = scenario.assessment
                if scenario.fair_value_range is not None:
                    fair_value_range = scenario.fair_value_range
            else:
                methodology_applicable = False
                assessment = "方法暂不适用"
                if confidence != "不可信":
                    confidence = "Low"
                warnings.insert(0, _GROWTH_MFG_SCENARIO_FAIL)
        elif prototype == "cashflow_ad_cycle":
            primary = _pick_cyclical_primary(results)
            if primary is not None:
                methodology_applicable = True
                assessment = primary.assessment
                if primary.fair_value_range is not None:
                    fair_value_range = primary.fair_value_range
            else:
                methodology_applicable = False
                assessment = "方法暂不适用"
                if confidence != "不可信":
                    confidence = "Low"
                warnings.insert(0, _CASHFLOW_AD_CYCLE_FAIL)
        elif prototype == "defense_orders":
            defense = results.get("defense_orders")
            if _defense_orders_usable(defense):
                assert defense is not None
                methodology_applicable = True
                assessment = defense.assessment
                if defense.fair_value_range is not None:
                    fair_value_range = defense.fair_value_range
            else:
                methodology_applicable = False
                assessment = "方法暂不适用"
                if confidence != "不可信":
                    confidence = "Low"
                warnings.insert(0, _DEFENSE_ORDERS_FAIL)
        elif prototype == "insurance":
            insurance = results.get("insurance_ev")
            if _insurance_ev_usable(insurance):
                assert insurance is not None
                methodology_applicable = True
                assessment = insurance.assessment
                if insurance.fair_value_range is not None:
                    fair_value_range = insurance.fair_value_range
            else:
                methodology_applicable = False
                assessment = "方法暂不适用"
                if confidence != "不可信":
                    confidence = "Low"
                warnings.insert(0, _INSURANCE_EV_FAIL)

        return ValueAnalysisResult(
            code=stock.code,
            name=stock.name,
            current_price=stock.current_price,
            prototype=prototype,
            method_keys_used=method_keys,
            fair_value_range=fair_value_range,
            margin_of_safety=margin_of_safety,
            price_percentile=price_percentile,
            assessment=assessment,
            confidence=confidence,
            method_results=results,
            warnings=warnings,
            data_timestamp=stock.data_timestamp,
            fundamental_report_date=stock.fundamental_report_date,
            value_score=None,
            value_trap_alert=agg.value_trap_alert,
            methodology_applicable=methodology_applicable,
        )
