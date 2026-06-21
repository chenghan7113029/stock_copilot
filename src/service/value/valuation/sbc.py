"""SBCAnalysis — 股权激励稀释分析。"""

from __future__ import annotations

from .base import BaseValuation, FieldRequirement, ValuationResult


def _dilution_rating(sbc_to_net_income: float) -> str:
    """SBC/净利润比例 → 稀释性评级。"""
    if sbc_to_net_income < 0.05:
        return "Negligible"
    if sbc_to_net_income < 0.15:
        return "Light"
    if sbc_to_net_income < 0.30:
        return "Moderate"
    if sbc_to_net_income <= 0.50:
        return "Severe"
    return "Extreme"


class SBCAnalysis(BaseValuation):
    """股权激励（SBC）稀释分析。

    计算 SBC 占净利润/营收比例、年化稀释率、调整后 EPS，给出稀释性评级。
    output_type = "score"；fair_value = current_price（不参与区间聚合）。
    A 股 sbc = None 时返回 applicability = "Not Applicable"。
    """

    method_name = "SBC Analysis"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
    ]

    best_for = [
        "Tech/growth companies with stock option plans",
        "Screening for hidden dilution costs",
    ]
    not_for = ["A-share companies without SBC disclosure (returns Not Applicable)"]

    def calculate(self, stock) -> ValuationResult:
        current_price = getattr(stock, "current_price", None) or 0.0
        sbc = getattr(stock, "sbc", None)

        # sbc = None → A 股未披露，Not Applicable
        if sbc is None:
            return ValuationResult(
                method=self.method_name,
                fair_value=current_price,
                current_price=current_price,
                premium_discount=0,
                assessment="Not Applicable — SBC data unavailable",
                details={"output_type": "score", "dilution_rating": "Not Applicable"},
                confidence="N/A",
                fair_value_range=None,
                applicability="Not Applicable",
            )

        net_income = getattr(stock, "net_income", None)
        revenue = getattr(stock, "revenue", None)
        shares_outstanding = getattr(stock, "shares_outstanding", None)
        prior_shares_outstanding = getattr(stock, "prior_shares_outstanding", None)
        eps = getattr(stock, "eps", None)

        warnings: list[str] = []

        # net_income 必填（用于评级计算）
        if net_income is None:
            return self._create_error_result(stock, "Missing required data: net_income", ["net_income"])

        # SBC/净利润
        sbc_to_net_income = sbc / net_income if net_income != 0 else 0.0
        rating = _dilution_rating(abs(sbc_to_net_income))

        # SBC/营收
        sbc_to_revenue = (sbc / revenue) if revenue is not None and revenue > 0 else None

        # 调整后 EPS
        adjusted_eps: float | None = None
        if shares_outstanding is not None and shares_outstanding > 0:
            adjusted_net_income = net_income - sbc
            adjusted_eps = adjusted_net_income / shares_outstanding
        elif eps is not None:
            adjusted_eps = eps - (sbc / (net_income / eps)) if eps != 0 else None

        # 年化稀释率
        annual_dilution_rate: float | None = None
        if prior_shares_outstanding is not None and prior_shares_outstanding > 0:
            if shares_outstanding is not None:
                annual_dilution_rate = (
                    (shares_outstanding - prior_shares_outstanding) / prior_shares_outstanding
                )
        else:
            warnings.append("prior_shares_outstanding unavailable — annual dilution rate not calculated")

        analysis_parts = [
            f"SBC / Net Income: {sbc_to_net_income:.1%}",
            f"Dilution Rating: {rating}",
        ]
        if sbc_to_revenue is not None:
            analysis_parts.append(f"SBC / Revenue: {sbc_to_revenue:.1%}")
        if adjusted_eps is not None:
            analysis_parts.append(f"Adjusted EPS: {adjusted_eps:.4f}")
        if annual_dilution_rate is not None:
            analysis_parts.append(f"Annual Dilution Rate: {annual_dilution_rate:.1%}")
        if warnings:
            analysis_parts.extend(["", "Warnings:"] + [f"  - {w}" for w in warnings])

        assessment_map = {
            "Negligible": "Negligible SBC dilution",
            "Light": "Light SBC dilution",
            "Moderate": "Moderate SBC dilution — monitor",
            "Severe": "Severe SBC dilution — significant risk",
            "Extreme": "Extreme SBC dilution — major red flag",
        }

        details: dict = {
            "output_type": "score",
            "sbc": sbc,
            "sbc_to_net_income": round(sbc_to_net_income, 4),
            "dilution_rating": rating,
        }
        if sbc_to_revenue is not None:
            details["sbc_to_revenue"] = round(sbc_to_revenue, 4)
        if adjusted_eps is not None:
            details["adjusted_eps"] = round(adjusted_eps, 4)
        if annual_dilution_rate is not None:
            details["annual_dilution_rate"] = round(annual_dilution_rate, 4)

        confidence = "High" if len(warnings) == 0 else "Medium"

        return ValuationResult(
            method=self.method_name,
            fair_value=current_price,
            current_price=current_price,
            premium_discount=0,
            assessment=assessment_map.get(rating, rating),
            details=details,
            analysis=analysis_parts,
            confidence=confidence,
            fair_value_range=None,
            applicability="Applicable",
            missing_fields=[],
        )
