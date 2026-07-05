"""Tushare Pro 列名 → StockData 字段映射。

参考：ref/valueinvest/valueinvest/data/fetcher/tushare.py（只读，禁止 import）
Tushare 金额单位因接口而异，缩放规则见 SCALE_WAN_FIELDS / SCALE_SHARE_WAN_FIELDS。
"""

from __future__ import annotations

# ── daily 日线行情 ─────────────────────────────────────────────────────────────
DAILY_FIELD_MAP: dict[str, str] = {
    "close": "current_price",
}

# ── daily_basic 每日指标 ───────────────────────────────────────────────────────
DAILY_BASIC_FIELD_MAP: dict[str, str] = {
    "pe_ttm": "pe_ratio",
    "pb": "pb_ratio",
    "total_mv": "market_cap",
    "total_share": "shares_outstanding",
    "dv_ratio": "dividend_yield",
}

STOCK_BASIC_FIELD_MAP: dict[str, str] = {
    "name": "name",
    "industry": "industry",
}

# ── fina_indicator 财务指标 ────────────────────────────────────────────────────
FINA_INDICATOR_FIELD_MAP: dict[str, str] = {
    "eps": "eps",
    "bps": "bvps",
    "roe": "roe",
    "roic": "roic",
    "netprofit_margin": "operating_margin",
    "grossprofit_margin": "_gross_margin",
    "debt_to_assets": "_debt_to_assets",
    "ocfps": "_ocfps",
    "netint_margin": "net_interest_margin",
    "npl_ratio": "npl_ratio",
    "prov_cov": "provision_coverage",
}

# ── income 利润表 ──────────────────────────────────────────────────────────────
INCOME_FIELD_MAP: dict[str, str] = {
    "revenue": "revenue",
    "n_income_attr_p": "net_income",
    "operate_profit": "ebit",
    "fin_exp_int_exp": "interest_expense",
}

# ── balancesheet 资产负债表 ──────────────────────────────────────────────────
BALANCE_SHEET_FIELD_MAP: dict[str, str] = {
    "total_assets": "total_assets",
    "total_liab": "total_liabilities",
    "total_cur_assets": "current_assets",
    "total_cur_liab": "current_liabilities",
    "total_hldr_eqy_exc_min_int": "shareholder_equity",
    "accounts_receiv": "accounts_receivable",
    "inventories": "inventory",
    "acct_payable": "accounts_payable",
    "st_borr": "short_term_debt",
    "lt_borr": "long_term_debt",
    "money_cap": "cash",
    "fix_assets": "net_fixed_assets",
}

# ── cashflow 现金流量表 ────────────────────────────────────────────────────────
CASHFLOW_FIELD_MAP: dict[str, str] = {
    "c_pay_acq_const_fiolta": "capex",
    "depr_fa_cog_dp": "depreciation",
    "n_cashflow_act": "_operating_cashflow",
}

# ── dividend 分红 ──────────────────────────────────────────────────────────────
DIVIDEND_FIELD_MAP: dict[str, str] = {
    "cash_div_tax": "dividend_per_share",
}

# 万元 → 元
SCALE_WAN_FIELDS: frozenset[str] = frozenset({"market_cap"})

# 万股 → 股
SCALE_SHARE_WAN_FIELDS: frozenset[str] = frozenset({"shares_outstanding"})
