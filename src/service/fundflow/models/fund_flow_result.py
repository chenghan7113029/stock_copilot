"""个股资金面确定性分析结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LeverageDirection(Enum):
    ADD_LEVERAGE = "加杠杆"
    DELEVERAGE = "去杠杆"
    STABLE = "平稳"


@dataclass
class FundFlowResult:
    code: str
    margin_balance_change_pct: float | None = None  # 两融余额近 5 日变化率（%）
    short_balance_change_pct: float | None = None  # 融券余额近 5 日变化率（%）
    main_net_inflow_5d: float | None = None  # 主力资金近 5 日净流入（万元）
    leverage_direction: LeverageDirection | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
