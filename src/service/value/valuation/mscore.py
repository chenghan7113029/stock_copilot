"""Beneish M-Score 盈余操纵检测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseValuation, FieldRequirement, ValuationResult


@dataclass
class MScoreResult:
    m_score: float
    manipulation_risk: str
    is_manipulator: bool
    red_flags: list[str]
    component_scores: dict[str, float]


class BeneishMScore(BaseValuation):
    method_name = "Beneish M-Score"

    required_fields = [
        FieldRequirement("revenue", "Revenue (current year)", is_critical=True),
        FieldRequirement("total_assets", "Total Assets", is_critical=True),
        FieldRequirement("current_assets", "Current Assets", is_critical=False),
        FieldRequirement("accounts_receivable", "Accounts Receivable", is_critical=False),
        FieldRequirement("net_income", "Net Income", is_critical=True),
        FieldRequirement("fcf", "Free Cash Flow", is_critical=False),
    ]

    best_for = [
        "Earnings manipulation detection",
        "Fraud risk assessment",
        "Value investing due diligence",
        "Quality screening",
    ]
    not_for = [
        "Financial companies (different accounting)",
        "Companies with major acquisitions (distorted ratios)",
    ]

    SAFE_THRESHOLD = -2.22
    HIGH_RISK_THRESHOLD = -1.78

    def __init__(
        self,
        prior_revenue: Optional[float] = None,
        prior_gross_margin: Optional[float] = None,
        prior_total_assets: Optional[float] = None,
        prior_current_assets: Optional[float] = None,
        prior_ppe: Optional[float] = None,
        prior_depreciation: Optional[float] = None,
        prior_sga: Optional[float] = None,
        prior_total_debt: Optional[float] = None,
        prior_accounts_receivable: Optional[float] = None,
    ):
        self.prior_revenue = prior_revenue
        self.prior_gross_margin = prior_gross_margin
        self.prior_total_assets = prior_total_assets
        self.prior_current_assets = prior_current_assets
        self.prior_ppe = prior_ppe
        self.prior_depreciation = prior_depreciation
        self.prior_sga = prior_sga
        self.prior_total_debt = prior_total_debt
        self.prior_accounts_receivable = prior_accounts_receivable

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, warnings = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        prior_rev = self.prior_revenue if self.prior_revenue is not None else getattr(stock, "prior_revenue", None)
        prior_gm = (
            self.prior_gross_margin
            if self.prior_gross_margin is not None
            else getattr(stock, "prior_gross_margin", None)
        )
        prior_ta = (
            self.prior_total_assets
            if self.prior_total_assets is not None
            else getattr(stock, "prior_total_assets", None)
        )
        prior_ca = (
            self.prior_current_assets
            if self.prior_current_assets is not None
            else getattr(stock, "prior_current_assets", None)
        )
        prior_ppe = self.prior_ppe if self.prior_ppe is not None else getattr(stock, "prior_ppe", None)
        prior_dep = (
            self.prior_depreciation
            if self.prior_depreciation is not None
            else getattr(stock, "prior_depreciation", None)
        )
        extra: dict[str, Any] = getattr(stock, "extra", {}) or {}
        prior_sga = self.prior_sga if self.prior_sga is not None else extra.get("sga")
        prior_debt = (
            self.prior_total_debt
            if self.prior_total_debt is not None
            else getattr(stock, "prior_total_debt", None)
        )
        prior_ar = (
            self.prior_accounts_receivable
            if self.prior_accounts_receivable is not None
            else getattr(stock, "prior_accounts_receivable", None)
        )

        curr_rev = stock.revenue
        curr_ta = stock.total_assets
        curr_ca = stock.current_assets if stock.current_assets is not None else 0.0
        curr_ar = stock.accounts_receivable if stock.accounts_receivable is not None else 0.0
        curr_ppe = stock.net_fixed_assets if stock.net_fixed_assets is not None else 0.0
        curr_dep = stock.depreciation if stock.depreciation is not None else 0.0
        curr_debt = stock.total_liabilities if stock.total_liabilities is not None else 0.0
        curr_ni = stock.net_income
        curr_fcf = stock.fcf if stock.fcf is not None else 0.0

        indices: dict[str, float] = {}

        if prior_rev and prior_rev > 0 and prior_ar is not None and curr_ar > 0 and curr_rev > 0:
            indices["DSRI"] = (curr_ar / curr_rev) / (prior_ar / prior_rev)
        else:
            indices["DSRI"] = 1.0
            warnings.append("DSRI estimated as 1.0 (insufficient prior data)")

        operating_margin = stock.operating_margin if stock.operating_margin is not None else 0.0
        if prior_gm and prior_gm > 0 and operating_margin > 0:
            indices["GMI"] = prior_gm / operating_margin
        else:
            indices["GMI"] = 1.0
            warnings.append("GMI estimated as 1.0 (insufficient margin data)")

        if prior_ta and prior_ta > 0 and prior_ca is not None and prior_ppe is not None:
            prior_asset_quality = 1 - (prior_ca + prior_ppe) / prior_ta
            curr_aq = 1 - (curr_ca + curr_ppe) / curr_ta if curr_ta > 0 else 0
            if prior_asset_quality > 0 and curr_aq > 0:
                indices["AQI"] = curr_aq / prior_asset_quality
            else:
                indices["AQI"] = 1.0
        else:
            indices["AQI"] = 1.0
            warnings.append("AQI estimated as 1.0 (insufficient asset data)")

        if prior_rev and prior_rev > 0:
            indices["SGI"] = curr_rev / prior_rev
        else:
            indices["SGI"] = 1.0
            warnings.append("SGI estimated as 1.0 (no prior revenue)")

        if (
            prior_dep
            and prior_dep > 0
            and prior_ppe
            and prior_ppe > 0
            and curr_dep > 0
            and curr_ppe > 0
        ):
            prior_dep_rate = prior_dep / (prior_dep + prior_ppe)
            curr_dep_rate = curr_dep / (curr_dep + curr_ppe)
            if curr_dep_rate > 0:
                indices["DEPI"] = prior_dep_rate / curr_dep_rate
            else:
                indices["DEPI"] = 1.0
        else:
            indices["DEPI"] = 1.0
            warnings.append("DEPI estimated as 1.0 (insufficient depreciation data)")

        if prior_sga and prior_sga > 0 and prior_rev > 0 and curr_rev > 0:
            curr_sga = extra.get("sga", curr_rev * 0.15)
            indices["SGAI"] = (curr_sga / curr_rev) / (prior_sga / prior_rev)
        else:
            indices["SGAI"] = 1.0
            warnings.append("SGAI estimated as 1.0 (insufficient SG&A data)")

        if prior_debt and prior_debt > 0 and prior_ta and prior_ta > 0:
            prior_lev = prior_debt / prior_ta
            curr_lev = curr_debt / curr_ta if curr_ta > 0 else 0
            if prior_lev > 0:
                indices["LVGI"] = curr_lev / prior_lev
            else:
                indices["LVGI"] = 1.0
        else:
            indices["LVGI"] = 1.0
            warnings.append("LVGI estimated as 1.0 (insufficient leverage data)")

        if curr_fcf != 0 and curr_ta > 0:
            accruals = curr_ni - curr_fcf
            indices["TATA"] = accruals / curr_ta
        else:
            indices["TATA"] = 0.1
            warnings.append("TATA estimated at 0.1 (no FCF data)")

        m_score = (
            -4.84
            + 0.92 * indices.get("DSRI", 1.0)
            + 0.528 * indices.get("GMI", 1.0)
            + 0.404 * indices.get("AQI", 1.0)
            + 0.892 * indices.get("SGI", 1.0)
            + 0.115 * indices.get("DEPI", 1.0)
            - 0.172 * indices.get("SGAI", 1.0)
            + 4.679 * indices.get("TATA", 0.1)
            - 0.327 * indices.get("LVGI", 1.0)
        )

        if m_score < self.SAFE_THRESHOLD:
            manipulation_risk = "Low"
            is_manipulator = False
        elif m_score < self.HIGH_RISK_THRESHOLD:
            manipulation_risk = "Medium"
            is_manipulator = False
        else:
            manipulation_risk = "High"
            is_manipulator = True

        red_flags: list[str] = []
        if indices.get("DSRI", 1.0) > 1.2:
            red_flags.append(
                f"High DSRI ({indices['DSRI']:.2f}) - receivables growing faster than sales"
            )
        if indices.get("GMI", 1.0) > 1.1:
            red_flags.append(f"Deteriorating gross margins ({indices['GMI']:.2f})")
        if indices.get("AQI", 1.0) > 1.2:
            red_flags.append(f"Declining asset quality ({indices['AQI']:.2f})")
        if indices.get("SGI", 1.0) > 1.5:
            red_flags.append(f"Very high sales growth ({indices['SGI']:.2f})")
        if indices.get("TATA", 0) > 0.1:
            red_flags.append(f"High accruals to assets ({indices['TATA']:.3f})")

        ticker = getattr(stock, "ticker", "UNKNOWN")
        analysis = [
            f"=== Beneish M-Score Analysis: {ticker} ===",
            f"M-Score: {m_score:.2f}",
            f"Threshold: < {self.SAFE_THRESHOLD:.2f} (safe), > {self.HIGH_RISK_THRESHOLD:.2f} (high risk)",
            f"Risk Level: {manipulation_risk}",
            f"Is Manipulator: {'YES' if is_manipulator else 'NO'}",
            "",
            "Component Scores:",
        ]
        for name, value in indices.items():
            analysis.append(f"  {name}: {value:.3f}")

        if red_flags:
            analysis.extend(["", "Red Flags:"])
            for flag in red_flags:
                analysis.append(f"  ⚠️  {flag}")

        if is_manipulator:
            analysis.extend(["", "⚠️  WARNING: Company shows signs of potential earnings manipulation."])
            analysis.append("Recommendation: Deep due diligence required before investing.")
        else:
            analysis.extend(["", "✅ Company shows low risk of earnings manipulation."])

        if warnings:
            analysis.extend(["", "Notes:"] + [f"  - {w}" for w in warnings])

        confidence = "High" if len(warnings) == 0 else ("Medium" if len(warnings) <= 2 else "Low")
        applicability = "Applicable" if prior_rev else "Limited"

        return ValuationResult(
            method=self.method_name,
            fair_value=stock.current_price,
            current_price=stock.current_price,
            premium_discount=0,
            assessment=f"Manipulation Risk: {manipulation_risk} (M={m_score:.2f})",
            details={
                "output_type": "score",
                "m_score": round(m_score, 2),
                "manipulation_risk": manipulation_risk,
                "is_manipulator": is_manipulator,
                "red_flags": red_flags,
                "component_scores": {k: round(v, 3) for k, v in indices.items()},
                "threshold_safe": self.SAFE_THRESHOLD,
                "threshold_high_risk": self.HIGH_RISK_THRESHOLD,
            },
            components=indices,
            analysis=analysis,
            confidence=confidence,
            applicability=applicability,
        )


def calculate_m_score(
    stock,
    prior_revenue: Optional[float] = None,
    prior_gross_margin: Optional[float] = None,
    prior_total_assets: Optional[float] = None,
    prior_accounts_receivable: Optional[float] = None,
    prior_total_debt: Optional[float] = None,
) -> MScoreResult:
    scorer = BeneishMScore(
        prior_revenue=prior_revenue,
        prior_gross_margin=prior_gross_margin,
        prior_total_assets=prior_total_assets,
        prior_accounts_receivable=prior_accounts_receivable,
        prior_total_debt=prior_total_debt,
    )
    val_result = scorer.calculate(stock)

    return MScoreResult(
        m_score=round(val_result.details.get("m_score", 0), 2),
        manipulation_risk=val_result.details.get("manipulation_risk", "Unknown"),
        is_manipulator=val_result.details.get("is_manipulator", False),
        red_flags=val_result.details.get("red_flags", []),
        component_scores=val_result.details.get("component_scores", {}),
    )
