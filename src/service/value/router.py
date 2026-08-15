"""股票原型路由：分类 + method_keys 选择。"""

from __future__ import annotations

from dataclasses import dataclass

from common.models.stock_data import StockData

_CODE_OVERRIDE: dict[str, str] = {
    "601398": "bank",
    "601328": "bank",
    "601939": "bank",
    "600036": "bank",
    "600900": "high_dividend",
    "600519": "value_growth",
    "002594": "growth_manufacturing",
    "002027": "cashflow_ad_cycle",
    "600072": "defense_orders",
    "601318": "insurance",
    "300627": "growth_tech",
}

# code → (标签, 方法论/偏差说明基句)；命中后短路为 unknown（诚实层）
# P1–P5：持仓样本已毕业；其他军工与其他保险仍走行业诚实层
_CODE_V2_HONESTY: dict[str, tuple[str, str]] = {}

_INDUSTRY_PROTOTYPE_MAP: dict[str, str] = {
    "银行": "bank",
    "电力": "high_dividend",
    "水务": "high_dividend",
    "燃气": "high_dividend",
    "高速公路": "high_dividend",
    "港口": "high_dividend",
    "软件服务": "growth_tech",
    "软件开发": "growth_tech",
    "互联网服务": "growth_tech",
    "通信设备": "growth_tech",
}

_INDUSTRY_V2_UNIMPLEMENTED: dict[str, str] = {
    "保险": "保险",
    "国防军工": "军工",
    "军工": "军工",
}

_INDUSTRY_METHODOLOGY_GAP: dict[str, str] = {
    "保险": "专用估值方法论（内含价值 EV/NBV 模型）暂缺",
    "军工": "专用估值方法论（在手订单驱动 + 资产重估模型）暂缺",
}

_DECISION_BAN = "通用方法得出的低估/高估不应用于买卖决策"

_IMPLEMENTED_PROTOTYPES = frozenset(
    {
        "bank",
        "high_dividend",
        "value_growth",
        "growth_manufacturing",
        "cashflow_ad_cycle",
        "defense_orders",
        "insurance",
        "growth_tech",
    }
)

_PROTOTYPE_METHODS: dict[str, list[str]] = {
    "bank": [
        "pb",
        "residual_income",
        "ddm",
        "two_stage_ddm",
        "graham_number",
        "altman_z",
        "pb_relative",
        "value_trap",
    ],
    "high_dividend": [
        "ddm",
        "two_stage_ddm",
        "epv",
        "owner_earnings",
        "graham_number",
        "altman_z",
        "value_trap",
    ],
    "value_growth": [
        "dcf",
        "epv",
        "owner_earnings",
        "graham_formula",
        "ev_ebitda",
        "pe_relative",
        "piotroski_f",
        "beneish_m",
        "value_trap",
    ],
    "growth_manufacturing": [
        "scenario_dcf",
        "altman_z",
        "piotroski_f",
        "value_trap",
    ],
    "cashflow_ad_cycle": [
        "cyclical_fcf",
        "cyclical_pe",
        "altman_z",
        "value_trap",
    ],
    "defense_orders": [
        "defense_orders",
        "altman_z",
        "value_trap",
    ],
    "insurance": [
        "insurance_ev",
        "altman_z",
        "value_trap",
    ],
    "growth_tech": [
        "peg",
        "garp",
        "rule_of_40",
        "ev_ebitda",
        "dcf",
        "piotroski_f",
        "value_trap",
    ],
    "unknown": [
        "graham_number",
        "graham_formula",
        "epv",
        "altman_z",
        "value_trap",
    ],
}


@dataclass(frozen=True)
class HonestyGap:
    """已识别但专用方法暂缺时的诚实缺口（用于警告与压制）。"""

    label: str
    methodology_gap: str


def _compose_methodology_gap(base: str) -> str:
    if _DECISION_BAN in base:
        return base
    return f"{base}；{_DECISION_BAN}"


def describe_unimplemented_industry(industry: str | None) -> tuple[str, str] | None:
    """返回已识别但尚无专用估值方法论的行业及其缺口说明（含决策禁止语义）。"""
    if not industry:
        return None

    for industry_substring, label in _INDUSTRY_V2_UNIMPLEMENTED.items():
        if industry_substring in industry:
            base = _INDUSTRY_METHODOLOGY_GAP.get(label, "专用估值方法论暂缺")
            return label, _compose_methodology_gap(base)

    return None


def describe_honesty_gap(code: str, industry: str | None) -> HonestyGap | None:
    """code 优先于行业：返回诚实缺口；未命中返回 None。

    已毕业到已实现 V2/V1 原型的 code（`_CODE_OVERRIDE`）不再套行业诚实层，
    避免中船等军工样本被「军工行业暂缺」二次压制。
    """
    code_entry = _CODE_V2_HONESTY.get(code)
    if code_entry is not None:
        label, base = code_entry
        return HonestyGap(label=label, methodology_gap=_compose_methodology_gap(base))

    override = _CODE_OVERRIDE.get(code)
    if override is not None and override in _IMPLEMENTED_PROTOTYPES:
        return None

    industry_detail = describe_unimplemented_industry(industry)
    if industry_detail is None:
        return None
    label, gap = industry_detail
    return HonestyGap(label=label, methodology_gap=gap)


def is_implemented_prototype(prototype: str) -> bool:
    return prototype in _IMPLEMENTED_PROTOTYPES


class PrototypeRouter:
    """V1 原型路由：硬编码覆盖、行业映射与财务特征启发。"""

    def route(self, stock: StockData, override: str | None = None) -> tuple[str, list[str]]:
        if override in _PROTOTYPE_METHODS:
            stock.proto = override
            return override, list(_PROTOTYPE_METHODS[override])

        prototype = self._classify(stock)
        stock.proto = prototype
        return prototype, list(_PROTOTYPE_METHODS[prototype])

    def _classify(self, stock: StockData) -> str:
        if stock.code in _CODE_V2_HONESTY:
            return "unknown"

        if stock.code in _CODE_OVERRIDE:
            return _CODE_OVERRIDE[stock.code]

        industry_prototype = self._classify_by_industry(stock.industry)
        if industry_prototype is not None:
            return industry_prototype

        if (
            stock.total_assets is None
            and stock.dividend_yield is None
            and stock.growth_rate is None
        ):
            return "unknown"

        if stock.total_assets and stock.total_liabilities:
            leverage = stock.total_liabilities / stock.total_assets
            if leverage > 0.85:
                return "bank"

        if stock.dividend_yield is not None and stock.dividend_yield > 4.0:
            if stock.growth_rate is not None and stock.growth_rate < 10:
                return "high_dividend"

        return "value_growth"

    def _classify_by_industry(self, industry: str | None) -> str | None:
        """根据 Tushare 简化行业名称映射原型；未收录时交由财务启发式。"""
        if not industry:
            return None

        for industry_substring, prototype in _INDUSTRY_PROTOTYPE_MAP.items():
            if industry_substring in industry:
                return prototype

        for industry_substring in _INDUSTRY_V2_UNIMPLEMENTED:
            if industry_substring in industry:
                return "unknown"

        return None
