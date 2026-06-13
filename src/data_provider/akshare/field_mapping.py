"""AKShare 列名 → StockData 字段映射。

来源：ref/valueinvest/valueinvest/data/fetcher/akshare.py
原路径：valueinvest/valueinvest/data/fetcher/akshare.py
许可证：参见 ref/valueinvest/LICENSE（MIT 兼容）

本文件对原项目中分散在各 fetch_* 方法里的列名映射进行集中整理，
便于维护和交叉校验。所有映射均基于新浪财经（stock_financial_report_sina）
和东方财富（stock_individual_info_em / stock_financial_analysis_indicator）API。
"""

from __future__ import annotations

# ── stock_individual_info_em  行情基础信息 ────────────────────────────────────
# 返回格式：item / value 两列 DataFrame，以字典使用
QUOTE_INFO_FIELD_MAP: dict[str, str] = {
    "最新": "current_price",
    "总股本": "shares_outstanding",
    "总市值": "market_cap",
    "股票简称": "name",
}

# ── stock_financial_report_sina 资产负债表 ────────────────────────────────────
BALANCE_SHEET_FIELD_MAP: dict[str, str] = {
    "流动资产合计": "current_assets",
    "流动负债合计": "_current_liabilities",    # 内部临时字段，用于计算 net_working_capital
    "负债合计": "total_liabilities",
    "资产总计": "total_assets",
    "固定资产净额": "net_fixed_assets",
    "固定资产合计": "net_fixed_assets",        # fallback
    "短期借款": "short_term_debt",
    "长期借款": "long_term_debt",
    "应收账款": "accounts_receivable",
    "存货": "inventory",
    "应付账款": "accounts_payable",
    # 归母权益（多种表述，以精确匹配为主，见 fetcher 处理逻辑）
    "归属于母公司股东权益合计": "shareholder_equity",
    "归属于母公司股东的权益": "shareholder_equity",
}

# ── stock_financial_report_sina 利润表 ────────────────────────────────────────
INCOME_STMT_FIELD_MAP: dict[str, str] = {
    "营业收入": "revenue",
    "营业总收入": "revenue",               # 部分行业使用此列名
    "归属于母公司所有者的净利润": "net_income",
    "净利润": "net_income",               # fallback
    "基本每股收益": "eps",
    "营业利润": "ebit",
    "利润总额": "_profit_before_tax",      # 内部临时字段，用于计算 tax_rate
    "所得税费用": "_income_tax",           # 内部临时字段
    "利息支出": "interest_expense",
    "利息费用": "interest_expense",
}

# ── stock_financial_report_sina 现金流量表 ────────────────────────────────────
CASHFLOW_FIELD_MAP: dict[str, str] = {
    "经营活动产生的现金流量净额": "_operating_cf",   # 内部临时字段，用于计算 fcf
    "购建固定资产、无形资产和其他长期资产支付的现金": "capex",
    "资本支出": "capex",                            # fallback
    "固定资产折旧、油气资产折耗、生产性生物资产折旧": "depreciation",
    "固定资产折旧": "depreciation",                 # fallback
    "折旧与摊销": "depreciation",                   # fallback
}

# ── stock_financial_analysis_indicator 财务指标 ───────────────────────────────
FINANCIAL_INDICATOR_FIELD_MAP: dict[str, str] = {
    "净资产收益率": "roe",
    "每股净资产": "bvps",
    "每股收益": "eps",                             # 与利润表 eps 重叠时取更精确值
}

# ── stock_dividend_cn 分红数据 ────────────────────────────────────────────────
DIVIDEND_FIELD_MAP: dict[str, str] = {
    "分红金额": "_dividend_amount_per_10_shares",  # 每 10 股分红额，需 /10 转为每股
}
