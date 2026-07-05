"""统一股票估值数据模型。

覆盖 MRD §7 V1 三原型（银行 / 高股息·类债 / 高质量价值成长）所需字段。
历史 PE/PB 序列字段已预留；data_provider 侧获取推迟到独立 change。

字段缺失语义：None 表示缺失（区别于真实的 0），下游估值方法据此标注不可靠。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class StockData:
    """A 股股票估值所需的统一数据结构。

    分组：
    - 基础标识
    - 基础行情
    - 每股指标
    - 盈利能力
    - 现金流
    - 资产负债
    - 分红
    - 质量与风险明细（Altman-Z / Piotroski-F / Beneish-M 所需输入）
    - 元数据（来源、时效、缺失字段）
    """

    # ── 基础标识 ──────────────────────────────────────────────────────────────
    code: str = ""                          # 标准化股票代码（如 "600519"）
    name: str = ""                          # 股票简称
    exchange: str = ""                      # 交易所：SH / SZ / BJ
    industry: str = ""                      # 行业（如「银行」「商业银行」）

    # ── 基础行情 ──────────────────────────────────────────────────────────────
    current_price: Optional[float] = None  # 当前价（元）
    shares_outstanding: Optional[float] = None  # 总股本（股）
    market_cap: Optional[float] = None     # 总市值（元）

    # ── 每股指标 ──────────────────────────────────────────────────────────────
    eps: Optional[float] = None            # 基本每股收益（元）
    bvps: Optional[float] = None           # 每股净资产（元）
    dividend_per_share: Optional[float] = None  # 每股分红（元，最近一期）

    # ── 盈利能力 ──────────────────────────────────────────────────────────────
    revenue: Optional[float] = None        # 营业收入（元）
    net_income: Optional[float] = None     # 归母净利润（元）
    ebit: Optional[float] = None           # 息税前利润（元）
    ebitda: Optional[float] = None         # 息税折旧摊销前利润（元）
    operating_margin: Optional[float] = None  # 营业利润率（%）
    roe: Optional[float] = None            # 净资产收益率（%）
    roic: Optional[float] = None           # 投入资本回报率（%）
    tax_rate: Optional[float] = None       # 有效税率（%）
    pe_ratio: Optional[float] = None       # 市盈率（TTM）
    pb_ratio: Optional[float] = None       # 市净率

    # ── 现金流 ────────────────────────────────────────────────────────────────
    fcf: Optional[float] = None            # 自由现金流（元）
    capex: Optional[float] = None          # 资本开支（元）
    depreciation: Optional[float] = None  # 折旧摊销（元）

    # ── 资产负债 ──────────────────────────────────────────────────────────────
    total_assets: Optional[float] = None   # 总资产（元）
    total_liabilities: Optional[float] = None  # 总负债（元）
    current_assets: Optional[float] = None     # 流动资产（元）
    current_liabilities: Optional[float] = None  # 流动负债（元）
    shareholder_equity: Optional[float] = None   # 归母股东权益（元）
    net_debt: Optional[float] = None       # 净负债（元）
    cash: Optional[float] = None           # 货币资金（元，用于推导 net_debt）
    short_term_debt: Optional[float] = None    # 短期借款（元）
    long_term_debt: Optional[float] = None     # 长期借款（元）
    interest_expense: Optional[float] = None   # 利息费用（元）
    net_working_capital: Optional[float] = None  # 净营运资本（元）
    net_fixed_assets: Optional[float] = None    # 净固定资产（元）
    accounts_receivable: Optional[float] = None  # 应收账款（元）
    inventory: Optional[float] = None           # 存货（元）
    accounts_payable: Optional[float] = None     # 应付账款（元）

    # ── 分红 ──────────────────────────────────────────────────────────────────
    dividend_yield: Optional[float] = None      # 股息率（%）
    dividend_payout_ratio: Optional[float] = None  # 派息率（%）
    dividend_growth_rate: Optional[float] = None    # 近期股息复合增长率（%）

    # ── 质量与风险明细（用于 Altman-Z / Piotroski-F / Beneish-M）─────────────
    # Piotroski 需要上一期对比值
    prior_roa: Optional[float] = None
    prior_debt_ratio: Optional[float] = None
    prior_current_ratio: Optional[float] = None
    prior_shares_outstanding: Optional[float] = None
    prior_gross_margin: Optional[float] = None
    prior_asset_turnover: Optional[float] = None
    # Beneish M-Score 组件
    days_sales_receivable: Optional[float] = None  # 应收账款天数
    gross_margin_index: Optional[float] = None
    asset_quality_index: Optional[float] = None
    sales_growth_index: Optional[float] = None
    depreciation_index: Optional[float] = None
    selling_expense_index: Optional[float] = None
    leverage_index: Optional[float] = None
    accruals: Optional[float] = None
    # SBC（股权激励摊销，通常 A 股暂无）
    sbc: Optional[float] = None
    shares_issued: Optional[float] = None
    shares_repurchased: Optional[float] = None
    # 银行专用（V1 完备性 TODO，当前方法未必用到）
    net_interest_margin: Optional[float] = None    # 净息差（%）
    npl_ratio: Optional[float] = None              # 不良贷款率（%）
    provision_coverage: Optional[float] = None     # 拨备覆盖率（%）

    # ── 增长率 ────────────────────────────────────────────────────────────────
    growth_rate: Optional[float] = None    # EPS/净利润近期年化增长率（%）

    # ── 历史估值序列（相对估值方法用，可空）────────────────────────────────────
    historical_pe: Optional[List[float]] = None  # 历史滚动 PE 序列（降序）
    historical_pb: Optional[List[float]] = None  # 历史滚动 PB 序列（降序）

    # ── 元数据 ────────────────────────────────────────────────────────────────
    # 估值原型（由 PrototypeRouter.route() 写入，供 AssumptionProvider 查 β/floor）
    proto: str = ""
    # 每个字段实际命中的数据源名称
    field_sources: Dict[str, str] = field(default_factory=dict)
    # 行情数据时间戳
    data_timestamp: Optional[datetime] = None
    # 财报报告期
    fundamental_report_date: Optional[date] = None
    # 缺失字段列表（None 的字段均在此列出，下游据此判断方法可靠性）
    missing_fields: List[str] = field(default_factory=list)

    def mark_missing(self, field_name: str) -> None:
        """将字段标记为缺失（设为 None 并加入 missing_fields 列表）。"""
        setattr(self, field_name, None)
        if field_name not in self.missing_fields:
            self.missing_fields.append(field_name)

    def is_missing(self, field_name: str) -> bool:
        """检查字段是否缺失。"""
        return getattr(self, field_name, None) is None

    def set_field(self, field_name: str, value: Optional[float], source: str) -> None:
        """设置字段值并记录来源（仅当当前为 None 时才写入，高优先级先写）。"""
        if getattr(self, field_name, None) is None and value is not None:
            setattr(self, field_name, value)
            self.field_sources[field_name] = source
            if field_name in self.missing_fields:
                self.missing_fields.remove(field_name)

    def override_field(self, field_name: str, value: Optional[float], source: str) -> None:
        """强制写入字段（低优先级源覆盖高优先级估算值时使用）。"""
        if value is not None:
            setattr(self, field_name, value)
            self.field_sources[field_name] = source
            if field_name in self.missing_fields:
                self.missing_fields.remove(field_name)
