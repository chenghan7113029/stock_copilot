"""Baostock 列名 → StockData 字段映射。

来源：ref/daily_stock_analysis/data_provider/baostock_fetcher.py
原路径：daily_stock_analysis/data_provider/baostock_fetcher.py
许可证：参见 ref/daily_stock_analysis/LICENSE

Baostock 提供季频财务数据（query_profit/operation/growth/balance/cash_flow），
以及日线行情（query_history_k_data_plus）。
本文件集中整理列名 → StockData 字段的映射关系。
"""

from __future__ import annotations

# ── Baostock 代码格式规则 ─────────────────────────────────────────────────────
# sh.600519 → SH；sz.000001 → SZ
# 北交所（8xxxxx）Baostock 不支持

EXCHANGE_PREFIX_MAP: dict[str, str] = {
    "sh": "SH",
    "sz": "SZ",
}

# ── query_profit_data 盈利能力（季频）────────────────────────────────────────
PROFIT_DATA_FIELD_MAP: dict[str, str] = {
    "roeAvg": "roe",             # 净资产收益率（平均）%
    "epsTTM": "eps",             # 每股收益 TTM
    "MBRevenue": "revenue",      # 主营业务收入（元）
    "netProfit": "_quarterly_net_profit",  # 单季/累计净利润（内部字段，勿直接当年度净利）
    "grossProfitMargin": "operating_margin",  # 毛利率（%），作为营业利润率近似
}

# ── query_balance_data 偿债能力（季频）───────────────────────────────────────
BALANCE_DATA_FIELD_MAP: dict[str, str] = {
    "currentRatio": "_current_ratio",    # 流动比率（用于推导 NWC，内部字段）
    "quickRatio": "_quick_ratio",
    "cashRatio": "_cash_ratio",
    "YOYLiability": "_yoy_liability",    # 仅供调试
    "liabilityToAsset": "_liability_ratio",  # 资产负债率，用于推导总负债
    "assetToEquity": "_equity_multiplier",
}

# ── query_growth_data 成长能力（季频）────────────────────────────────────────
GROWTH_DATA_FIELD_MAP: dict[str, str] = {
    "YOYEquity": "_yoy_equity",
    "YOYAsset": "_yoy_asset",
    "YOYNI": "growth_rate",       # 净利润同比增长率（%）
    "YOYEPSBasic": "_yoy_eps",
    "YOYPNI": "_yoy_net_income",  # 归母净利润同比增长率
}

# ── query_cash_flow_data 现金流（季频）───────────────────────────────────────
CASHFLOW_DATA_FIELD_MAP: dict[str, str] = {
    "operCashTTM": "_operating_cashflow_ttm",  # 经营现金流 TTM（内部，经 FCF 推导链写入 fcf）
    "CFOToOR": "_cfo_to_or",
    "CFOToNP": "_cfo_to_np",
    "CFOToGr": "_cfo_to_gr",
}

# ── query_history_k_data_plus 日线行情 ────────────────────────────────────────
# 返回字段：date, open, high, low, close, volume, amount, pctChg
KDATA_FIELD_MAP: dict[str, str] = {
    "close": "current_price",
}
