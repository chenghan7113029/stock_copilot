"""治理事件面确定性分析结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EventResult:
    code: str
    holder_net_sell_90d: float | None = None  # 近 90 日净减持（股；正=净减持，负=净增持）
    repurchase_active: bool = False  # 近 90 日回购实施/完成
    upcoming_unlock_30d: float | None = None  # 未来 30 日解禁占比（%）
    pledge_ratio: float | None = None  # 最新质押比例（%）
    block_trade_discount: float | None = None  # 近 30 日大宗平均折价（%；正=折价，负=溢价）
    northbound_net_inflow_5d: float | None = None  # 北向近 5 日净流入（市场级）
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
