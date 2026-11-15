"""配置执行器：把政策 + 快照变成「当月买多少、买什么类别」的纯算术指令。

零网络、零状态、全链路确定性：`compute_plan` 是纯函数（同输入逐字段同输出），
理由文本由固定模板 + 回显数值生成（design R10 / A 节）。
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from service.allocation.models import (
    AllocationPlan,
    AllocationStaleError,
    AmountDecision,
    CashHint,
    CategoryAllocation,
    DeferDecision,
    IpsPolicy,
    PlanEcho,
    RebalanceHint,
    Snapshot,
    StaleInfo,
)

_THURSDAY = 3  # date.weekday()：周一 = 0
_ONE = Decimal("1")
_CENT = Decimal("0.01")

ROUNDING_RULE = "四舍五入到整数元（.5 向上，ROUND_HALF_UP；Q1 待 Owner 确认）"

# 状态机命中项（确定性枚举，便于单测与排查）
STATE_NOT_STARTED = "not_started"
STATE_ENDED = "ended"
STATE_MIGRATION = "migration"
STATE_DEFERRED = "deferred"
STATE_NON_POSITIVE_GAP = "non_positive_gap"
STATE_FINAL_MONTH = "final_month"
STATE_REGULAR = "regular"

_BUCKET_LABELS = {
    "equity": "权益（宽基 ETF）",
    "fixed_income": "固收迁移",
    "cash": "现金（当月新增）",
}


# ── 文本格式（确定性模板）──────────────────────────────────────────────


def _month_text(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"


def _money(value: Decimal) -> str:
    """金额文本：整数元不带小数尾，非整数保留精度；均加千分位。"""
    if value == value.to_integral_value():
        return f"{int(value):,d}"
    return f"{value.normalize():,f}"


def _scaled_text(value: Decimal) -> str:
    """比例 → 百分数数字部分（最多两位小数，去掉尾零）。"""
    text = format((value * 100).normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _pct(value: Decimal) -> str:
    return f"{_scaled_text(value)}%"


def _pp(value: Decimal) -> str:
    return f"{_scaled_text(abs(value))}pp"


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


# ── 月份与执行日（R2 / R3）───────────────────────────────────────────────────


def _month_of(value: date) -> date:
    """把任意日期折成该月 1 日（月份为「年月」粒度）。"""
    return date(value.year, value.month, 1)


def _add_months(month: date, delta: int) -> date:
    index = month.year * 12 + (month.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


def _last_thursday(year: int, month: int) -> date:
    """当月最后一个周四：从月末向前回退到周四。"""
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - _THURSDAY) % 7)


def resolve_execution_month_day(as_of_calc: date) -> tuple[date, date]:
    """计算日当日或之后最近的「当月最后一个周四」→ (执行月首日, 执行日)。

    例：2026-11-15 → (2026-11-01, 2026-11-26)；2026-12-01 → (2026-12-01, 2026-12-31)；
    计算日恰为执行日当天则取当天。不接行情、不做节假日顺延（KQ-1 未答复）。
    """
    day = _last_thursday(as_of_calc.year, as_of_calc.month)
    if day < as_of_calc:
        next_month = _add_months(_month_of(as_of_calc), 1)
        day = _last_thursday(next_month.year, next_month.month)
    return _month_of(day), day


def _target_month(policy: IpsPolicy) -> date:
    return _month_of(policy.target_date)


def _first_dca_month(policy: IpsPolicy) -> date:
    """首个定投月 = 目标月 − (horizon_months − 1) 个月。"""
    return _add_months(_target_month(policy), -(policy.horizon_months - 1))


def _migration_month(policy: IpsPolicy) -> date:
    """迁移月 = 首个定投月 − (start_month − 1) 个月。"""
    return _add_months(_first_dca_month(policy), -(policy.start_month - 1))


# ── 缺口、月数、金额（R3 / R4）───────────────────────────────────────────────


def compute_gap(policy: IpsPolicy, snapshot: Snapshot) -> Decimal:
    """权益缺口 = 目标权益比例 × 池总额 − 权益总市值（可为负）。"""
    return policy.target_equity * snapshot.pool_total - snapshot.holdings_market_value


def compute_remaining_months(policy: IpsPolicy, execution_month: date) -> int:
    """含端点月份数：max(执行月, 首个定投月) → 目标月；执行月晚于目标月为 0。"""
    target = _target_month(policy)
    start = max(execution_month, _first_dca_month(policy))
    if start > target:
        return 0
    return (target.year - start.year) * 12 + (target.month - start.month) + 1


def round_yuan(value: Decimal) -> Decimal:
    """金额取整：四舍五入到整数元，`.5` 向上（design A2；Q1 待确认）。"""
    return Decimal(str(value)).quantize(_ONE, rounding=ROUND_HALF_UP)


def decide_defer(policy: IpsPolicy, snapshot: Snapshot) -> DeferDecision:
    """权益占比 > `skip_if_equity_above` → 顺延；> `R1_equity_cap` 只追加提示。"""
    current = snapshot.current_equity
    if current <= policy.skip_if_equity_above:
        return DeferDecision(deferred=False, reason=None, cap_warning=None)

    reason = (
        f"顺延：权益占比 {_pct(current)} 高于顺延阈值 "
        f"{_pct(policy.skip_if_equity_above)}，当月不买入（不追高）"
    )
    cap_warning = None
    if current > policy.equity_cap:
        cap_warning = (
            f"权益超过 R1 上限 {_pct(policy.equity_cap)}（未经回测验证，仅提示，"
            f"不产减仓金额；当前 {_pct(current)}）"
        )
    return DeferDecision(deferred=True, reason=reason, cap_warning=cap_warning)


def compute_monthly_amount(
    policy: IpsPolicy,
    snapshot: Snapshot,
    execution_month: date,
    gap: Decimal,
    remaining_months: int,
) -> AmountDecision:
    """当月权益买入额：design「判定顺序」状态机，首个命中即止。"""
    target_month = _target_month(policy)
    migration_month = _migration_month(policy)
    first_dca_month = _first_dca_month(policy)

    if execution_month > target_month:
        return AmountDecision(
            equity_amount=Decimal("0"),
            state=STATE_ENDED,
            reason=(
                f"投放期已结束（执行月 {_month_text(execution_month)} 晚于目标月 "
                f"{_month_text(target_month)}），不再产出买入建议"
            ),
        )
    if execution_month < migration_month:
        return AmountDecision(
            equity_amount=Decimal("0"),
            state=STATE_NOT_STARTED,
            reason=(
                f"投放未开始：迁移月 {_month_text(migration_month)} 起才有指令"
                f"（首个定投月 {_month_text(first_dca_month)}）"
            ),
        )
    if execution_month == migration_month:
        return AmountDecision(
            equity_amount=Decimal("0"),
            state=STATE_MIGRATION,
            reason=(
                f"迁移月（{_month_text(migration_month)}），只做固收迁移；"
                f"定投自 {_month_text(first_dca_month)} 起"
            ),
        )

    defer = decide_defer(policy, snapshot)
    if defer.deferred:
        return AmountDecision(
            equity_amount=Decimal("0"),
            state=STATE_DEFERRED,
            reason=defer.reason or "顺延：权益占比高于顺延阈值，当月不买入",
            deferred=True,
            cap_warning=defer.cap_warning,
        )
    if gap <= 0:
        return AmountDecision(
            equity_amount=Decimal("0"),
            state=STATE_NON_POSITIVE_GAP,
            reason=f"缺口为负或零（{_money(gap)}），不卖出、不买入",
        )
    if execution_month == target_month:
        return AmountDecision(
            equity_amount=round_yuan(gap),
            state=STATE_FINAL_MONTH,
            reason=f"目标月补齐，投放期结束（缺口 {_money(gap)} 全额买入）",
        )

    months = Decimal(max(remaining_months, 1))
    quotient = (gap / months).quantize(_CENT, rounding=ROUND_HALF_UP)
    monthly = round_yuan(gap / months)
    return AmountDecision(
        equity_amount=monthly,
        state=STATE_REGULAR,
        reason=(
            f"常规月：缺口 {_money(gap)} ÷ 剩余 {months} 个月 = {_money(quotient)}，"
            f"取整到元 {_money(monthly)}"
        ),
    )


def allocate_categories(
    policy: IpsPolicy,
    snapshot: Snapshot,
    execution_month: date,
    equity_amount: Decimal,
) -> tuple[CategoryAllocation, ...]:
    """三桶类别与金额：权益只投宽基 ETF（不给代码），固收仅迁移月，现金新增 0。"""
    fixed_income_amount = Decimal("0")
    if execution_month == _migration_month(policy):
        fixed_income_amount = round_yuan(
            policy.target_fixed_income * snapshot.pool_total * policy.trial_ratio
        )
    return (
        CategoryAllocation("equity", _BUCKET_LABELS["equity"], equity_amount),
        CategoryAllocation("fixed_income", _BUCKET_LABELS["fixed_income"], fixed_income_amount),
        CategoryAllocation("cash", _BUCKET_LABELS["cash"], Decimal("0")),
    )


# ── 提示（R8 / R9：只提示，不改金额）──────────────────────────────────────────


def rebalance_hints(policy: IpsPolicy, snapshot: Snapshot) -> tuple[RebalanceHint, ...]:
    """三桶 |当前 − 目标| > 再平衡带 → 提示（不产调仓金额、不改当月买入额）。"""
    buckets = (
        ("equity", "权益", snapshot.current_equity, policy.target_equity),
        ("fixed_income", "固收", snapshot.current_fixed_income, policy.target_fixed_income),
        ("cash", "现金", snapshot.current_cash, policy.target_cash),
    )
    hints: list[RebalanceHint] = []
    for bucket, label, current, target in buckets:
        deviation = current - target
        if abs(deviation) <= policy.rebalance_band:
            continue
        direction = "高于" if deviation > 0 else "低于"
        hints.append(
            RebalanceHint(
                bucket=bucket,
                label=label,
                current=current,
                target=target,
                deviation=deviation,
                direction=direction,
                message=(
                    f"{label}{direction}目标 {_pp(deviation)}"
                    f"（当前 {_pct(current)} / 目标 {_pct(target)}，"
                    f"偏离超再平衡带 {_pp(policy.rebalance_band)}；仅提示，不自动调仓）"
                ),
            )
        )
    return tuple(hints)


def cash_floor_hint(policy: IpsPolicy, snapshot: Snapshot) -> CashHint:
    """现金市值 < `R7_cash_floor × pool` → 提示 + 补足金额（不改当月买入额）。"""
    cash_market_value = snapshot.current_cash * snapshot.pool_total
    floor_amount = policy.cash_floor * snapshot.pool_total
    shortfall = floor_amount - cash_market_value
    if shortfall > 0:
        return CashHint(
            triggered=True,
            cash_market_value=cash_market_value,
            floor_amount=floor_amount,
            shortfall=round_yuan(shortfall),
            message=(
                f"现金不足：现金市值 {_money(cash_market_value)}（占 {_pct(snapshot.current_cash)}）"
                f"低于下限 {_money(floor_amount)}（{_pct(policy.cash_floor)} × 池总额 "
                f"{_money(snapshot.pool_total)}），补足到下限需 {_money(round_yuan(shortfall))} 元；"
                "按 R7 应优先补现金、权益买入需人工确认（仅提示，不改当月金额）"
            ),
        )
    return CashHint(
        triggered=False,
        cash_market_value=cash_market_value,
        floor_amount=floor_amount,
        shortfall=Decimal("0"),
        message="现金充足：无补足需求",
    )


# ── 时效门禁（R7：唯一硬门禁）────────────────────────────────────────────────


def assert_fresh(policy: IpsPolicy, snapshot: Snapshot, as_of_calc: date) -> StaleInfo:
    """快照时效：`as_of` 距计算日 > stale_days 或晚于计算日 → 拒绝执行。"""
    holdings_as_of = snapshot.holdings_as_of
    days = (as_of_calc - holdings_as_of).days
    if days < 0:
        raise AllocationStaleError(
            f"as_of {holdings_as_of.isoformat()} 晚于计算日 {as_of_calc.isoformat()}"
            "（未来快照，拒绝产出指令）"
        )
    if days > policy.stale_days:
        raise AllocationStaleError(
            f"as_of {holdings_as_of.isoformat()} 距计算日 {as_of_calc.isoformat()} 共 {days} 天"
            f" > R8_stale_days {policy.stale_days}（快照过期，拒绝产出指令）"
        )
    return StaleInfo(days=days, threshold=policy.stale_days)


# ── 编排（R10）──────────────────────────────────────────────────────────────


def compute_plan(policy: IpsPolicy, snapshot: Snapshot, as_of_calc: date) -> AllocationPlan:
    """编排一条完整工单；纯函数，同输入两次输出逐字段一致（幂等）。

    入参只有政策、快照与计算日：快照派生金额字段不参与计算（R1）。
    """
    stale = assert_fresh(policy, snapshot, as_of_calc)
    execution_month, execution_day = resolve_execution_month_day(as_of_calc)
    gap = compute_gap(policy, snapshot)
    remaining_months = compute_remaining_months(policy, execution_month)
    decision = compute_monthly_amount(policy, snapshot, execution_month, gap, remaining_months)
    categories = allocate_categories(policy, snapshot, execution_month, decision.equity_amount)

    plan = AllocationPlan(
        as_of_calc=as_of_calc,
        execution_month=execution_month,
        execution_day=execution_day,
        gap=gap,
        remaining_months=remaining_months,
        equity_amount=decision.equity_amount,
        categories=categories,
        defer=DeferDecision(
            deferred=decision.deferred,
            reason=decision.reason if decision.deferred else None,
            cap_warning=decision.cap_warning,
        ),
        rebalance_hints=rebalance_hints(policy, snapshot),
        cash_hint=cash_floor_hint(policy, snapshot),
        stale=stale,
        reasons=(decision.reason,),
        echo=PlanEcho(
            target_equity=policy.target_equity,
            target_fixed_income=policy.target_fixed_income,
            target_cash=policy.target_cash,
            pool_total=snapshot.pool_total,
            holdings_market_value=snapshot.holdings_market_value,
            current_equity=snapshot.current_equity,
            current_fixed_income=snapshot.current_fixed_income,
            current_cash=snapshot.current_cash,
            horizon_months=policy.horizon_months,
            target_date=policy.target_date,
            start_month=policy.start_month,
            first_dca_month=_first_dca_month(policy),
            migration_month=_migration_month(policy),
            execution_day_rule=policy.execution_day,
            skip_if_equity_above=policy.skip_if_equity_above,
            equity_cap=policy.equity_cap,
            rebalance_band=policy.rebalance_band,
            cash_floor=policy.cash_floor,
            stale_days=policy.stale_days,
            rounding_rule=ROUNDING_RULE,
            as_of_calc=as_of_calc,
            holdings_as_of=snapshot.holdings_as_of,
        ),
    )
    return plan


def render_plan(plan: AllocationPlan) -> str:
    """人类可读工单（只含类别与金额，无代码/下单/体检结论）。"""
    echo = plan.echo
    lines = [
        "配置执行指令（纯算术；不含下单、选股与体检）",
        f"计算日: {plan.as_of_calc.isoformat()}",
        f"快照 as_of: {echo.holdings_as_of.isoformat()}"
        f"（距计算日 {plan.stale.days} 天，阈值 {plan.stale.threshold} 天，未过期）",
        f"执行月: {_month_text(plan.execution_month)}  执行日: {plan.execution_day.isoformat()}"
        f"（规则 {echo.execution_day_rule}）",
        f"缺口: {echo.target_equity} × {_money(echo.pool_total)}"
        f" − {_money(echo.holdings_market_value)} = {_money(plan.gap)}",
        f"剩余投放月数: {plan.remaining_months}"
        f"（首个定投月 {_month_text(echo.first_dca_month)} → 目标月 "
        f"{_month_text(_month_of(echo.target_date))}，含端点）",
        f"当月权益买入额: {_money(plan.equity_amount)} 元",
        "类别分配:",
    ]
    lines.extend(f"  - {category.label}: {_money(category.amount)} 元" for category in plan.categories)
    if plan.defer.deferred:
        lines.append(f"顺延: 是 — {plan.defer.reason}")
        if plan.defer.cap_warning:
            lines.append(f"提示: {plan.defer.cap_warning}")
    else:
        lines.append("顺延: 无")
    if plan.rebalance_hints:
        lines.append("再平衡提示:")
        lines.extend(f"  - {hint.message}" for hint in plan.rebalance_hints)
    else:
        lines.append("再平衡提示: 无")
    lines.append(f"现金不足提示: {plan.cash_hint.message if plan.cash_hint.triggered else '无'}")
    lines.append(f"理由: {'；'.join(plan.reasons)}")
    lines.extend(
        [
            "回显（核对与 ips 一致）:",
            f"  目标比例: 权益 {_pct(echo.target_equity)} / 固收 {_pct(echo.target_fixed_income)}"
            f" / 现金 {_pct(echo.target_cash)}",
            f"  当前占比: 权益 {_pct(echo.current_equity)} / 固收 {_pct(echo.current_fixed_income)}"
            f" / 现金 {_pct(echo.current_cash)}",
            f"  期限: {echo.horizon_months} 个月，目标日 {echo.target_date.isoformat()}"
            f"（目标月 {_month_text(_month_of(echo.target_date))}），start_month {echo.start_month}"
            f" → 迁移月 {_month_text(echo.migration_month)}、首个定投月 {_month_text(echo.first_dca_month)}",
            f"  阈值: 顺延 {_pct(echo.skip_if_equity_above)} / R1 上限 {_pct(echo.equity_cap)}"
            f" / 再平衡带 {_pp(echo.rebalance_band)} / 现金下限 {_pct(echo.cash_floor)}"
            f" / 时效 {echo.stale_days} 天（只提示，唯一硬门禁是时效拒绝）",
            f"  取整: {echo.rounding_rule}",
            f"  输入: 政策 config/ips.yaml + 快照 config/ips.local.yaml（as_of "
            f"{echo.holdings_as_of.isoformat()}）；池总额 {_money(echo.pool_total)}；"
            f"权益总市值 {_money(echo.holdings_market_value)}",
        ]
    )
    return "\n".join(lines)


def render_plan_json(plan: AllocationPlan) -> dict[str, Any]:
    """结构化输出（与工单文本同构，供机检）。"""
    echo = plan.echo
    return {
        "execution_month": _month_text(plan.execution_month),
        "execution_day": plan.execution_day.isoformat(),
        "gap": _json_number(plan.gap),
        "remaining_months": plan.remaining_months,
        "equity_buy_amount": _json_number(plan.equity_amount),
        "categories": [
            {"bucket": c.bucket, "label": c.label, "amount": _json_number(c.amount)}
            for c in plan.categories
        ],
        "defer": {
            "deferred": plan.defer.deferred,
            "reason": plan.defer.reason,
            "cap_warning": plan.defer.cap_warning,
        },
        "rebalance_hints": [
            {
                "bucket": hint.bucket,
                "label": hint.label,
                "current": _json_number(hint.current),
                "target": _json_number(hint.target),
                "deviation_pp": _json_number(hint.deviation * 100),
                "direction": hint.direction,
                "message": hint.message,
            }
            for hint in plan.rebalance_hints
        ],
        "cash_hint": {
            "triggered": plan.cash_hint.triggered,
            "cash_market_value": _json_number(plan.cash_hint.cash_market_value),
            "floor_amount": _json_number(plan.cash_hint.floor_amount),
            "shortfall": _json_number(plan.cash_hint.shortfall),
            "message": plan.cash_hint.message,
        },
        "stale": {"days": plan.stale.days, "threshold": plan.stale.threshold},
        "reasons": list(plan.reasons),
        "echo": {
            "as_of_calc": echo.as_of_calc.isoformat(),
            "holdings_as_of": echo.holdings_as_of.isoformat(),
            "pool_total": _json_number(echo.pool_total),
            "holdings_market_value": _json_number(echo.holdings_market_value),
            "target": {
                "equity": _json_number(echo.target_equity),
                "fixed_income": _json_number(echo.target_fixed_income),
                "cash": _json_number(echo.target_cash),
            },
            "current": {
                "equity": _json_number(echo.current_equity),
                "fixed_income": _json_number(echo.current_fixed_income),
                "cash": _json_number(echo.current_cash),
            },
            "horizon_months": echo.horizon_months,
            "target_date": echo.target_date.isoformat(),
            "start_month": echo.start_month,
            "first_dca_month": _month_text(echo.first_dca_month),
            "migration_month": _month_text(echo.migration_month),
            "execution_day_rule": echo.execution_day_rule,
            "thresholds": {
                "skip_if_equity_above": _json_number(echo.skip_if_equity_above),
                "equity_cap": _json_number(echo.equity_cap),
                "rebalance_band": _json_number(echo.rebalance_band),
                "cash_floor": _json_number(echo.cash_floor),
                "stale_days": echo.stale_days,
            },
            "rounding_rule": echo.rounding_rule,
        },
    }
