"""周期调整估值：Cyclical PE / Cyclical FCF（P2 子集）。"""

from __future__ import annotations

import statistics
from typing import Any

from .base import BaseValuation, FieldRequirement, ValuationRange, ValuationResult
from .cycle_config import cycle_position_label_zh

# A 股阈值（对齐 valueinvest 参考实现的量级）
_PE_FAIR = 15.0
_PE_BUY = 12.0
_PE_SELL = 20.0
_FCF_YIELD_FAIR = 7.0
_FCF_YIELD_BUY = 10.0
_FCF_YIELD_SELL = 5.0


def _require_cycle_position(stock) -> ValuationResult | None:
    position = getattr(stock, "cycle_position", None)
    if not position:
        return ValuationResult(
            method="",
            fair_value=0,
            current_price=float(getattr(stock, "current_price", 0) or 0),
            premium_discount=0,
            assessment="N/A",
            error="Missing cycle_position (refuse to value cyclical stock without cycle context)",
            missing_fields=["cycle_position"],
            confidence="N/A",
            applicability="Not Applicable",
        )
    return None


def _resolve_normalized_eps(stock) -> tuple[float | None, str | None]:
    normalized = getattr(stock, "normalized_eps", None)
    if normalized is not None and float(normalized) > 0:
        return float(normalized), "normalized_eps"

    historical_roe = getattr(stock, "historical_roe", None) or []
    bvps = getattr(stock, "bvps", None)
    if historical_roe and len(historical_roe) >= 3 and bvps is not None and float(bvps) > 0:
        avg_roe = statistics.mean(float(x) for x in historical_roe)
        return (avg_roe / 100.0) * float(bvps), "historical_roe_x_bvps"

    return None, None


def _resolve_normalized_fcf_per_share(stock) -> tuple[float | None, str | None]:
    shares = getattr(stock, "shares_outstanding", None)
    if shares is None or float(shares) <= 0:
        return None, None

    normalized = getattr(stock, "normalized_fcf", None)
    if normalized is not None and float(normalized) > 0:
        return float(normalized) / float(shares), "normalized_fcf"

    historical_fcf = getattr(stock, "historical_fcf", None) or []
    positive = [float(x) for x in historical_fcf if x is not None and float(x) > 0]
    if len(positive) >= 3:
        return statistics.mean(positive) / float(shares), "historical_fcf_mean"

    fcf = getattr(stock, "fcf", None)
    if fcf is not None and float(fcf) > 0:
        # 有 cycle_position 门禁时，允许用当期 FCF，但标记为非均值化
        return float(fcf) / float(shares), "current_fcf"

    return None, None


def _position_aware_assessment(price: float, fair: float, position: str) -> str:
    label = cycle_position_label_zh(position)
    if fair <= 0:
        return f"周期位置：{label}；估值数据不足"
    mos = (fair - price) / fair * 100
    if mos >= 20:
        tone = "相对周期调整公允偏便宜"
    elif mos >= 5:
        tone = "相对周期调整公允略便宜"
    elif mos >= -5:
        tone = "相对周期调整公允大致相当"
    elif mos >= -20:
        tone = "相对周期调整公允略贵"
    else:
        tone = "相对周期调整公允偏贵"
    return f"周期位置：{label}；{tone}"


