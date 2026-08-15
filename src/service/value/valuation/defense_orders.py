"""军工在手订单驱动估值（P3）。"""

from __future__ import annotations

from typing import Any

from .base import BaseValuation, FieldRequirement, ValuationRange, ValuationResult
from .defense_config import has_defense_order_inputs


class DefenseOrders(BaseValuation):
    """把在手订单粗略折现为权益价值：订单利润年金 + 可选资产重估。"""

    method_name = "Defense Orders"

    required_fields = [
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
        FieldRequirement("shares_outstanding", "Shares Outstanding", is_critical=True, min_value=0.01),
    ]

    best_for = ["军工/订单驱动（在手订单可观测）"]
    not_for = ["无订单输入的军工股", "订单不可信或不可比"]

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}

    def calculate(self, stock) -> ValuationResult:
        if not has_defense_order_inputs(stock):
            return self._create_error_result(
                stock,
                "Missing order_backlog / order_execution_years (defense order gate)",
                ["order_backlog", "order_execution_years"],
            )

        is_valid, missing, _ = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        backlog = float(stock.order_backlog)
        years = float(stock.order_execution_years)
        margin = getattr(stock, "order_margin", None)
        if margin is None:
            # 回退：用营业利润率；再不行用保守 8%
            margin = getattr(stock, "operating_margin", None)
        if margin is None or float(margin) <= 0:
            margin = 8.0
        else:
            margin = float(margin)

        discount = _discount_rate(stock, self._config)
        tax = getattr(stock, "tax_rate", None)
        tax_rate = float(tax) / 100.0 if tax is not None else 0.25

        annual_revenue = backlog / years
        annual_pretax = annual_revenue * (margin / 100.0)
        annual_after_tax = annual_pretax * (1.0 - tax_rate)

        # 有限年订单利润折现（不做永续，避免把订单当成无限成长）
        pv_orders = 0.0
        r = discount / 100.0
        for t in range(1, int(years) + 1):
            # 非整数年：最后一年按比例；简化用整年循环 + 小数年追加
            pv_orders += annual_after_tax / ((1.0 + r) ** t)
        frac = years - int(years)
        if frac > 1e-9:
            t = int(years) + 1
            pv_orders += (annual_after_tax * frac) / ((1.0 + r) ** t)

        reval = float(getattr(stock, "revaluation_assets", None) or 0.0)
        net_cash = 0.0
        cash = getattr(stock, "cash", None)
        net_debt = getattr(stock, "net_debt", None)
        if net_debt is not None:
            net_cash = -float(net_debt)
        elif cash is not None:
            net_cash = float(cash)

        equity_value = pv_orders + reval + net_cash
        shares = float(stock.shares_outstanding)
        fair_value = equity_value / shares if shares > 0 else 0.0
        if fair_value <= 0:
            return self._create_error_result(
                stock, "Defense order model produced non-positive fair value", ["order_backlog"]
            )

        price = float(stock.current_price)
        premium = ((fair_value - price) / price) * 100 if price else 0.0
        assessment = _assessment(price, fair_value, years)

        # 敏感性：利润率 ±20%、折现率 ±2pt
        low = _fair_with(stock, margin * 0.8, discount + 2.0, years, backlog, tax_rate, reval, net_cash)
        high = _fair_with(stock, margin * 1.2, max(discount - 2.0, 4.0), years, backlog, tax_rate, reval, net_cash)
        ordered = sorted([low, fair_value, high])

        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_value, 2),
            current_price=price,
            premium_discount=round(premium, 1),
            assessment=assessment,
            details={
                "output_type": "defense_orders",
                "order_backlog": backlog,
                "order_execution_years": years,
                "order_margin": margin,
                "discount_rate": discount,
                "annual_after_tax_profit": round(annual_after_tax, 2),
                "pv_orders": round(pv_orders, 2),
                "revaluation_assets": reval,
                "net_cash": net_cash,
                "equity_value": round(equity_value, 2),
            },
            analysis=[
                f"在手订单: {backlog / 1e8:.2f} 亿元，消化 {years:.1f} 年",
                f"隐含年化税后利润: {annual_after_tax / 1e8:.2f} 亿元（利润率 {margin:.1f}%）",
                f"订单利润现值: {pv_orders / 1e8:.2f} 亿元（折现率 {discount:.1f}%）",
                assessment,
                "主结论依赖手工/配置订单输入；缺输入时不得假装适用",
            ],
            confidence="Low",  # 订单多为手工输入，默认低置信
            fair_value_range=ValuationRange(
                low=round(ordered[0], 2),
                base=round(fair_value, 2),
                high=round(ordered[2], 2),
            ),
            applicability="Applicable",
        )


def _discount_rate(stock, config: dict[str, Any]) -> float:
    section = ((config or {}).get("value_analysis") or {}).get("defense_orders") or {}
    by_code = section.get("by_code") or {}
    code_cfg = by_code.get(getattr(stock, "code", ""), {}) if isinstance(by_code, dict) else {}
    if isinstance(code_cfg, dict) and code_cfg.get("discount_rate") is not None:
        return float(code_cfg["discount_rate"])
    if section.get("discount_rate") is not None:
        return float(section["discount_rate"])
    # CAPM-ish fallback via adapter cost_of_capital if present
    coc = getattr(stock, "cost_of_capital", None) or getattr(stock, "discount_rate", None)
    if coc is not None:
        return float(coc)
    return 10.0


def _fair_with(
    stock,
    margin: float,
    discount: float,
    years: float,
    backlog: float,
    tax_rate: float,
    reval: float,
    net_cash: float,
) -> float:
    annual_after_tax = (backlog / years) * (margin / 100.0) * (1.0 - tax_rate)
    r = discount / 100.0
    pv = 0.0
    for t in range(1, int(years) + 1):
        pv += annual_after_tax / ((1.0 + r) ** t)
    frac = years - int(years)
    if frac > 1e-9:
        pv += (annual_after_tax * frac) / ((1.0 + r) ** (int(years) + 1))
    shares = float(stock.shares_outstanding)
    return (pv + reval + net_cash) / shares


def _assessment(price: float, fair: float, years: float) -> str:
    mos = (fair - price) / fair * 100 if fair > 0 else 0.0
    if mos >= 20:
        tone = "相对订单折现公允偏便宜"
    elif mos >= 5:
        tone = "相对订单折现公允略便宜"
    elif mos >= -5:
        tone = "相对订单折现公允大致相当"
    elif mos >= -20:
        tone = "相对订单折现公允略贵"
    else:
        tone = "相对订单折现公允偏贵"
    return f"在手订单约 {years:.1f} 年消化；{tone}"
