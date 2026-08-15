"""保险内含价值（EV）/ 新业务价值（NBV）估值（P4）。"""

from __future__ import annotations

from typing import Any

from .base import BaseValuation, FieldRequirement, ValuationRange, ValuationResult
from .insurance_config import has_insurance_ev_inputs


class InsuranceEV(BaseValuation):
    """用报告/配置的 EV（及可选 NBV）给出每股对照公允价。

    不做无 EV 时的弱替代（与 design Open Question 默认「否」一致）。
    """

    method_name = "Insurance EV/NBV"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
        FieldRequirement("shares_outstanding", "Shares Outstanding", is_critical=True, min_value=0.01),
    ]

    best_for = ["寿险/综合保险（有披露或手工 EV）"]
    not_for = ["无 EV 输入的保险公司", "用银行/成长方法硬套的保险股"]

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}

    def calculate(self, stock) -> ValuationResult:
        if not has_insurance_ev_inputs(stock):
            return self._create_error_result(
                stock,
                "Missing embedded_value (insurance EV gate)",
                ["embedded_value"],
            )

        is_valid, missing, _ = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        ev = float(stock.embedded_value)
        shares = float(stock.shares_outstanding)
        nbv = getattr(stock, "nbv", None)
        nbv_val = float(nbv) if nbv is not None and float(nbv) > 0 else 0.0

        p_ev = getattr(stock, "p_ev_fair", None)
        if p_ev is None:
            p_ev = _default_p_ev(self._config, getattr(stock, "code", None))
        p_ev = float(p_ev)
        if p_ev <= 0:
            p_ev = 1.0

        # 基准：公允权益 ≈ EV × P/EV；高档可选加一年 NBV（粗 Appraisal Value）
        base_equity = ev * p_ev
        high_equity = (ev + nbv_val) * p_ev if nbv_val > 0 else base_equity * 1.1
        low_equity = ev * max(p_ev - 0.15, 0.5)

        fair_value = base_equity / shares
        low = low_equity / shares
        high = high_equity / shares
        ordered = sorted([low, fair_value, high])

        price = float(stock.current_price)
        ev_ps = ev / shares
        p_ev_actual = price / ev_ps if ev_ps > 0 else 0.0
        premium = ((fair_value - price) / price) * 100 if price else 0.0
        assessment = _assessment(price, fair_value, p_ev_actual, p_ev)

        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=price,
            premium_discount=round(premium, 1),
            assessment=assessment,
            details={
                "output_type": "insurance_ev",
                "embedded_value": ev,
                "nbv": nbv_val if nbv_val > 0 else None,
                "ev_per_share": round(ev_ps, 2),
                "p_ev_actual": round(p_ev_actual, 2),
                "p_ev_fair": p_ev,
            },
            analysis=[
                f"内含价值 EV: {ev / 1e8:.2f} 亿元（每股 {ev_ps:.2f}）",
                f"当前 P/EV: {p_ev_actual:.2f}x（公允假设 {p_ev:.2f}x）",
                *(
                    [f"一年新业务价值 NBV: {nbv_val / 1e8:.2f} 亿元（已纳入高档敏感性）"]
                    if nbv_val > 0
                    else ["未提供 NBV：高档仅用 P/EV 上浮敏感性"]
                ),
                assessment,
                "EV/NBV 依赖报告或配置手工输入；缺 EV 时不得用通用方法假装适用",
            ],
            confidence="Low",
            fair_value_range=ValuationRange(
                low=round(ordered[0], 2),
                base=round(fair_value, 2),
                high=round(ordered[2], 2),
            ),
            applicability="Applicable",
        )


def _default_p_ev(config: dict[str, Any], code: str | None) -> float:
    section = ((config or {}).get("value_analysis") or {}).get("insurance") or {}
    by_code = section.get("by_code") or {}
    code_cfg = by_code.get(code or "") if isinstance(by_code, dict) else None
    if isinstance(code_cfg, dict) and code_cfg.get("p_ev_fair") is not None:
        return float(code_cfg["p_ev_fair"])
    if section.get("p_ev_fair") is not None:
        return float(section["p_ev_fair"])
    return 1.0


def _assessment(price: float, fair: float, p_ev_actual: float, p_ev_fair: float) -> str:
    mos = (fair - price) / fair * 100 if fair > 0 else 0.0
    if mos >= 20:
        tone = "相对 EV 公允偏便宜"
    elif mos >= 5:
        tone = "相对 EV 公允略便宜"
    elif mos >= -5:
        tone = "相对 EV 公允大致相当"
    elif mos >= -20:
        tone = "相对 EV 公允略贵"
    else:
        tone = "相对 EV 公允偏贵"
    return f"当前 P/EV {p_ev_actual:.2f}x（公允假设 {p_ev_fair:.2f}x）；{tone}"
