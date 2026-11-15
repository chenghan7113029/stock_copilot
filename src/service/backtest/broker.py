"""A 股撮合：成本四分量 + T+1 / 封板顺延 / 停牌跳过 / 流动性上限（design §4.1，R7/R8）。

口径来源：
- 成本构成与方向：飞书 r482 §二·#4（佣金、卖出印花税、按成交额分层滑点）；
- 数值：一律来自 `config/app.yaml backtest:`（Q4 未答复 → 缺键 `MissingBacktestConfigError`）；
- T+1 / 封板顺延 / 停牌跳过：市场规则，**代码内不变量**（`_design.md` §4.1「canon 不可调」）；
- 封板判定：A3「日终一字板（无成交）」；Q5 未答复前只做这一种判定并在明细标注原因。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from common.exceptions import BacktestDataGapError, BacktestError, MissingBacktestConfigError
from common.trading_day import is_a_share_trading_day
from service.backtest.models import (
    LOT_SIZE,
    ZERO_COST,
    BacktestConfig,
    CostBreakdown,
    Fill,
    LiquidityCapSpec,
    Order,
    OrderAttempt,
    OrderSide,
    OrderStatus,
    PriceBar,
)


@dataclass(frozen=True)
class SlippageTier:
    amount_lower: float
    amount_upper: float | None
    bps: float


@dataclass(frozen=True)
class CostRules:
    commission_rate: float
    commission_min: float
    stamp_tax_rate: float
    transfer_fee_included: bool
    transfer_fee_rate: float
    slippage_tiers: tuple[SlippageTier, ...]


@dataclass(frozen=True)
class LiquidityTier:
    amount_lower: float
    amount_upper: float | None
    max_participation: float


class CostCalculator:
    """成本四分量（佣金/印花税/滑点/过户费）；缺键即拒绝，不按 0。"""

    def __init__(self, rules: CostRules) -> None:
        self.rules = rules

    @classmethod
    def from_config(cls, cfg: BacktestConfig) -> "CostCalculator":
        return cls(_cost_rules(cfg))

    def slippage_rate(self, amount: float) -> float:
        for tier in self.rules.slippage_tiers:
            upper = tier.amount_upper
            if amount >= tier.amount_lower and (upper is None or amount < upper):
                return tier.bps / 10000.0
        raise MissingBacktestConfigError(
            f"无匹配滑点档位：金额 {amount} 不在 slippage_tiers 覆盖区间内（Q4）"
        )

    def cost(
        self, amount: float, side: OrderSide, *, slippage_multiplier: float = 1.0
    ) -> tuple[CostBreakdown, tuple[str, ...]]:
        """四分量成本（R7）。过户费 `included=true` 时**并入佣金、不单列**（§9.3 t37）。"""
        notes: list[str] = []
        raw_commission = amount * self.rules.commission_rate
        commission = max(raw_commission, self.rules.commission_min)
        if raw_commission < self.rules.commission_min:
            notes.append("触发最低佣金")
        # 过户费并入佣金：只在佣金行计一次，transfer_fee 分量固定 0（不双算）
        merged_transfer = (
            amount * self.rules.transfer_fee_rate if self.rules.transfer_fee_included else 0.0
        )
        commission += merged_transfer
        if merged_transfer > 0:
            notes.append("过户费已并入佣金")
        stamp_tax = amount * self.rules.stamp_tax_rate if side is OrderSide.SELL else 0.0
        slippage = amount * self.slippage_rate(amount) * slippage_multiplier
        total = commission + stamp_tax + slippage
        return (
            CostBreakdown(
                commission=commission,
                stamp_tax=stamp_tax,
                slippage=slippage,
                transfer_fee=0.0,
                total=total,
            ),
            tuple(notes),
        )


class LiquidityRules:
    """单笔下单金额上限（按日均成交额分档，R7；T2-fix-5）。

    上限 = `PriceBar.avg_amount × 匹配档 max_participation`。`liquidity_cap` 未配置 →
    `MissingBacktestConfigError`；多档需要「日均成交额 → adv_tier」映射数据（本机缺口）→
    `BacktestDataGapError`，**不退化单档**（禁止静默降级）。
    """

    def __init__(self, caps: tuple[LiquidityCapSpec, ...]) -> None:
        self.caps = caps

    @classmethod
    def from_config(cls, cfg: BacktestConfig) -> "LiquidityRules":
        caps = cfg.liquidity_cap
        if caps is None:
            raise MissingBacktestConfigError("回测配置缺值: liquidity_cap（Q4）")
        if len(caps) > 1:
            raise BacktestDataGapError(
                "流动性上限配置了多档，但缺「日均成交额→adv_tier」映射数据："
                "不退化单档、不猜档位（R7/Q4/T2-fix-5）"
            )
        return cls(tuple(caps))

    def limit_for(self, daily_amount: float) -> float:
        return daily_amount * self.caps[0].max_participation


def _cost_rules(cfg: BacktestConfig) -> CostRules:
    commission = cfg.commission
    if commission is None:
        raise MissingBacktestConfigError("回测配置缺值: commission.rate/min（Q4）")
    stamp_tax = cfg.stamp_tax
    if stamp_tax is None:
        raise MissingBacktestConfigError("回测配置缺值: stamp_tax.side/rate（Q4）")
    transfer_fee = cfg.transfer_fee
    if transfer_fee is None:
        raise MissingBacktestConfigError("回测配置缺值: transfer_fee.included/rate（Q4）")
    slippage = cfg.slippage_tiers
    if not slippage:
        raise MissingBacktestConfigError("回测配置缺值: slippage_tiers（Q4）")
    return CostRules(
        commission_rate=float(commission.rate),
        commission_min=float(commission.min),
        stamp_tax_rate=float(stamp_tax.rate),
        transfer_fee_included=bool(transfer_fee.included),
        transfer_fee_rate=float(transfer_fee.rate),
        slippage_tiers=tuple(
            SlippageTier(
                amount_lower=float(tier.amount_lower),
                amount_upper=(None if tier.amount_upper is None else float(tier.amount_upper)),
                bps=float(tier.bps),
            )
            for tier in slippage
        ),
    )


def _is_trading_day(day: str, holidays: Sequence[str]) -> bool:
    return is_a_share_trading_day(date.fromisoformat(day), holidays=holidays)


def next_tradable_day(
    day: str,
    *,
    calendar: Any,
    prices: Sequence[PriceBar] | None = None,
) -> str:
    """下一个可成交交易日（严格晚于 `day`）；`calendar` 可为 callable 或带 is_trading_day。"""
    is_trading = _calendar_callable(calendar)
    current = date.fromisoformat(day)
    known_dates = {bar.trade_date for bar in prices or ()}
    for _ in range(3650):  # 上限只为防死循环；真实顺延由 execute_orders 的 max_delay 封死
        current = current + timedelta(days=1)
        candidate = current.isoformat()
        if not is_trading(candidate):
            continue
        if known_dates and candidate not in known_dates:
            continue
        return candidate
    raise BacktestError(f"找不到 {day} 之后的可成交交易日（日历异常）")


def _calendar_callable(calendar: Any) -> Any:
    if callable(calendar):
        return calendar
    method = getattr(calendar, "is_trading_day", None)
    if method is None:
        raise BacktestError("calendar 必须是 callable 或带 is_trading_day 的对象")
    return method


def execute_orders(
    orders: Sequence[Order],
    prices: Mapping[str, Sequence[PriceBar]],
    *,
    cfg: BacktestConfig,
) -> tuple[Fill, ...]:
    """确定性状态机：t+1 成交、封板顺延、停牌跳过、T+1 拒绝、流动性截断（R7/R8）。

    T+1 的持仓来源 = 同一批次内 Buy 的成交日（当日买入不可当日卖出）；跨批次持仓不在
    本函数状态内（MVP 事件研究不做组合级持仓账）。
    """
    if cfg.max_delay_days is None:
        raise MissingBacktestConfigError(
            "回测配置缺值: max_delay_days（防撮合无限顺延，Q7/design §3H）"
        )
    max_delay = int(cfg.max_delay_days)
    if max_delay < 1:
        raise MissingBacktestConfigError(f"max_delay_days 非法: {max_delay}")
    _require_market_rule_config(cfg)
    calculator = CostCalculator.from_config(cfg)
    liquidity = LiquidityRules.from_config(cfg)
    holidays: tuple[str, ...] = ()  # 休市表未在 schema 内 → A2「周一至周五」降级

    known_buy_dates: dict[str, str] = {}
    fills: list[Fill] = []
    for order in orders:
        bars = tuple(sorted(prices.get(order.code, ()), key=lambda bar: bar.trade_date))
        if not bars:
            raise BacktestDataGapError(f"{order.code} 无价格序列，无法撮合（R8）")
        candidates = [
            bar.trade_date
            for bar in bars
            if bar.trade_date > order.signal_date and _is_trading_day(bar.trade_date, holidays)
        ]
        if not candidates:
            raise BacktestDataGapError(
                f"{order.code} 在信号日 {order.signal_date} 之后无可成交交易日（R8）"
            )
        bar_by_date = {bar.trade_date: bar for bar in bars}
        prev_close_by_date = {
            bars[index].trade_date: bars[index - 1].close for index in range(1, len(bars))
        }

        sellable_from: str | None = None
        if order.side is OrderSide.SELL and order.code in known_buy_dates:
            buy_date = known_buy_dates[order.code]
            sellable_from = next_tradable_day(
                buy_date, calendar=_calendar(holidays)
            )

        fill = _run_order(
            order=order,
            candidates=candidates,
            bar_by_date=bar_by_date,
            calculator=calculator,
            liquidity=liquidity,
            max_delay=max_delay,
            sellable_from=sellable_from,
            cfg=cfg,
            prev_close_by_date=prev_close_by_date,
        )
        fills.append(fill)
        if order.side is OrderSide.BUY and fill.fill_date:
            known_buy_dates[order.code] = fill.fill_date
    return tuple(fills)


def _calendar(holidays: Sequence[str]) -> Any:
    return lambda day: _is_trading_day(day, holidays)


def _run_order(
    *,
    order: Order,
    candidates: Sequence[str],
    bar_by_date: Mapping[str, PriceBar],
    calculator: CostCalculator,
    liquidity: LiquidityRules,
    max_delay: int,
    sellable_from: str | None,
    cfg: BacktestConfig,
    prev_close_by_date: Mapping[str, float],
) -> Fill:
    attempts: list[OrderAttempt] = []
    sealed_days = 0
    for index, attempt_date in enumerate(candidates):
        if index >= max_delay:
            attempts.append(
                OrderAttempt(
                    attempt_date=attempt_date,
                    status=OrderStatus.FAILED_LIMIT_SEAL,
                    reason=f"超过最大顺延上限（{max_delay} 个交易日），订单失败",
                )
            )
            break
        bar = bar_by_date[attempt_date]
        if bar.suspended:
            attempts.append(
                OrderAttempt(attempt_date, OrderStatus.SKIPPED_SUSPENDED, "停牌，跳过并顺延")
            )
            continue
        prev_close = prev_close_by_date.get(attempt_date)
        seal = _seal_state(bar, prev_close, order.side, cfg)
        if seal == "flat":
            sealed_days += 1
            direction = "涨停" if order.side is OrderSide.BUY else "跌停"
            attempts.append(
                OrderAttempt(
                    attempt_date,
                    OrderStatus.FAILED_LIMIT_SEAL,
                    f"一字{direction}封板（{_limit_pct(bar.code, bar.st, cfg):.0%}），无法成交",
                )
            )
            continue
        if sellable_from is not None and attempt_date < sellable_from:
            attempts.append(
                OrderAttempt(
                    attempt_date,
                    OrderStatus.REJECTED_T1,
                    f"T+1 拒绝：当日买入不可当日卖出，最早可卖日 {sellable_from}",
                )
            )
            return Fill(
                order=order,
                attempts=tuple(attempts),
                cost=ZERO_COST,
                fill_date=None,
                fill_price=None,
                filled_amount=None,
                delay_days=0,
                notes=(
                    "T+1 拒绝：当日买入不可当日卖出",
                    f"最早可卖日={sellable_from}",
                ),
            )
        if bar.amount is None:
            raise BacktestDataGapError(
                f"{order.code} {attempt_date} 缺成交额，滑点分档不可算（R7）"
            )
        if bar.avg_amount is None:
            raise BacktestDataGapError(
                f"{order.code} {attempt_date} 缺日均成交额 avg_amount：流动性上限不可算（R7/T2-fix-5）"
            )
        requested = float(order.requested_amount)
        cap = liquidity.limit_for(float(bar.avg_amount))
        filled = min(requested, cap)
        capped = filled < requested
        fill_price = bar.close
        filled_amount = _round_lots(filled, fill_price, order.requested_qty)
        opened_seal = seal == "opened"
        cost, cost_notes = calculator.cost(
            filled_amount, order.side, slippage_multiplier=2.0 if opened_seal else 1.0
        )
        notes: list[str] = list(cost_notes)
        if opened_seal:
            notes.append("收盘封板但盘中打开：可成交，滑点加倍")
        if capped:
            notes.append("触及流动性上限")
            notes.append("剩余额度需新订单顺延至下一可成交日")
        if sealed_days >= 2:
            notes.append(f"连续封板 {sealed_days} 日")
        status = OrderStatus.CAPPED_LIQUIDITY if capped else OrderStatus.FILLED
        reason = "触及流动性上限，按上限截断" if capped else None
        attempts.append(OrderAttempt(attempt_date, status, reason))
        return Fill(
            order=order,
            attempts=tuple(attempts),
            cost=cost,
            fill_date=attempt_date,
            fill_price=fill_price,
            filled_amount=filled_amount,
            delay_days=index,
            notes=tuple(notes),
        )
    return Fill(
        order=order,
        attempts=tuple(attempts),
        cost=ZERO_COST,
        fill_date=None,
        fill_price=None,
        filled_amount=None,
        delay_days=0,
        notes=(f"未成交：最大顺延上限 {max_delay} 个交易日已用尽",),
    )


def _require_market_rule_config(cfg: BacktestConfig) -> None:
    """Q5 口径必须来自配置：缺键即拒绝（broker 不再硬编码任何涨跌停/封板/停牌默认值）。"""
    if cfg.limit_pct is None:
        raise MissingBacktestConfigError("回测配置缺值: limit_pct（Q5 涨跌停判定）")
    for key in ("board", "st", "bj"):
        if cfg.limit_pct.get(key) is None:
            raise MissingBacktestConfigError(f"回测配置缺值: limit_pct.{key}（Q5）")
    if _star_chinext_pct(cfg) is None:
        raise MissingBacktestConfigError(
            "回测配置缺值: limit_pct.star_chinext（Q5；兼容 star/chinext 别名）"
        )
    if not cfg.seal_definition:
        raise MissingBacktestConfigError("回测配置缺值: seal_definition（Q5 封板判定口径）")
    seal_text = str(cfg.seal_definition).lower()
    if "一字" not in seal_text and "one_word" not in seal_text:
        raise MissingBacktestConfigError(
            f"seal_definition 口径未知: {cfg.seal_definition!r}（需含「一字板」/one_word 判定，Q5）"
        )
    if not cfg.suspend_source:
        raise MissingBacktestConfigError("回测配置缺值: suspend_source（Q5 停牌源）")


def _board_key(code: str, st: bool) -> str:
    """按代码前缀/ST 标记映射 limit_pct 档位（ST 优先级最高）。"""
    if st:
        return "st"
    if code.startswith(("688", "689", "300", "301")):
        return "star_chinext"
    if code.startswith(("4", "8")):
        return "bj"
    return "board"


def _star_chinext_pct(cfg: BacktestConfig) -> float | None:
    """科创板/创业板 20% 档：契约键 `star_chinext`，兼容 `star`/`chinext` 别名（同一口径）。"""
    mapping = cfg.limit_pct or {}
    for key in ("star_chinext", "star", "chinext"):
        value = mapping.get(key)
        if value is not None:
            return float(value)
    return None


def _limit_pct(code: str, st: bool, cfg: BacktestConfig) -> float:
    key = _board_key(code, st)
    if key == "star_chinext":
        value = _star_chinext_pct(cfg)
        if value is None:
            raise MissingBacktestConfigError(
                "回测配置缺值: limit_pct.star_chinext（Q5；兼容 star/chinext 别名）"
            )
        return value
    value = (cfg.limit_pct or {}).get(key)
    if value is None:
        raise MissingBacktestConfigError(f"回测配置缺值: limit_pct.{key}（Q5）")
    return float(value)


def _seal_state(
    bar: PriceBar, prev_close: float | None, side: OrderSide, cfg: BacktestConfig
) -> str:
    """Q5 封板判定（配置驱动）：`flat`=一字板不可成交；`opened`=收盘封板但盘中打开（可成交+滑点加倍）。

    涨跌停价优先用数据字段（`PriceBar.limit_up_price/limit_down_price`，即真实市场限价）；
    数据缺该字段时按 §9.3 `limit_pct`（按板/ST 分档）由前收盘价推算；两者都缺 →
    `BacktestDataGapError`（不猜阈值）。
    """
    if side is OrderSide.BUY:
        limit = bar.limit_up_price
        if limit is None:
            if prev_close is None:
                raise BacktestDataGapError(
                    f"{bar.code} {bar.trade_date} 缺涨跌停价与前收盘价：封板判定不可做（Q5/R8）"
                )
            limit = round(prev_close * (1.0 + _limit_pct(bar.code, bar.st, cfg)) + 1e-9, 2)
        at_limit = bar.close >= float(limit) - 1e-9
    else:
        limit = bar.limit_down_price
        if limit is None:
            if prev_close is None:
                raise BacktestDataGapError(
                    f"{bar.code} {bar.trade_date} 缺涨跌停价与前收盘价：封板判定不可做（Q5/R8）"
                )
            limit = round(prev_close * (1.0 - _limit_pct(bar.code, bar.st, cfg)) + 1e-9, 2)
        at_limit = bar.close <= float(limit) + 1e-9
    if not at_limit:
        return "none"
    flat = bar.open == bar.high == bar.low == bar.close
    return "flat" if flat else "opened"


def _round_lots(amount: float, price: float, requested_qty: int | None) -> float:
    """按 100 股一手取整；不足一手时按金额成交并交由调用方标注（MVP 事件研究不做组合撮合）。"""
    if price <= 0:
        raise BacktestError(f"成交价非法: {price}")
    if requested_qty is not None:
        qty = int(requested_qty)
    else:
        qty = int(amount / price // LOT_SIZE) * LOT_SIZE
    if qty < LOT_SIZE:
        return amount
    return qty * price