class CyclicalPE(BaseValuation):
    method_name = "Cyclical PE"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
    ]

    best_for = ["盈利波动的周期股", "广告/可选消费等顺周期轻资产"]
    not_for = ["无周期位置的股票", "持续亏损且无均值化 EPS"]

    def calculate(self, stock) -> ValuationResult:
        gate = _require_cycle_position(stock)
        if gate is not None:
            gate.method = self.method_name
            return gate

        price = float(stock.current_price)
        position = str(stock.cycle_position)
        cyclical_eps, eps_source = _resolve_normalized_eps(stock)
        if cyclical_eps is None or cyclical_eps <= 0:
            return self._create_error_result(
                stock,
                "Cyclical PE needs normalized_eps or historical_roe×bvps",
                ["normalized_eps"],
            )

        fair_value = cyclical_eps * _PE_FAIR
        cyclical_pe = price / cyclical_eps if cyclical_eps > 0 else 0.0
        current_eps = getattr(stock, "eps", None)
        premium = ((fair_value - price) / price) * 100 if price else 0.0
        assessment = _position_aware_assessment(price, fair_value, position)

        low = cyclical_eps * _PE_BUY
        high = cyclical_eps * _PE_SELL
        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=price,
            premium_discount=round(premium, 1),
            assessment=assessment,
            details={
                "output_type": "cyclical",
                "cycle_position": position,
                "cycle_position_label": cycle_position_label_zh(position),
                "cyclical_adjusted_eps": round(cyclical_eps, 4),
                "cyclical_adjusted_pe": round(cyclical_pe, 2),
                "current_eps": current_eps,
                "eps_source": eps_source,
                "fair_pe": _PE_FAIR,
            },
            analysis=[
                f"周期位置: {cycle_position_label_zh(position)}",
                f"均值化 EPS: {cyclical_eps:.3f}（来源 {eps_source}）",
                f"周期调整 PE: {cyclical_pe:.1f}（公允倍数 {_PE_FAIR:.0f}x）",
                assessment,
            ],
            confidence="Medium" if eps_source == "normalized_eps" else "Low",
            fair_value_range=ValuationRange(low=round(low, 2), base=round(fair_value, 2), high=round(high, 2)),
            applicability="Applicable",
        )


class CyclicalFCF(BaseValuation):
    method_name = "Cyclical FCF"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
        FieldRequirement("shares_outstanding", "Shares Outstanding", is_critical=True, min_value=0.01),
    ]

    best_for = ["高 FCF 的顺周期轻资产（如广告）", "利润波动大但现金流可读的周期股"]
    not_for = ["无周期位置", "持续负 FCF"]

    def calculate(self, stock) -> ValuationResult:
        gate = _require_cycle_position(stock)
        if gate is not None:
            gate.method = self.method_name
            return gate

        is_valid, missing, _ = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        price = float(stock.current_price)
        position = str(stock.cycle_position)
        fcf_ps, fcf_source = _resolve_normalized_fcf_per_share(stock)
        if fcf_ps is None or fcf_ps <= 0:
            return self._create_error_result(
                stock,
                "Cyclical FCF needs positive normalized/current FCF",
                ["fcf"],
            )

        fair_value = fcf_ps / (_FCF_YIELD_FAIR / 100.0)
        market_cap = None
        shares = float(stock.shares_outstanding)
        if getattr(stock, "market_cap", None):
            market_cap = float(stock.market_cap)
        else:
            market_cap = price * shares
        fcf_total = fcf_ps * shares
        fcf_yield = (fcf_total / market_cap) * 100 if market_cap > 0 else 0.0
        premium = ((fair_value - price) / price) * 100 if price else 0.0
        assessment = _position_aware_assessment(price, fair_value, position)

        low = fcf_ps / (_FCF_YIELD_BUY / 100.0)
        high = fcf_ps / (_FCF_YIELD_SELL / 100.0)
        # buy yield higher → lower price; ensure low<=base<=high
        ordered = sorted([low, fair_value, high])
        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=price,
            premium_discount=round(premium, 1),
            assessment=assessment,
            details={
                "output_type": "cyclical",
                "cycle_position": position,
                "cycle_position_label": cycle_position_label_zh(position),
                "fcf_per_share": round(fcf_ps, 4),
                "fcf_yield": round(fcf_yield, 2),
                "fair_fcf_yield": _FCF_YIELD_FAIR,
                "fcf_source": fcf_source,
            },
            analysis=[
                f"周期位置: {cycle_position_label_zh(position)}",
                f"每股 FCF: {fcf_ps:.3f}（来源 {fcf_source}）",
                f"当前 FCF Yield: {fcf_yield:.1f}%（公允 {_FCF_YIELD_FAIR:.0f}%）",
                assessment,
            ],
            confidence="Medium" if fcf_source != "current_fcf" else "Low",
            fair_value_range=ValuationRange(
                low=round(ordered[0], 2),
                base=round(fair_value, 2),
                high=round(ordered[2], 2),
            ),
            applicability="Applicable",
        )
