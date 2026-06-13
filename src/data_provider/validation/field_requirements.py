"""原型 → 必需字段映射表（MRD §7 V1 三原型）。

银行、高股息·类债、高质量价值成长各自需要哪些字段才能正常运行估值方法。
缺失必需字段时，对应方法标注"数据缺失不可靠"，不参与区间聚合（MRD VA-DATA-1）。
"""

from __future__ import annotations

from typing import FrozenSet

# ── 按类别分组的字段集 ────────────────────────────────────────────────────────

QUOTE_FIELDS: FrozenSet[str] = frozenset({
    "current_price",
    "shares_outstanding",
    "market_cap",
})

PER_SHARE_FIELDS: FrozenSet[str] = frozenset({
    "eps",
    "bvps",
    "dividend_per_share",
})

PROFITABILITY_FIELDS: FrozenSet[str] = frozenset({
    "revenue",
    "net_income",
    "roe",
})

CASHFLOW_FIELDS: FrozenSet[str] = frozenset({
    "fcf",
})

BALANCE_FIELDS: FrozenSet[str] = frozenset({
    "total_assets",
    "total_liabilities",
    "shareholder_equity",
})

DIVIDEND_FIELDS: FrozenSet[str] = frozenset({
    "dividend_yield",
    "dividend_payout_ratio",
})

QUALITY_FIELDS: FrozenSet[str] = frozenset({
    "roic",
    "operating_margin",
    "ebit",
})

# 银行专用
BANK_SPECIFIC_FIELDS: FrozenSet[str] = frozenset({
    "net_interest_margin",
    "npl_ratio",
    "provision_coverage",
})

# ── 各原型必需字段 ────────────────────────────────────────────────────────────
# 格式：原型 → (必需字段集, 可选字段集, 银行专属 TODO 字段集)

PROTOTYPE_REQUIRED_FIELDS: dict[str, FrozenSet[str]] = {
    "bank": (
        QUOTE_FIELDS
        | PER_SHARE_FIELDS
        | PROFITABILITY_FIELDS
        | BALANCE_FIELDS
        | DIVIDEND_FIELDS
    ),
    "high_dividend": (
        QUOTE_FIELDS
        | PER_SHARE_FIELDS
        | PROFITABILITY_FIELDS
        | CASHFLOW_FIELDS
        | BALANCE_FIELDS
        | DIVIDEND_FIELDS
    ),
    "value_growth": (
        QUOTE_FIELDS
        | PER_SHARE_FIELDS
        | PROFITABILITY_FIELDS
        | CASHFLOW_FIELDS
        | BALANCE_FIELDS
        | QUALITY_FIELDS
    ),
}

# 银行专属字段（当前列为 TODO，V1 完备性检查中仅作警告，不报致命错误）
BANK_TODO_FIELDS: FrozenSet[str] = BANK_SPECIFIC_FIELDS


def get_required_fields(prototype: str) -> FrozenSet[str]:
    """返回指定原型的必需字段集合。未知原型返回空集。"""
    return PROTOTYPE_REQUIRED_FIELDS.get(prototype.lower(), frozenset())
