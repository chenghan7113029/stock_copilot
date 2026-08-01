"""结构化决策清单的输入与校验结果模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChecklistSubmission:
    """用户一次买入或卖出意图的结构化陈述。"""

    code: str
    action: str | None
    value_reasons: list[str]
    tech_alignment: str | None
    sentiment_position: str | None
    stop_loss_price: float | None
    take_profit_price: float | None


@dataclass(frozen=True)
class ChecklistValidationResult:
    """确定性规则校验结果。"""

    passed: bool
    rejection_reasons: list[str]
