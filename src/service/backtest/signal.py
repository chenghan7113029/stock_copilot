"""纯函数信号（design §4.1，R10）。

结构性约束（不靠自觉，见 design 否-4）：
- 函数签名只有 `(snapshot, condition)`，**不接收任何日期参数**；
- 只读 `PointInTimeSnapshot` 里的行（构造时已断言 `trade_date/visible_from <= as_of`）；
- 本模块不引入任何取数/存储/时钟依赖，因此无法读到 as_of 之后的数据。
"""

from __future__ import annotations

from typing import Any, Sequence

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.models import (
    ConditionSpec,
    EventSignal,
    PointInTimeSnapshot,
)

# MA60 口径沿用技术面既有定义（KD-10-03：SMA；不足 60 日用 MA20 替代 = tech 现行口径）
MA_WINDOW = 60
MA_FALLBACK_WINDOW = 20
# T2-fix-4：条件类型固定为 "ma60_breakdown"，参数只有 window（design §4.1 示例 {window: 60}）
CONDITION_KIND = "ma60_breakdown"
REQUIRED_PARAMS = ("window",)


def evaluate_condition(
    snapshot: PointInTimeSnapshot, condition: ConditionSpec
) -> EventSignal | None:
    """在 t 日切片上判定条件是否成立；成立返回 `EventSignal(event_date=as_of)`。

    纯函数：同一 snapshot 重复调用必得同值结果（R10 Scenario「同输入同输出」）。
    """
    if condition.kind != CONDITION_KIND:
        raise BacktestError(
            f"未实现的条件类型: {condition.kind!r}（MVP 只做 {CONDITION_KIND}）"
        )
    window = _params(condition)
    bars = _bars_for(snapshot)
    if len(bars) < MA_FALLBACK_WINDOW:
        return None
    if len(bars) < window:
        # 不足 window 个交易日：沿用 tech 现行口径（MA20 替代，KD-10-03）
        window = MA_FALLBACK_WINDOW

    closes = [bar.close for bar in bars]
    current_ma = _sma(closes, window)
    previous_ma = _sma(closes[:-1], window)
    if current_ma is None or previous_ma is None:
        return None
    previous_close = closes[-2]
    if previous_close >= previous_ma and closes[-1] < current_ma:
        return EventSignal(condition_id=condition.condition_id, event_date=str(snapshot.as_of))
    return None


def _params(condition: ConditionSpec) -> int:
    missing = [key for key in REQUIRED_PARAMS if key not in condition.params]
    if missing:
        raise MissingBacktestConfigError(
            f"条件 {condition.condition_id} 缺参数: {', '.join(missing)}（不得预埋默认值）"
        )
    window = int(condition.params["window"])
    if window < 1:
        raise MissingBacktestConfigError(f"条件窗口非法: {window}")
    return window


def _bars_for(snapshot: PointInTimeSnapshot) -> Sequence[Any]:
    bars = sorted(snapshot.price, key=lambda bar: bar.trade_date)
    if not bars:
        return ()
    codes = {bar.code for bar in bars}
    if len(codes) > 1:
        raise BacktestError(
            f"一个时点切片只能含单一标的，实际 {sorted(codes)}：多标的请逐票构造切片"
        )
    return bars


def _sma(closes: Sequence[float], window: int) -> float | None:
    if window < 1 or len(closes) < window:
        return None
    window_slice = closes[-window:]
    return sum(window_slice) / float(window)
