"""纯函数信号（design §4.1，R10）。

结构性约束（不靠自觉，见 design 否-4）：
- 函数签名只有 `(snapshot, condition)`，**不接收任何日期参数**；
- 只读 `PointInTimeSnapshot` 里的行（构造时已断言 `trade_date/visible_from <= as_of`）；
- 本模块不引入任何取数/存储/时钟依赖，因此无法读到 as_of 之后的数据。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.models import (
    ConditionSpec,
    EventSignal,
    PointInTimeSnapshot,
)

# MA60 口径沿用技术面既有定义（KD-10-03：SMA；不足 60 日的历史处置由 KQ-1 开关决定）
MA_WINDOW = 60
MA_FALLBACK_WINDOW = 20
SHORT_HISTORY_POLICIES = ("ma20_substitute", "exclude", "flag_only")
_REQUIRED_PARAMS = ("window", "fallback_window", "short_history_policy")


def evaluate_condition(
    snapshot: PointInTimeSnapshot, condition: ConditionSpec
) -> EventSignal | None:
    """在 t 日切片上判定条件是否成立；成立返回 `EventSignal(event_date=as_of)`。

    纯函数：同一 snapshot 重复调用必得同值结果（R10 Scenario「同输入同输出」）。
    """
    if condition.kind != "ma_breakdown":
        raise BacktestError(f"未实现的条件类型: {condition.kind!r}（MVP 只做 ma_breakdown）")
    params = _params(condition)
    bars = _bars_for(snapshot, params)
    if len(bars) < params["fallback_window"]:
        return None

    window = params["window"]
    if len(bars) < window:
        policy = params["short_history_policy"]
        if policy == "exclude":
            return None
        if policy == "flag_only":
            return None
        window = params["fallback_window"]

    closes = [bar.close for bar in bars]
    current_ma = _sma(closes, window)
    previous_ma = _sma(closes[:-1], window)
    if current_ma is None or previous_ma is None:
        return None
    previous_close = closes[-2]
    if previous_close >= previous_ma and closes[-1] < current_ma:
        return EventSignal(condition_id=condition.condition_id, event_date=str(snapshot.as_of))
    return None


def _params(condition: ConditionSpec) -> dict[str, Any]:
    missing = [key for key in _REQUIRED_PARAMS if key not in condition.params]
    if missing:
        raise MissingBacktestConfigError(
            f"条件 {condition.condition_id} 缺参数: {', '.join(missing)}（不得预埋默认值）"
        )
    window = int(condition.params["window"])
    fallback_window = int(condition.params["fallback_window"])
    if window < 1 or fallback_window < 1:
        raise MissingBacktestConfigError(f"条件窗口非法: {window}/{fallback_window}")
    policy = str(condition.params["short_history_policy"])
    if policy not in SHORT_HISTORY_POLICIES:
        raise MissingBacktestConfigError(
            f"short_history_policy 非法: {policy!r}；允许 {SHORT_HISTORY_POLICIES}（KQ-1）"
        )
    return {"window": window, "fallback_window": fallback_window, "short_history_policy": policy}


def _bars_for(snapshot: PointInTimeSnapshot, params: Mapping[str, Any]) -> Sequence[Any]:
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
