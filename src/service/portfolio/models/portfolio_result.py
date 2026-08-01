"""严格离线组合分析的确定性结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PositionSummary:
    """按股票代码汇总的当前持仓。"""

    code: str
    quantity: int
    market_value: float
    weight: float | None
    industry: str | None
    price_as_of: datetime | None


@dataclass
class PortfolioAnalysisResult:
    """组合集中度与行业暴露度粗估结果。"""

    total_value: float
    positions: list[PositionSummary] = field(default_factory=list)
    single_stock_weight: dict[str, float] = field(default_factory=dict)
    top_n_concentration: dict[int, float] = field(default_factory=dict)
    industry_exposure: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
