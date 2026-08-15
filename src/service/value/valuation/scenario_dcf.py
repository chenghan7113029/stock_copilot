"""浅情景 DCF：悲观 / 基准 / 乐观三档。"""

from __future__ import annotations

from typing import Any

from .base import BaseValuation, FieldRequirement, ValuationRange, ValuationResult
from .dcf import DCF
from .scenario_config import resolve_scenario_params, scenario_label_zh


class _FcfOverride:
    """在不修改原 StockData 的前提下，向 DCF 注入情景用现金流底座。"""

    def __init__(self, base: Any, fcf: float) -> None:
        self._base = base
        self._fcf = fcf

    def __getattr__(self, name: str) -> Any:
        if name == "fcf":
            return self._fcf
        return getattr(self._base, name)


class ScenarioDCF(BaseValuation):
    """对同一股票用三档成长假设跑 DCF，主 fair_value 取基准情景。"""

    method_name = "Scenario DCF"

    required_fields = [
        FieldRequirement("shares_outstanding", "Shares Outstanding", is_critical=True, min_value=0.01),
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
    ]

    best_for = ["成长+制造周期（产能/销量波动大）"]
    not_for = ["Banks and financials"]

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, _warnings = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        cash_base, cash_source, cash_notes = _resolve_scenario_cash_base(stock, self._config)
        if cash_base is None or cash_base <= 0:
            return self._create_error_result(
                stock,
                "Scenario cash base unavailable (need positive FCF, OCF, or net_income proxy)",
                ["fcf"],
            )

        code = getattr(stock, "code", None) or getattr(getattr(stock, "_data", None), "code", None)
        scenarios = resolve_scenario_params(code, self._config)
        stock_for_dcf = _FcfOverride(stock, cash_base)

        scenario_rows: dict[str, dict[str, Any]] = {}
        for key, params in scenarios.items():
            dcf = DCF(
                growth_1_5=params.growth_rate_1_5,
                growth_6_10=params.growth_rate_6_10,
                terminal_growth=params.terminal_growth,
                discount_rate=params.discount_rate,
            )
            result = dcf.calculate(stock_for_dcf)
            if result.error or result.applicability == "Not Applicable" or result.fair_value <= 0:
                return self._create_error_result(
                    stock,
                    result.error or f"Scenario '{key}' DCF failed",
                    result.missing_fields or ["fcf"],
                )
            scenario_rows[key] = {
                "label": scenario_label_zh(key),
                "fair_value": result.fair_value,
                "growth_rate_1_5": params.growth_rate_1_5,
                "growth_rate_6_10": params.growth_rate_6_10,
                "terminal_growth": params.terminal_growth,
                "discount_rate": result.details.get("discount_rate"),
            }

        bear_fv = float(scenario_rows["bear"]["fair_value"])
        base_fv = float(scenario_rows["base"]["fair_value"])
        bull_fv = float(scenario_rows["bull"]["fair_value"])
        ordered = sorted([bear_fv, base_fv, bull_fv])
        low, mid, high = ordered[0], base_fv, ordered[2]

        price = float(stock.current_price)
        position_key, assessment = _price_position(price, bear_fv, base_fv, bull_fv)
        premium = ((base_fv - price) / price) * 100 if price else 0.0

        analysis = [
            "浅情景 DCF：悲观 / 基准 / 乐观三档成长假设",
            f"现金流底座: {cash_source} = {cash_base / 1e8:.2f} 亿元",
            *cash_notes,
            f"悲观公允价: {bear_fv:.2f}（1-5年增速 {scenario_rows['bear']['growth_rate_1_5']:.1f}%）",
            f"基准公允价: {base_fv:.2f}（1-5年增速 {scenario_rows['base']['growth_rate_1_5']:.1f}%）",
            f"乐观公允价: {bull_fv:.2f}（1-5年增速 {scenario_rows['bull']['growth_rate_1_5']:.1f}%）",
            f"现价落位: {assessment}",
            "主结论以三档相对位置表达，勿把基准情景当成唯一公允价真理",
        ]
        confidence = "Medium" if cash_source == "fcf" else "Low"

        return ValuationResult(
            method=self.method_name,
            fair_value=round(base_fv, 2),
            current_price=price,
            premium_discount=round(premium, 1),
            assessment=assessment,
            details={
                "output_type": "scenario",
                "scenarios": scenario_rows,
                "price_position": position_key,
                "cash_base": cash_base,
                "cash_source": cash_source,
                "cash_notes": cash_notes,
            },
            components={
                "bear": bear_fv,
                "base": base_fv,
                "bull": bull_fv,
            },
            analysis=analysis,
            confidence=confidence,
            fair_value_range=ValuationRange(low=round(low, 2), base=round(mid, 2), high=round(high, 2)),
            applicability="Applicable",
        )


def _resolve_scenario_cash_base(
    stock: Any, config: dict[str, Any] | None
) -> tuple[float | None, str | None, list[str]]:
    """制造扩张期 FCF 常为负：优先 FCF → OCF → 净利润×fcf_rate。"""
    notes: list[str] = []
    fcf = getattr(stock, "fcf", None)
    if fcf is not None and fcf > 0:
        return float(fcf), "fcf", notes

    if fcf is not None and fcf <= 0:
        notes.append(
            "报告期 FCF≤0（常见于产能扩张）；增长性资本开支由增速情景表达，避免与 FCF 双重惩罚"
        )

    ocf = getattr(stock, "operating_cash_flow", None)
    if ocf is None:
        # 兼容 adapter：有时只有 ocf 派生路径
        capex = getattr(stock, "capex", None)
        if fcf is not None and capex is not None and fcf <= 0:
            # 反推粗 OCF≈FCF+|capex| 仅作诊断，不直接采用负 FCF
            pass
    if ocf is not None and ocf > 0:
        notes.append("现金流底座改用经营现金流（OCF）")
        return float(ocf), "operating_cash_flow", notes

    net_income = getattr(stock, "net_income", None)
    if net_income is not None and net_income > 0:
        fcf_rate = 0.85
        if isinstance(config, dict):
            fcf_rate = float((config.get("value_analysis") or {}).get("fcf_rate", fcf_rate))
        proxy = float(net_income) * fcf_rate
        notes.append(f"现金流底座改用净利润×{fcf_rate:.2f}（低置信近似）")
        return proxy, "net_income_fcf_rate", notes

    return None, None, notes


def _price_position(
    price: float, bear: float, base: float, bull: float
) -> tuple[str, str]:
    """返回 (position_key, 中文评估)。假设 bear <= base <= bull；否则按数值排序解释。"""
    levels = sorted([(bear, "悲观"), (base, "基准"), (bull, "乐观")], key=lambda x: x[0])
    lo_v, lo_l = levels[0]
    mid_v, mid_l = levels[1]
    hi_v, hi_l = levels[2]

    if price < lo_v:
        return "below_bear", f"现价低于{lo_l}情景（相对三档偏便宜）"
    if price < mid_v:
        return "between_bear_base", f"现价介于{lo_l}与{mid_l}情景之间"
    if price < hi_v:
        return "between_base_bull", f"现价介于{mid_l}与{hi_l}情景之间"
    return "above_bull", f"现价高于{hi_l}情景（相对三档偏贵）"
