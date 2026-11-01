"""龙虎榜确定性分析结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ActiveLevel(Enum):
    NOT_LISTED = "未上榜"
    OCCASIONAL = "偶发"
    ACTIVE = "活跃"


class NetAmountLevel(Enum):
    LARGE_NET_BUY = "大额净买入"
    LARGE_NET_SELL = "大额净卖出"
    NEUTRAL = "中性"


class InstParticipation(Enum):
    INST_BUY = "机构买入"
    INST_SELL = "机构卖出"
    NO_SEAT = "无机构席位"


@dataclass
class TopListResult:
    """龙虎榜观察维度结果（纯确定性，不参与信号融合与 LLM）。"""

    code: str
    appearance_count: int = 0  # 窗口内去重后的上榜交易日数
    active_level: ActiveLevel = ActiveLevel.NOT_LISTED
    latest_trade_date: str | None = None
    latest_net_amount: float | None = None  # 主导上榜事件净买额（元）
    latest_net_amount_level: NetAmountLevel | None = None
    latest_event_count: int | None = None  # 最近上榜日的上榜事件数（多 reason）
    latest_reasons: list[str] = field(default_factory=list)
    inst_net_buy: float | None = None  # 机构席位净买额（元）
    inst_participation: InstParticipation | None = None
    reason_categories: list[str] = field(default_factory=list)
    coverage_trade_days: int = 0
    coverage_start: str | None = None
    coverage_end: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
