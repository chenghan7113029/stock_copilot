"""ValueTrapDetector — 五维度价值陷阱风险检测。"""

from __future__ import annotations

from .base import BaseValuation, ValuationResult
from .quality import AltmanZScore  # noqa: E402

_ALTMAN = AltmanZScore()

_RISK_WEIGHT = {
    "Low": 0,
    "Medium": 1,
    "High": 2,
    "Limited": None,
    "Not Applicable": None,
}


def _overall_risk(dim_risks: list[str]) -> str:
    """加权多数决：High ≥ 2 → High；High=1 或 Medium ≥ 2 → Medium；否则 Low。

    Limited/Not Applicable 维度不纳入计算。
    """
    counted = [r for r in dim_risks if r in ("Low", "Medium", "High")]
    if not counted:
        return "Limited"
    high_cnt = counted.count("High")
    med_cnt = counted.count("Medium")
    if high_cnt >= 2:
        return "High"
    if high_cnt == 1 or med_cnt >= 2:
        return "Medium"
    return "Low"


class ValueTrapDetector(BaseValuation):
    """五维度价值陷阱风险检测（量化 + 占位）。

    维度：财务健康、业务恶化、护城河侵蚀、AI/技术脆弱性（占位）、股息可持续性。
    output_type = "score"；fair_value = current_price（不参与区间聚合）。
    """

    method_name = "Value Trap Detector"

    required_fields = []

    best_for = [
        "Value investing due diligence",
        "Low P/B or Low P/E stocks",
        "Risk screening before position sizing",
    ]
    not_for = ["Growth stocks with negative earnings (use other risk checks)"]

    # ── 阈值常量 ────────────────────────────────────────────────────────────
    ALTMAN_SAFE = 2.99
    ALTMAN_DISTRESS = 1.81
    CR_SAFE = 1.5
    ICR_SAFE = 3.0
    ICR_WARN = 1.5
    DEBT_RATIO_HIGH = 0.70
    OM_LOW_RISK = 15.0
    OM_HIGH_RISK = 5.0
    ROE_LOW_RISK = 15.0
    ROE_HIGH_RISK = 8.0
    ROIC_LOW_RISK = 12.0
    ROIC_HIGH_RISK = 6.0
    PAYOUT_LOW_RISK = 60.0
    PAYOUT_HIGH_RISK = 100.0

    def calculate(self, stock) -> ValuationResult:  # noqa: C901
        current_price = getattr(stock, "current_price", None) or 0.0
        warnings: list[str] = []

        # ── 1. 财务健康 ────────────────────────────────────────────────────
        fin_risk, fin_note = self._financial_health(stock, warnings)

        # ── 2. 业务恶化 ────────────────────────────────────────────────────
        biz_risk, biz_note = self._business_deterioration(stock, warnings)

        # ── 3. 护城河侵蚀 ──────────────────────────────────────────────────
        moat_risk, moat_note = self._moat_erosion(stock)

        # ── 4. AI/技术脆弱性（占位，固定 Medium） ──────────────────────────
        ai_risk = "Medium"
        ai_note = "需人工评估：行业数字化程度与 AI 颠覆性依赖定性判断"

        # ── 5. 股息可持续性 ────────────────────────────────────────────────
        div_risk, div_note = self._dividend_sustainability(stock)

        dim_risks = [fin_risk, biz_risk, moat_risk, ai_risk, div_risk]
        overall = _overall_risk(dim_risks)

        if any(r == "Limited" for r in dim_risks):
            warnings_for_limited = [
                name
                for name, r in zip(
                    [
                        "financial_health",
                        "business_deterioration",
                        "moat_erosion",
                        "ai_vulnerability",
                        "dividend_sustainability",
                    ],
                    dim_risks,
                )
                if r == "Limited"
            ]
            warnings.append(
                f"Limited data for dimensions: {', '.join(warnings_for_limited)}"
            )

        assessment_map = {
            "Low": "Low Value Trap Risk",
            "Medium": "Medium Value Trap Risk",
            "High": "High Value Trap Risk",
            "Limited": "Insufficient data for full assessment",
        }

        analysis = [
            f"Overall Risk: {overall}",
            "",
            f"1. Financial Health: {fin_risk} — {fin_note}",
            f"2. Business Deterioration: {biz_risk} — {biz_note}",
            f"3. Moat Erosion: {moat_risk} — {moat_note}",
            f"4. AI/Tech Vulnerability: {ai_risk} — {ai_note}",
            f"5. Dividend Sustainability: {div_risk} — {div_note}",
        ]
        if warnings:
            analysis.extend(["", "Warnings:"] + [f"  - {w}" for w in warnings])

        limited_count = sum(1 for r in dim_risks if r in ("Limited", "Not Applicable"))
        confidence = (
            "High"
            if limited_count == 0
            else ("Medium" if limited_count <= 2 else "Low")
        )
        applicability = "Limited" if limited_count >= 4 else "Applicable"

        return ValuationResult(
            method=self.method_name,
            fair_value=current_price,
            current_price=current_price,
            premium_discount=0,
            assessment=assessment_map.get(overall, overall),
            details={
                "output_type": "score",
                "overall_risk": overall,
                "financial_health": fin_risk,
                "financial_health_note": fin_note,
                "business_deterioration": biz_risk,
                "business_deterioration_note": biz_note,
                "moat_erosion": moat_risk,
                "moat_erosion_note": moat_note,
                "ai_vulnerability": ai_risk,
                "ai_vulnerability_note": ai_note,
                "dividend_sustainability": div_risk,
                "dividend_sustainability_note": div_note,
            },
            analysis=analysis,
            confidence=confidence,
            fair_value_range=None,
            applicability=applicability,
        )

    # ── 维度计算辅助方法 ─────────────────────────────────────────────────────

    def _financial_health(self, stock, warnings: list[str]) -> tuple[str, str]:
        """维度 1：财务健康（Z-Score + 流动比率 + 利息覆盖率 + 负债率）。"""
        total_assets = getattr(stock, "total_assets", None)
        total_liabilities = getattr(stock, "total_liabilities", None)
        current_assets = getattr(stock, "current_assets", None)
        current_liabilities = getattr(stock, "current_liabilities", None)
        ebit = getattr(stock, "ebit", None)
        interest_expense = getattr(stock, "interest_expense", None)

        if total_assets is None:
            return "Limited", "total_assets unavailable"

        # Z-Score（复用 AltmanZScore 计算，捕获异常降级）
        z_score: float | None = None
        try:
            altman_result = _ALTMAN.calculate(stock)
            z_score = altman_result.details.get("z_score") if altman_result.error is None else None
        except Exception:
            pass

        # 流动比率
        cr: float | None = None
        if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
            cr = current_assets / current_liabilities

        # 利息覆盖率
        icr: float | None = None
        if ebit is not None and interest_expense is not None and interest_expense > 0:
            icr = ebit / interest_expense

        # 负债率
        debt_ratio: float | None = None
        if total_liabilities is not None:
            debt_ratio = total_liabilities / total_assets

        # 评级逻辑
        is_high = (
            (z_score is not None and z_score < self.ALTMAN_DISTRESS)
            or (icr is not None and icr < self.ICR_WARN)
            or (debt_ratio is not None and debt_ratio > self.DEBT_RATIO_HIGH)
        )
        is_low = (
            (z_score is not None and z_score > self.ALTMAN_SAFE)
            and (cr is None or cr > self.CR_SAFE)
            and (icr is None or icr > self.ICR_SAFE)
        )

        if is_high:
            note_parts = []
            if z_score is not None and z_score < self.ALTMAN_DISTRESS:
                note_parts.append(f"Z={z_score:.2f} (distress zone)")
            if icr is not None and icr < self.ICR_WARN:
                note_parts.append(f"ICR={icr:.1f}")
            if debt_ratio is not None and debt_ratio > self.DEBT_RATIO_HIGH:
                note_parts.append(f"D/A={debt_ratio:.0%}")
            return "High", "; ".join(note_parts) or "High financial stress"
        if is_low:
            return "Low", f"Z={z_score:.2f}, CR={cr:.2f}" if (z_score and cr) else "Strong financials"

        parts = []
        if z_score is not None:
            parts.append(f"Z={z_score:.2f}")
        if cr is not None:
            parts.append(f"CR={cr:.2f}")
        if icr is not None:
            parts.append(f"ICR={icr:.1f}")
        return "Medium", "; ".join(parts) or "Moderate financial health"

    def _business_deterioration(self, stock, warnings: list[str]) -> tuple[str, str]:
        """维度 2：业务恶化（营业利润率水平；revenue_growth 缺失时 Limited）。"""
        operating_margin = getattr(stock, "operating_margin", None)
        revenue_growth = getattr(stock, "revenue_growth", None)

        if operating_margin is None and revenue_growth is None:
            return "Limited", "operating_margin and revenue_growth unavailable"

        if revenue_growth is None:
            warnings.append("revenue_growth unavailable — business deterioration dimension uses operating_margin only")

        if operating_margin is not None:
            if operating_margin > self.OM_LOW_RISK:
                return "Low", f"Operating margin {operating_margin:.1f}% — healthy"
            if operating_margin < self.OM_HIGH_RISK:
                return "High", f"Operating margin {operating_margin:.1f}% — very thin"
            return "Medium", f"Operating margin {operating_margin:.1f}%"

        return "Limited", "revenue_growth unavailable"

    def _moat_erosion(self, stock) -> tuple[str, str]:
        """维度 3：护城河侵蚀（ROE + ROIC 水平）。"""
        roe = getattr(stock, "roe", None)
        roic = getattr(stock, "roic", None)

        if roe is None and roic is None:
            return "Limited", "ROE and ROIC unavailable"

        is_low = (roe is not None and roe > self.ROE_LOW_RISK) and (
            roic is not None and roic > self.ROIC_LOW_RISK
        )
        is_high = (roe is not None and roe < self.ROE_HIGH_RISK) or (
            roic is not None and roic < self.ROIC_HIGH_RISK
        )

        parts = []
        if roe is not None:
            parts.append(f"ROE={roe:.1f}%")
        if roic is not None:
            parts.append(f"ROIC={roic:.1f}%")
        note = "; ".join(parts)

        if is_low:
            return "Low", note + " — strong moat"
        if is_high:
            return "High", note + " — moat under pressure"
        return "Medium", note

    def _dividend_sustainability(self, stock) -> tuple[str, str]:
        """维度 5：股息可持续性（派息率 + FCF 覆盖）。"""
        dividend_per_share = getattr(stock, "dividend_per_share", None)
        payout_ratio = getattr(stock, "dividend_payout_ratio", None)
        fcf = getattr(stock, "fcf", None)

        if dividend_per_share is None:
            return "Not Applicable", "No dividend data"

        parts = []
        if payout_ratio is not None:
            parts.append(f"Payout={payout_ratio:.0f}%")
        if fcf is not None:
            parts.append(f"FCF={'positive' if fcf > 0 else 'negative'}")
        note = "; ".join(parts) if parts else "dividend present"

        is_high = (payout_ratio is not None and payout_ratio > self.PAYOUT_HIGH_RISK) or (
            fcf is not None and fcf < 0
        )
        is_low = (payout_ratio is not None and payout_ratio < self.PAYOUT_LOW_RISK) and (
            fcf is not None and fcf > 0
        )

        if is_high:
            return "High", note + " — sustainability risk"
        if is_low:
            return "Low", note + " — well covered"
        return "Medium", note
