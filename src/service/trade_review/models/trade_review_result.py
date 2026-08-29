"""交易复盘结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Badcase:
    """一次通过 Checklist 但产生显著亏损的已实现交易。"""

    code: str
    checklist_id: int
    return_rate: float
    quantity: int
    confrontation_id: int | None = None
    declare_stance: str | None = None


@dataclass(frozen=True)
class TradeReviewResult:
    """严格由确定性 FIFO 配对得到的复盘汇总。"""

    win_rate: float | None
    avg_return: float | None
    total_trades: int
    open_positions: int
    badcase_list: list[Badcase] = field(default_factory=list)
    checklist_data_available: bool = False
    warnings: list[str] = field(default_factory=list)
    badcase_summary: list[str] = field(default_factory=list)
