"""ORM 模型：原始股票数据快照表。

唯一键：(code, source, report_period)
- 每个数据源的数据独立成行（来源维度存储）
- report_period 对于行情数据使用 fetch_date（YYYY-MM-DD）
- 对于财报数据使用财报报告期（如 2023-12-31）
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from dao.engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StockSnapshot(Base):
    """原始股票数据快照。

    每行对应一个 (code, source, report_period) 的数据快照，
    多个数据源彼此独立，不互相覆盖。
    """

    __tablename__ = "stock_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── 标识 ──────────────────────────────────────────────────────────────────
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(50))
    exchange: Mapped[str | None] = mapped_column(String(5))
    industry: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    # 报告期：财报用 '20231231'，行情快照用 fetch date 'YYYYMMDD'
    report_period: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── 时效 ──────────────────────────────────────────────────────────────────
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime)

    # ── 行情 ──────────────────────────────────────────────────────────────────
    current_price: Mapped[float | None] = mapped_column(Float)
    shares_outstanding: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)

    # ── 每股指标 ──────────────────────────────────────────────────────────────
    eps: Mapped[float | None] = mapped_column(Float)
    bvps: Mapped[float | None] = mapped_column(Float)
    dividend_per_share: Mapped[float | None] = mapped_column(Float)

    # ── 盈利能力 ──────────────────────────────────────────────────────────────
    revenue: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)
    ebit: Mapped[float | None] = mapped_column(Float)
    operating_margin: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    roic: Mapped[float | None] = mapped_column(Float)
    tax_rate: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    pb_ratio: Mapped[float | None] = mapped_column(Float)

    # ── 现金流 ────────────────────────────────────────────────────────────────
    fcf: Mapped[float | None] = mapped_column(Float)
    capex: Mapped[float | None] = mapped_column(Float)
    depreciation: Mapped[float | None] = mapped_column(Float)

    # ── 资产负债 ──────────────────────────────────────────────────────────────
    total_assets: Mapped[float | None] = mapped_column(Float)
    total_liabilities: Mapped[float | None] = mapped_column(Float)
    current_assets: Mapped[float | None] = mapped_column(Float)
    current_liabilities: Mapped[float | None] = mapped_column(Float)
    shareholder_equity: Mapped[float | None] = mapped_column(Float)
    net_debt: Mapped[float | None] = mapped_column(Float)
    short_term_debt: Mapped[float | None] = mapped_column(Float)
    long_term_debt: Mapped[float | None] = mapped_column(Float)
    interest_expense: Mapped[float | None] = mapped_column(Float)
    net_working_capital: Mapped[float | None] = mapped_column(Float)
    net_fixed_assets: Mapped[float | None] = mapped_column(Float)
    accounts_receivable: Mapped[float | None] = mapped_column(Float)
    inventory: Mapped[float | None] = mapped_column(Float)
    accounts_payable: Mapped[float | None] = mapped_column(Float)

    # ── 分红 ──────────────────────────────────────────────────────────────────
    dividend_yield: Mapped[float | None] = mapped_column(Float)
    dividend_payout_ratio: Mapped[float | None] = mapped_column(Float)
    dividend_growth_rate: Mapped[float | None] = mapped_column(Float)

    # ── 成长 ──────────────────────────────────────────────────────────────────
    growth_rate: Mapped[float | None] = mapped_column(Float)

    # ── 同比 prior 字段（Piotroski / Beneish）──────────────────────────────────
    prior_roa: Mapped[float | None] = mapped_column(Float)
    prior_debt_ratio: Mapped[float | None] = mapped_column(Float)
    prior_current_ratio: Mapped[float | None] = mapped_column(Float)
    prior_shares_outstanding: Mapped[float | None] = mapped_column(Float)
    prior_gross_margin: Mapped[float | None] = mapped_column(Float)
    prior_asset_turnover: Mapped[float | None] = mapped_column(Float)

    # ── 银行专项指标 ──────────────────────────────────────────────────────────
    net_interest_margin: Mapped[float | None] = mapped_column(Float)
    npl_ratio: Mapped[float | None] = mapped_column(Float)
    provision_coverage: Mapped[float | None] = mapped_column(Float)

    # ── 历史估值序列（JSON 数组）──────────────────────────────────────────────
    historical_pe_json: Mapped[str | None] = mapped_column(Text)
    historical_pb_json: Mapped[str | None] = mapped_column(Text)

    # ── 约束 ──────────────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("code", "source", "report_period", name="uq_code_source_period"),
        Index("ix_code_source", "code", "source"),
    )

    def __repr__(self) -> str:
        return f"<StockSnapshot code={self.code} source={self.source} period={self.report_period}>"


class Kline(Base):
    """日 K 线 OHLCV 缓存表。"""

    __tablename__ = "kline"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_kline_code_date", "code", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"<Kline code={self.code} date={self.trade_date}>"


class MarketSentimentSnapshot(Base):
    """按交易日缓存的全市场情绪快照。"""

    __tablename__ = "market_sentiment_snapshot"

    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    limit_up_count: Mapped[int | None] = mapped_column(Integer)
    limit_down_count: Mapped[int | None] = mapped_column(Integer)
    up_count: Mapped[int | None] = mapped_column(Integer)
    down_count: Mapped[int | None] = mapped_column(Integer)
    margin_balance_change_pct: Mapped[float | None] = mapped_column(Float)
    turnover_percentile: Mapped[float | None] = mapped_column(Float)
    fear_greed_index: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<MarketSentimentSnapshot date={self.trade_date}>"


class ChipDistribution(Base):
    """东方财富口径的日度筹码分布缓存。"""

    __tablename__ = "chip_distribution"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    winner_ratio: Mapped[float | None] = mapped_column(Float)
    avg_cost: Mapped[float | None] = mapped_column(Float)
    concentration_90: Mapped[float | None] = mapped_column(Float)
    concentration_70: Mapped[float | None] = mapped_column(Float)
    cost_90_low: Mapped[float | None] = mapped_column(Float)
    cost_90_high: Mapped[float | None] = mapped_column(Float)
    cost_70_low: Mapped[float | None] = mapped_column(Float)
    cost_70_high: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_chip_distribution_code_date", "code", "trade_date"),)

    def __repr__(self) -> str:
        return f"<ChipDistribution code={self.code} date={self.trade_date}>"


class LLMNarrateCache(Base):
    """LLM narrate() 幂等缓存。"""

    __tablename__ = "llm_narrate_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<LLMNarrateCache key={self.cache_key[:12]}...>"


class PrototypeOverrideRecord(Base):
    """用户为股票设置的当前有效估值原型覆盖。"""

    __tablename__ = "prototype_overrides"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    prototype: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PrototypeOverrideRecord code={self.code} prototype={self.prototype}>"


class ChecklistRecord(Base):
    """买卖意图 Checklist 的审计留痕，包含合规与被拒绝的提交。"""

    __tablename__ = "checklist_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    action: Mapped[str | None] = mapped_column(String(10))
    value_reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    tech_alignment: Mapped[str | None] = mapped_column(Text)
    sentiment_position: Mapped[str | None] = mapped_column(Text)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    take_profit_price: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(nullable=False)
    rejection_reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    confrontation_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ChecklistRecord code={self.code} passed={self.passed}>"


class PositionRecord(Base):
    """单只股票的一条当前持仓记录，用于入场检查的无仓位视角。"""

    __tablename__ = "position_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PositionRecord code={self.code} shares={self.shares}>"


class TradeRecord(Base):
    """用户手工录入的买卖交易记录；checklist_id / confrontation_id 为软引用。"""

    __tablename__ = "trade_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(4), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    checklist_id: Mapped[int | None] = mapped_column(Integer)
    confrontation_id: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_trade_records_code_date", "code", "trade_date"),)

    def __repr__(self) -> str:
        return f"<TradeRecord code={self.code} action={self.action} quantity={self.quantity}>"


class ConfrontationRecord(Base):
    """红蓝对抗会话：证据分桶 + 可选 LLM 互驳叙事 + 用户 declare。"""

    __tablename__ = "confrontation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    narrative_json: Mapped[str | None] = mapped_column(Text)
    narrate_status: Mapped[str] = mapped_column(String(20), nullable=False)
    declare_json: Mapped[str | None] = mapped_column(Text)
    declare_status: Mapped[str | None] = mapped_column(String(20))
    declared_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ConfrontationRecord id={self.id} code={self.code} "
            f"status={self.narrate_status}>"
        )

