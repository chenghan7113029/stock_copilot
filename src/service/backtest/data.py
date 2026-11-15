"""数据对齐：后复权价 + 财务公告日 + 时点视图（design §4.1，R9/R10/R11）。

`loader` 是注入点（外部数据层适配器或测试假件），只要求方法：
- `load_price_rows(codes, start, end, adjust)` → {code: (row, ...)}
- `load_financial_rows(codes, as_of)` → {code: (row, ...)}

防未来函数靠**结构**：时点视图不裁剪未来行，而是把 loader 给的行原样放进
`PointInTimeSnapshot`，由其 `__post_init__` 抛 `FutureDataError`（不静默截断，R10）。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence

from common.exceptions import BacktestDataGapError
from data_provider.backtest.adjust_price import parse_adjust_mode
from data_provider.backtest.financial_timing import annotate_visible_from
from service.backtest.models import (
    AdjustMode,
    BacktestConfig,
    Benchmark,
    EventObservation,
    EventSignal,
    FinancialRecord,
    PointInTimeSnapshot,
    PriceBar,
)

# 时点视图取全历史起点（非业务口径：只是「不设下界」，避免引入未确认参数）
HISTORY_START = "1900-01-01"


def _call(loader: Any, method: str, *args: Any, **kwargs: Any) -> Any:
    """取数通道：支持「带方法的适配器对象」与「可调用 loader」两种注入形态。"""
    func = getattr(loader, method, None)
    if func is not None:
        return func(*args, **kwargs)
    if callable(loader):
        return loader(*args, **kwargs)
    raise BacktestDataGapError(f"loader 缺 {method}：数据通道未接通（不静默降级）")


def _same_mode(row_mode: Any, mode: AdjustMode) -> bool:
    raw = row_mode.value if isinstance(row_mode, Enum) else str(row_mode)
    return raw == mode.value


def load_price_series(
    codes: Sequence[str],
    start: str,
    end: str,
    adjust: AdjustMode | str,
    *,
    loader: Any,
) -> dict[str, tuple[PriceBar, ...]]:
    """`adjust` 只允许 hfq/segmented_hfq：前复权抛 `InvalidAdjustModeError`（R9）。"""
    mode = AdjustMode(parse_adjust_mode(adjust))
    rows = _call(loader, "load_price_rows", list(codes), start, end, mode)
    result: dict[str, tuple[PriceBar, ...]] = {}
    for code in codes:
        items = rows.get(code, ())
        bars = tuple(sorted((_to_price_bar(row, code, mode) for row in items), key=lambda b: b.trade_date))
        if not bars:
            raise BacktestDataGapError(f"{code} 在 {start}~{end} 无后复权价格（R9）")
        result[code] = bars
    return result


def _to_price_bar(row: Any, code: str, mode: AdjustMode) -> PriceBar:
    if isinstance(row, PriceBar):
        return row  # loader 已产出契约对象（信任其口径）；口径元数据由调用方记录
    row_mode = row.get("adjust_mode")
    if row_mode is not None and not _same_mode(row_mode, mode):
        raise BacktestDataGapError(f"{code} 行口径 {row_mode!r} ≠ 请求口径 {mode!r}（R9）")
    trade_date = str(row.get("trade_date", "")).strip()
    if not trade_date:
        raise BacktestDataGapError(f"{code} 价格行缺 trade_date: {row!r}")
    try:
        ohlc = {key: float(row[key]) for key in ("open", "high", "low", "close")}
    except (KeyError, TypeError, ValueError) as exc:
        raise BacktestDataGapError(f"{code} {trade_date} 价格字段不全: {row!r}") from exc
    return PriceBar(
        code=code,
        trade_date=trade_date,
        open=ohlc["open"],
        high=ohlc["high"],
        low=ohlc["low"],
        close=ohlc["close"],
        amount=_opt_float(row.get("amount")),
        avg_amount=_opt_float(row.get("avg_amount")),
        limit_up_price=_opt_float(row.get("limit_up_price")),
        limit_down_price=_opt_float(row.get("limit_down_price")),
        suspended=bool(row.get("suspended", False)),
        delisted=bool(row.get("delisted", False)),
        st=bool(row.get("st", False)),
    )


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def load_financials_point_in_time(
    codes: Sequence[str], as_of: str, *, loader: Any
) -> dict[str, tuple[FinancialRecord, ...]]:
    """按 `visible_from <= as_of` 对齐（R11）；缺 `ann_date` 走保守回退并标注。"""
    rows = _call(loader, "load_financial_rows", list(codes), as_of)
    result: dict[str, tuple[FinancialRecord, ...]] = {code: () for code in codes}
    for code in codes:
        items = []
        for row in rows.get(code, ()):
            if isinstance(row, FinancialRecord):
                if row.visible_from <= as_of:
                    items.append(row)
                continue
            if "visible_from" not in row:
                row = annotate_visible_from([row])[0]
            record = FinancialRecord(
                code=code,
                report_period=str(row["report_period"]),
                visible_from=str(row["visible_from"]),
                ann_date=None if row.get("ann_date") in (None, "") else str(row["ann_date"]),
                end_date=None if row.get("end_date") in (None, "") else str(row["end_date"]),
                ann_date_fallback=bool(row.get("ann_date_fallback", False)),
                fields={
                    key: float(value)
                    for key, value in dict(row.get("fields") or {}).items()
                },
            )
            if record.visible_from <= as_of:
                items.append(record)
        result[code] = tuple(sorted(items, key=lambda item: item.visible_from))
    return result


def build_point_in_time(codes: Sequence[str], as_of: str, *, loader: Any) -> PointInTimeSnapshot:
    """构造 signal 的输入：只请求 `<= as_of` 的数据，越界由快照断言抛 `FutureDataError`。"""
    prices = load_price_series(codes, start=HISTORY_START, end=as_of, adjust=AdjustMode.HFQ, loader=loader)
    financials = load_financials_point_in_time(codes, as_of, loader=loader)
    price_bars: list[PriceBar] = []
    for code in codes:
        price_bars.extend(prices.get(code, ()))
    financial_records: list[FinancialRecord] = []
    for code in codes:
        financial_records.extend(financials.get(code, ()))
    # 结构性防线：loader 已按 end=as_of 请求；若仍返回未来行，这里**不裁剪**而是让快照抛错
    return PointInTimeSnapshot(
        as_of=as_of,
        price=tuple(price_bars),
        financials=tuple(financial_records),
    )

def load_event_observations(
    signals: Sequence[EventSignal],
    benchmarks: Sequence[Benchmark],
    *,
    loader: Any,
    cfg: BacktestConfig,
) -> tuple[EventObservation, ...]:
    """为每个 EventSignal 载入事件日后逐日超额（design §4.1，T2-fix-4）。

    `EventSignal` 只判「条件成立」，本身不带标的代码；loader 契约因此是
    **事件级**取数（缺方法即 `BacktestDataGapError`，不静默降级）：
    - `load_forward_returns(signal, horizon)` → `(code, 事件日后第 1..horizon 个交易日的逐日收益)`；
    - `load_benchmark_forward_returns(kind, signal, horizon)` → 同期基准逐日收益。

    `horizon = max(cfg.windows)`；逐日相减得到 `EventObservation.excess_returns`。
    """
    if not signals:
        raise BacktestDataGapError("事件研究无事件信号：不得产出结论（R17）")
    if not benchmarks:
        raise BacktestDataGapError("基准缺失：不得给出有效判定（R13）")
    horizon = max(cfg.windows)
    fetch_stock = getattr(loader, "load_forward_returns", None)
    fetch_benchmark = getattr(loader, "load_benchmark_forward_returns", None)
    if fetch_stock is None or fetch_benchmark is None:
        raise BacktestDataGapError(
            "事件收益通道未接通：loader 缺 load_forward_returns / "
            "load_benchmark_forward_returns（R17/R13，不静默降级）"
        )
    observations: list[EventObservation] = []
    for signal in signals:
        code, raw_returns = fetch_stock(signal, horizon)
        stock_returns = tuple(float(value) for value in raw_returns)
        if len(stock_returns) < horizon:
            raise BacktestDataGapError(
                f"{signal.event_date} 事件后收益不足 {horizon} 日：样本不足（R17）"
            )
        for benchmark in benchmarks:
            raw_benchmark = fetch_benchmark(benchmark.kind, signal, horizon)
            benchmark_returns = tuple(float(value) for value in raw_benchmark)
            if len(benchmark_returns) < horizon:
                raise BacktestDataGapError(
                    f"{benchmark.kind} 在 {signal.event_date} 后收益不足 {horizon} 日（R13）"
                )
            observations.append(
                EventObservation(
                    code=str(code),
                    event_date=signal.event_date,
                    condition_id=signal.condition_id,
                    benchmark_kind=benchmark.kind,
                    excess_returns=tuple(
                        stock - bench
                        for stock, bench in zip(stock_returns, benchmark_returns)
                    ),
                )
            )
    return tuple(observations)
