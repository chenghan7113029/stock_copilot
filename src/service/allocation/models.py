"""配置执行器的数据模型与域异常（纯数据，无 I/O、无网络）。

入参结构只包含政策与快照的**原始字段**：快照派生字段
（`deployment.gap_to_target` / `deployment.monthly_amount`）不出现在任何 dataclass 上，
因此结构上不可能成为输入（design R1：结果必须由政策与原始市值重算）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from common.exceptions import StockCopilotError


class AllocationError(StockCopilotError):
    """配置执行器域异常根。"""


class AllocationConfigError(AllocationError):
    """政策/快照缺键、类型错、YAML 解析失败（CLI 退出码 1）。"""


class AllocationStaleError(AllocationError):
    """快照过期或晚于计算日（CLI 退出码 2，R7 唯一硬门禁）。"""


@dataclass(frozen=True)
class IpsPolicy:
    """`config/ips.yaml` 中执行器用到的政策字段（政策唯一真源）。

    # 口径治理索引：CAN-ALLOC-001…005（真源仍是本文件对应的 YAML 行）
    """

    target_equity: Decimal
    target_fixed_income: Decimal
    target_cash: Decimal
    start_month: int
    horizon_months: int
    target_date: date
    execution_day: str
    skip_if_equity_above: Decimal
    trial_ratio: Decimal
    equity_cap: Decimal
    rebalance_band: Decimal
    cash_floor: Decimal
    stale_days: int


@dataclass(frozen=True)
class Snapshot:
    """`config/ips.local.yaml` 中执行器用到的快照字段（只读，不回写）。"""

    pool_total: Decimal
    current_equity: Decimal
    current_fixed_income: Decimal
    current_cash: Decimal
    holdings_market_value: Decimal
    holdings_as_of: date


@dataclass(frozen=True)
class PlanInput:
    """执行器唯一入参组合：政策 + 快照（不含任何派生金额）。"""

    policy: IpsPolicy
    snapshot: Snapshot


@dataclass(frozen=True)
class AmountDecision:
    """当月权益买入额的判定结果（状态机命中项 + 确定性理由文本）。"""

    equity_amount: Decimal
    state: str
    reason: str
    deferred: bool = False
    cap_warning: str | None = None


@dataclass(frozen=True)
class CategoryAllocation:
    """类别分配的一行（只给类别与金额，不给代码）。"""

    bucket: str
    label: str
    amount: Decimal


@dataclass(frozen=True)
class RebalanceHint:
    """单桶再平衡提示（只提示，不产调仓金额）。"""

    bucket: str
    label: str
    current: Decimal
    target: Decimal
    deviation: Decimal
    direction: str
    message: str


@dataclass(frozen=True)
class CashHint:
    """现金下限提示（只提示，不改当月权益买入额）。"""

    triggered: bool
    cash_market_value: Decimal
    floor_amount: Decimal
    shortfall: Decimal
    message: str


@dataclass(frozen=True)
class DeferDecision:
    """顺延判定（权益超限则当月不买；超 R1 上限只追加提示）。"""

    deferred: bool
    reason: str | None
    cap_warning: str | None


@dataclass(frozen=True)
class StaleInfo:
    """时效判定结果（未过期才会出现在指令里）。"""

    days: int
    threshold: int


@dataclass(frozen=True)
class PlanEcho:
    """回显全部公式输入，供人工核对「与 ips 一致」。"""

    target_equity: Decimal
    target_fixed_income: Decimal
    target_cash: Decimal
    pool_total: Decimal
    holdings_market_value: Decimal
    current_equity: Decimal
    current_fixed_income: Decimal
    current_cash: Decimal
    horizon_months: int
    target_date: date
    start_month: int
    first_dca_month: date
    migration_month: date
    execution_day_rule: str
    skip_if_equity_above: Decimal
    equity_cap: Decimal
    rebalance_band: Decimal
    cash_floor: Decimal
    stale_days: int
    rounding_rule: str
    as_of_calc: date
    holdings_as_of: date


@dataclass(frozen=True)
class AllocationPlan:
    """一条完整工单（人类可读文本与 `--json` 同构）。"""

    as_of_calc: date
    execution_month: date
    execution_day: date
    gap: Decimal
    remaining_months: int
    equity_amount: Decimal
    categories: tuple[CategoryAllocation, ...]
    defer: DeferDecision
    rebalance_hints: tuple[RebalanceHint, ...]
    cash_hint: CashHint
    stale: StaleInfo
    reasons: tuple[str, ...]
    echo: PlanEcho
