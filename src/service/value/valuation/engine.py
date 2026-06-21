"""估值引擎：注册表 + 批量运行。"""

from __future__ import annotations

from common.models.stock_data import StockData

from .adapter import StockDataAdapter
from .assumptions import AssumptionProvider
from .bank import PBValuation, ResidualIncome
from .base import BaseValuation, ValuationResult
from .dcf import DCF, ReverseDCF
from .ddm import DDM, TwoStageDDM
from .epv import EPV
from .graham import NCAV, GrahamFormula, GrahamNumber
from .growth import EVEBITDA, GARP, PEG, RuleOf40
from .magic_formula import MagicFormula
from .mscore import BeneishMScore
from .quality import AltmanZScore, OwnerEarnings, PiotroskiFScore
from .relative import PBRelativeValuation, PERelativeValuation
from .sbc import SBCAnalysis
from .value_trap import ValueTrapDetector


class ValuationEngine:
    def __init__(self, assumptions: AssumptionProvider | None = None):
        self._methods: dict[str, BaseValuation] = {}
        self._assumptions = assumptions or AssumptionProvider()

    def register(self, key: str, method: BaseValuation) -> None:
        self._methods[key] = method

    def _adapt(self, stock_data: StockData) -> StockDataAdapter:
        return StockDataAdapter(stock_data, self._assumptions)

    def run_single(self, key: str, stock_data: StockData) -> ValuationResult:
        method = self._methods[key]
        adapter = self._adapt(stock_data)
        try:
            return method.calculate(adapter)
        except Exception as exc:
            return ValuationResult(
                method=getattr(method, "method_name", key),
                fair_value=0,
                current_price=stock_data.current_price or 0,
                premium_discount=0,
                assessment="N/A",
                error=str(exc),
                confidence="N/A",
                applicability="Not Applicable",
            )

    def run_all(self, stock_data: StockData) -> dict[str, ValuationResult]:
        results: dict[str, ValuationResult] = {}
        for key in self._methods:
            results[key] = self.run_single(key, stock_data)
        return results


def default_engine(assumptions: AssumptionProvider | None = None) -> ValuationEngine:
    engine = ValuationEngine(assumptions=assumptions)
    engine.register("graham_number", GrahamNumber())
    engine.register("graham_formula", GrahamFormula())
    engine.register("ncav", NCAV())
    engine.register("pb", PBValuation())
    engine.register("residual_income", ResidualIncome())
    engine.register("ddm", DDM())
    engine.register("two_stage_ddm", TwoStageDDM())
    engine.register("epv", EPV())
    engine.register("owner_earnings", OwnerEarnings())
    engine.register("dcf", DCF())
    engine.register("reverse_dcf", ReverseDCF())
    engine.register("altman_z", AltmanZScore())
    engine.register("piotroski_f", PiotroskiFScore())
    engine.register("beneish_m", BeneishMScore())
    engine.register("peg", PEG())
    engine.register("garp", GARP())
    engine.register("rule_of_40", RuleOf40())
    engine.register("ev_ebitda", EVEBITDA())
    engine.register("magic_formula", MagicFormula())
    engine.register("pe_relative", PERelativeValuation())
    engine.register("pb_relative", PBRelativeValuation())
    engine.register("value_trap", ValueTrapDetector())
    engine.register("sbc", SBCAnalysis())
    return engine
