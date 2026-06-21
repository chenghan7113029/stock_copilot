"""WACC（加权平均资本成本）计算。"""

from __future__ import annotations

from dataclasses import dataclass

from .assumptions import AssumptionProvider


@dataclass
class WACCResult:
    cost_of_equity: float
    cost_of_debt: float
    equity_weight: float
    debt_weight: float
    wacc: float
    beta_used: float | None = None
    risk_free_rate: float | None = None
    equity_risk_premium: float | None = None
    tax_rate_used: float | None = None
    method: str = "WACC"
    confidence: str = "Medium"


def calculate_wacc(
    stock,
    assumptions: AssumptionProvider | None = None,
    beta: float | None = None,
    risk_free_rate: float | None = None,
    equity_risk_premium: float | None = None,
    cost_of_equity_override: float | None = None,
    cost_of_debt_override: float | None = None,
) -> WACCResult:
    """Port 自 ref/valueinvest/valueinvest/roic/wacc.py。"""
    provider = assumptions or AssumptionProvider()
    erp = equity_risk_premium if equity_risk_premium is not None else provider.equity_risk_premium

    tax_rate = getattr(stock, "tax_rate", None)
    if tax_rate is None or tax_rate <= 0:
        tax_rate = provider.get_tax_rate(stock.data if hasattr(stock, "data") else stock)
    else:
        tax_rate = float(tax_rate)

    market_cap = getattr(stock, "market_cap", None) or 0.0
    ev = getattr(stock, "enterprise_value", None) or 0.0
    net_debt = getattr(stock, "net_debt", None)
    if net_debt is None:
        net_debt = 0.0

    currency = getattr(stock, "currency", "CNY")
    if risk_free_rate is not None:
        rf = risk_free_rate
    elif currency == "USD":
        rf = 4.3
    else:
        rf = getattr(stock, "china_10y_yield", provider.china_10y_yield)

    if cost_of_equity_override is not None:
        cost_of_equity = cost_of_equity_override
        method = "Simplified (override)"
    elif beta is not None:
        cost_of_equity = rf + beta * erp
        method = "CAPM"
    else:
        cost_of_equity = getattr(stock, "cost_of_capital", provider.discount_rate)
        method = "Simplified"

    interest_expense = getattr(stock, "interest_expense", None) or 0.0
    short_term_debt = getattr(stock, "short_term_debt", None) or 0.0
    long_term_debt = getattr(stock, "long_term_debt", None) or 0.0
    total_debt = short_term_debt + long_term_debt
    aaa_yield = getattr(stock, "aaa_corporate_yield", provider.aaa_corporate_yield)

    if cost_of_debt_override is not None:
        cost_of_debt = cost_of_debt_override
    elif interest_expense > 0 and total_debt > 0:
        cost_of_debt = interest_expense / total_debt * 100
    else:
        cost_of_debt = aaa_yield

    if ev > 0:
        equity_weight = market_cap / ev
        debt_weight = net_debt / ev
    elif market_cap > 0:
        equity_weight = 1.0
        debt_weight = 0.0
    else:
        equity_weight = 1.0
        debt_weight = 0.0

    after_tax_cost_of_debt = cost_of_debt * (1 - tax_rate / 100)
    wacc = equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt

    if method == "CAPM" and interest_expense > 0:
        confidence = "High"
    elif method == "Simplified":
        confidence = "Medium"
    else:
        confidence = "Medium"

    return WACCResult(
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        equity_weight=equity_weight,
        debt_weight=debt_weight,
        wacc=wacc,
        beta_used=beta,
        risk_free_rate=rf,
        equity_risk_premium=erp,
        tax_rate_used=tax_rate,
        method=method,
        confidence=confidence,
    )
