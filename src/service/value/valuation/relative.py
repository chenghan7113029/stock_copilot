"""历史 PE/PB 相对估值方法。"""

from __future__ import annotations

from .base import BaseValuation, FieldRequirement, ValuationResult


class PERelativeValuation(BaseValuation):
    """基于历史 PE 均值的相对估值。"""

    method_name = "PE Relative"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
        FieldRequirement("eps", "Earnings Per Share", is_critical=True),
        FieldRequirement("historical_pe", "Historical PE Ratios", is_critical=False),
    ]

    best_for = [
        "Profitable companies with stable earnings",
        "Mature companies with trading history",
    ]
    not_for = [
        "Negative earnings companies",
        "Early-stage startups",
        "Highly cyclical companies (use normalized PE)",
    ]

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, warnings = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        historical_pe = stock.historical_pe
        if historical_pe is None or len(historical_pe) < 3:
            return ValuationResult(
                method=self.method_name,
                fair_value=0,
                current_price=stock.current_price,
                premium_discount=0,
                assessment="N/A - Insufficient historical PE data",
                missing_fields=["historical_pe"],
                confidence="N/A",
                applicability="Not Applicable",
                error="historical_pe is None or has fewer than 3 data points",
                analysis=["Cannot calculate: need at least 3 historical PE observations"],
            )

        if stock.eps is None or stock.eps <= 0:
            return self._create_error_result(
                stock, "EPS must be positive for PE relative valuation", ["eps"]
            )

        current_pe = stock.pe_ratio
        if current_pe <= 0:
            return self._create_error_result(
                stock, "P/E ratio must be positive (company must be profitable)", ["pe_ratio"]
            )

        hist_avg = sum(historical_pe) / len(historical_pe)
        fair_value = stock.eps * hist_avg
        premium_discount = ((fair_value - stock.current_price) / stock.current_price) * 100

        sorted_pe = sorted(historical_pe)
        hist_low = min(historical_pe)
        hist_high = max(historical_pe)
        percentile = (
            ((current_pe - hist_low) / (hist_high - hist_low)) * 100
            if hist_high > hist_low
            else 50.0
        )

        if percentile < 25:
            assessment = "Undervalued (bottom quartile historically)"
        elif percentile < 40:
            assessment = "Undervalued"
        elif percentile <= 60:
            assessment = "Fair Value"
        elif percentile <= 75:
            assessment = "Overvalued"
        else:
            assessment = "Overvalued (top quartile historically)"

        vs_historical = ((current_pe - hist_avg) / hist_avg) * 100 if hist_avg > 0 else 0.0

        analysis = [
            f"Current P/E: {current_pe:.1f}x",
            f"Historical Average: {hist_avg:.1f}x ({len(historical_pe)} data points)",
            f"Historical Range: {hist_low:.1f}x - {hist_high:.1f}x",
            f"Current Percentile: {percentile:.0f}th",
            f"vs Historical: {vs_historical:+.1f}%",
            f"Fair Value (EPS × avg PE): {fair_value:.2f}",
            f"Premium/Discount: {premium_discount:+.1f}%",
        ]
        if warnings:
            analysis.extend([f"Note: {w}" for w in warnings])

        confidence = (
            "High" if len(historical_pe) >= 10 else ("Medium" if len(historical_pe) >= 5 else "Low")
        )

        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=stock.current_price,
            premium_discount=round(premium_discount, 1),
            assessment=assessment,
            details={
                "current_pe": round(current_pe, 2),
                "historical_avg_pe": round(hist_avg, 2),
                "historical_median_pe": round(sorted_pe[len(sorted_pe) // 2], 2),
                "historical_low_pe": round(hist_low, 2),
                "historical_high_pe": round(hist_high, 2),
                "percentile_in_history": round(percentile, 1),
                "vs_historical_pct": round(vs_historical, 1),
                "data_points": len(historical_pe),
            },
            components={"current_pe": current_pe, "historical_avg": hist_avg},
            analysis=analysis,
            confidence=confidence,
            applicability="Applicable",
        )


class PBRelativeValuation(BaseValuation):
    """基于历史 PB 均值的相对估值。"""

    method_name = "PB Relative"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
        FieldRequirement("bvps", "Book Value Per Share", is_critical=True),
        FieldRequirement("historical_pb", "Historical PB Ratios", is_critical=False),
    ]

    best_for = [
        "Banks and financials",
        "Asset-heavy companies",
        "Value investing",
    ]
    not_for = [
        "Asset-light companies (software, services)",
        "Companies with significant intangibles",
        "Negative book value companies",
    ]

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, warnings = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        historical_pb = stock.historical_pb
        if historical_pb is None or len(historical_pb) < 3:
            return ValuationResult(
                method=self.method_name,
                fair_value=0,
                current_price=stock.current_price,
                premium_discount=0,
                assessment="N/A - Insufficient historical PB data",
                missing_fields=["historical_pb"],
                confidence="N/A",
                applicability="Not Applicable",
                error="historical_pb is None or has fewer than 3 data points",
                analysis=["Cannot calculate: need at least 3 historical PB observations"],
            )

        if stock.bvps is None or stock.bvps <= 0:
            return self._create_error_result(stock, "BVPS must be positive", ["bvps"])

        current_pb = stock.pb_ratio
        if current_pb <= 0:
            return self._create_error_result(stock, "P/B ratio must be positive", ["pb_ratio"])

        hist_avg = sum(historical_pb) / len(historical_pb)
        fair_value = stock.bvps * hist_avg
        premium_discount = ((fair_value - stock.current_price) / stock.current_price) * 100

        sorted_pb = sorted(historical_pb)
        hist_low = min(historical_pb)
        hist_high = max(historical_pb)
        percentile = (
            ((current_pb - hist_low) / (hist_high - hist_low)) * 100
            if hist_high > hist_low
            else 50.0
        )

        if percentile < 25:
            assessment = "Undervalued (bottom quartile historically)"
        elif percentile < 40:
            assessment = "Undervalued"
        elif percentile <= 60:
            assessment = "Fair Value"
        elif percentile <= 75:
            assessment = "Overvalued"
        else:
            assessment = "Overvalued (top quartile historically)"

        vs_historical = ((current_pb - hist_avg) / hist_avg) * 100 if hist_avg > 0 else 0.0

        analysis = [
            f"Current P/B: {current_pb:.2f}x",
            f"Historical Average: {hist_avg:.2f}x ({len(historical_pb)} data points)",
            f"Historical Range: {hist_low:.2f}x - {hist_high:.2f}x",
            f"Current Percentile: {percentile:.0f}th",
            f"vs Historical: {vs_historical:+.1f}%",
            f"Fair Value (BVPS × avg PB): {fair_value:.2f}",
            f"Premium/Discount: {premium_discount:+.1f}%",
        ]
        if warnings:
            analysis.extend([f"Note: {w}" for w in warnings])

        confidence = (
            "High" if len(historical_pb) >= 10 else ("Medium" if len(historical_pb) >= 5 else "Low")
        )

        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=stock.current_price,
            premium_discount=round(premium_discount, 1),
            assessment=assessment,
            details={
                "current_pb": round(current_pb, 2),
                "historical_avg_pb": round(hist_avg, 2),
                "historical_median_pb": round(sorted_pb[len(sorted_pb) // 2], 2),
                "historical_low_pb": round(hist_low, 2),
                "historical_high_pb": round(hist_high, 2),
                "percentile_in_history": round(percentile, 1),
                "vs_historical_pct": round(vs_historical, 1),
                "data_points": len(historical_pb),
            },
            components={"current_pb": current_pb, "historical_avg": hist_avg},
            analysis=analysis,
            confidence=confidence,
            applicability="Applicable",
        )
