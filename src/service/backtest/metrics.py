"""指标 / 统计推断 / 归因 / 部分池化 / 稳定性（design §4.1，R5/R6/R13/R14/R16/R17）。

全部纯函数、确定性：
- 推断默认 block bootstrap（R6；禁止 iid t 检验下结论）；
- 块长 / 重采样次数 / 样本阈值来自配置，缺键即 `MissingBacktestConfigError`（KQ-2 未答复）；
- 固定随机种子只为可复现，不是业务口径。
"""

from __future__ import annotations

import math
import random
from typing import Any, Iterable, Mapping, Sequence

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.models import (
    EVENT_WINDOWS,
    AttributionResult,
    BacktestConfig,
    Benchmark,
    EventObservation,
    EventStudyResult,
    StabilityResult,
    WindowStats,
)

FACTOR_KEYS = ("beta", "size", "value", "momentum")
# R14（飞书原文「每组至少 30 只、跨度至少 3 年」）：已确定要求，非待确认数值
MIN_GROUP_SIZE = 30
MIN_YEARS = 3
# 固定种子：只保证可复现，不影响任何口径（非业务默认值）
BOOTSTRAP_SEED = 0
CI_LOWER_Q = 0.025
CI_UPPER_Q = 0.975


# --------------------------------------------------------------------------
# 基础统计
# --------------------------------------------------------------------------


def _mean(values: Sequence[float]) -> float:
    return sum(values) / float(len(values)) if values else 0.0


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (n - 1)
    return math.sqrt(variance)


def _quantile(ordered: Sequence[float], q: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def p_value_from_t(t_stat: float) -> float:
    """双侧 p 值（正态近似）——确定性、无第三方依赖。"""
    return math.erfc(abs(float(t_stat)) / math.sqrt(2.0))


def t_statistic(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    std = _std(values)
    if std == 0.0:
        return 0.0 if _mean(values) == 0.0 else math.copysign(math.inf, _mean(values))
    return _mean(values) / (std / math.sqrt(n))


# --------------------------------------------------------------------------
# R6 block bootstrap
# --------------------------------------------------------------------------


def block_bootstrap(
    excess: Sequence[float],
    *,
    block_length: int,
    n_bootstrap: int,
    seed: int,
) -> tuple[tuple[float, float], int]:
    """按时间块重采样，返回 (CI, 有效样本=时间块数)；同时满足 R6「报告有效样本」。"""
    values = [float(value) for value in excess]
    n = len(values)
    if n == 0:
        return (0.0, 0.0), 0
    if int(block_length) < 1:
        raise MissingBacktestConfigError(f"block_length 非法: {block_length}（KQ-2）")
    if int(n_bootstrap) < 1:
        raise MissingBacktestConfigError(f"n_bootstrap 非法: {n_bootstrap}（KQ-2）")
    block = int(block_length)
    effective_n = int(math.ceil(n / block))
    rng = random.Random(int(seed))
    means: list[float] = []
    for _ in range(int(n_bootstrap)):
        sample: list[float] = []
        while len(sample) < n:
            start = rng.randrange(n)
            for offset in range(block):
                sample.append(values[(start + offset) % n])
                if len(sample) == n:
                    break
        means.append(_mean(sample))
    means.sort()
    return (
        (_quantile(means, CI_LOWER_Q), _quantile(means, CI_UPPER_Q)),
        effective_n,
    )


# --------------------------------------------------------------------------
# R5 多重比较校正
# --------------------------------------------------------------------------


def multiple_testing_correction(
    p_values: Sequence[float],
    K: int | None,
    method: str,
    *,
    cfg: BacktestConfig,
) -> tuple[float, ...]:
    """Bonferroni / Deflated Sharpe 择一（预注册固定）；K 缺失不得下发结论（R5）。"""
    if K is None:
        raise BacktestError("K 缺失：不得给出校正后判定，结论只能是「不可判定」（R5）")
    trials = int(K)
    if trials < 1:
        raise BacktestError(f"K 非法: {K}（R5 要求报告累计尝试次数）")
    normalized = str(method).strip().lower()
    if normalized == "bonferroni":
        return tuple(min(1.0, max(0.0, float(p)) * trials) for p in p_values)
    if normalized == "deflated_sharpe":
        raise MissingBacktestConfigError(
            "deflated_sharpe 校正参数未配置（KQ-5 未答复）：缺 backtest.deflated_sharpe"
        )
    raise MissingBacktestConfigError(f"未知校正方法: {method!r}（只允许 bonferroni/deflated_sharpe）")


# --------------------------------------------------------------------------
# R17/R13 事件研究
# --------------------------------------------------------------------------


def _inference_cfg(cfg: BacktestConfig) -> tuple[int, int]:
    block_length = int(cfg.require("block_length"))
    n_bootstrap = int(cfg.require("n_bootstrap"))
    return block_length, n_bootstrap


def _window_stats(
    observations: Sequence[EventObservation], *, block_length: int, n_bootstrap: int
) -> WindowStats:
    excess = [float(item.excess) for item in observations]
    ci, effective_n = block_bootstrap(
        excess, block_length=block_length, n_bootstrap=n_bootstrap, seed=BOOTSTRAP_SEED
    )
    by_year: dict[str, WindowStats] = {}
    for year, items in _group_by(observations, lambda item: item.event_date[:4]).items():
        by_year[year] = _simple_stats(items, block_length=block_length, n_bootstrap=n_bootstrap)
    by_cap: dict[str, WindowStats] = {}
    cap_groups = _group_by(
        [item for item in observations if item.cap_tier is not None],
        lambda item: str(int(item.cap_tier)),
    )
    for tier, items in cap_groups.items():
        by_cap[tier] = _simple_stats(items, block_length=block_length, n_bootstrap=n_bootstrap)
    return WindowStats(
        n=len(excess),
        mean=_mean(excess),
        median=_median(excess),
        std=_std(excess),
        ci=ci,
        effective_n=effective_n,
        by_year=by_year,
        by_cap_tier=by_cap,
    )


def _simple_stats(
    observations: Sequence[EventObservation], *, block_length: int, n_bootstrap: int
) -> WindowStats:
    excess = [float(item.excess) for item in observations]
    ci, effective_n = block_bootstrap(
        excess, block_length=block_length, n_bootstrap=n_bootstrap, seed=BOOTSTRAP_SEED
    )
    return WindowStats(
        n=len(excess),
        mean=_mean(excess),
        median=_median(excess),
        std=_std(excess),
        ci=ci,
        effective_n=effective_n,
    )


def _group_by(
    items: Iterable[EventObservation], key: Any
) -> dict[str, list[EventObservation]]:
    grouped: dict[str, list[EventObservation]] = {}
    for item in items:
        grouped.setdefault(str(key(item)), []).append(item)
    return grouped


def compute_event_study(
    events: Sequence[EventObservation],
    benchmarks: Sequence[Benchmark],
    *,
    cfg: BacktestConfig,
) -> EventStudyResult:
    """20/60 日 × 双基准超额分布：事件数/均值/中位数/标准差/CI/分年度/分市值组。"""
    if not events:
        raise BacktestError("事件研究无事件：不得产出结论（允许「无信号」但要先有事件集）")
    if not benchmarks:
        raise BacktestError("基准缺失：不得给出有效判定（R13）")
    block_length, n_bootstrap = _inference_cfg(cfg)
    windows: dict[str, dict[str, WindowStats]] = {}
    grouped: dict[tuple[int, str], list[EventObservation]] = {}
    for item in events:
        window = int(item.window)
        if window not in EVENT_WINDOWS:
            raise BacktestError(
                f"自定义窗口 {window} 未获确认（Q8）；MVP 只允许 {EVENT_WINDOWS}"
            )
        grouped.setdefault((window, str(item.benchmark_kind)), []).append(item)
    for window in sorted({int(item.window) for item in events}):
        per_benchmark: dict[str, WindowStats] = {}
        for benchmark in benchmarks:
            items = grouped.get((window, str(benchmark.kind)))
            if not items:
                raise BacktestError(
                    f"基准 {benchmark.kind!r} 在 {window} 日窗口无观测：不得给出有效判定（R13）"
                )
            per_benchmark[str(benchmark.kind)] = _window_stats(
                items, block_length=block_length, n_bootstrap=n_bootstrap
            )
        windows[str(window)] = per_benchmark
    return EventStudyResult(
        windows=windows,
        n_events=len({(item.code, item.event_date) for item in events}),
        inference_method="block_bootstrap",
        block_length=block_length,
        n_bootstrap=n_bootstrap,
    )


def insufficient_sample(
    result: EventStudyResult, *, cfg: BacktestConfig
) -> tuple[str, ...]:
    """返回样本不足的 `窗口/基准` 标签（R17 Scenario「事件数不足时不出结论」）。"""
    threshold = int(cfg.require("min_events"))
    labels: list[str] = []
    for window, per_benchmark in result.windows.items():
        for kind, stats in per_benchmark.items():
            if stats.n < threshold:
                labels.append(f"{window}d/{kind}")
    return tuple(labels)


# --------------------------------------------------------------------------
# R13 归因
# --------------------------------------------------------------------------


def attribution(
    returns: Sequence[float],
    factors: Mapping[str, Sequence[float]],
    benchmarks: Sequence[Benchmark],
) -> AttributionResult:
    """beta/规模/价值/动量 四项暴露与贡献 + 未解释部分（R13）。

    `returns` 须为**相对某一基准**的超额序列；双基准各调一次（本函数不混合基准）。
    """
    if not benchmarks:
        raise BacktestError("基准缺失：不得给出有效判定（R13 Scenario「缺失基准时不出结论」）")
    values = [float(value) for value in returns]
    if not values:
        raise BacktestError("归因收益序列为空")
    missing = [key for key in FACTOR_KEYS if key not in factors]
    if missing:
        raise BacktestError(f"归因因子缺失: {missing}（R13 要求四项齐全）")
    exposures: dict[str, float] = {}
    contributions: dict[str, float] = {}
    for key in FACTOR_KEYS:
        series = [float(value) for value in factors[key]]
        if len(series) != len(values):
            raise BacktestError(f"因子 {key} 长度 {len(series)} ≠ 收益长度 {len(values)}")
        variance = _variance(series)
        beta = _covariance(values, series) / variance if variance > 0 else 0.0
        exposures[key] = beta
        contributions[key] = beta * _mean(series)
    return AttributionResult(
        beta=exposures["beta"],
        size=exposures["size"],
        value=exposures["value"],
        momentum=exposures["momentum"],
        exposures=exposures,
        contributions=contributions,
        unexplained=_mean(values) - sum(contributions.values()),
    )


def _variance(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    avg = _mean(values)
    return sum((value - avg) ** 2 for value in values) / (n - 1)


def _covariance(left: Sequence[float], right: Sequence[float]) -> float:
    n = len(left)
    if n < 2:
        return 0.0
    left_mean = _mean(left)
    right_mean = _mean(right)
    return sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / (n - 1)


# --------------------------------------------------------------------------
# R16 部分池化
# --------------------------------------------------------------------------


def partial_pooling(
    estimates: Sequence[float], group_mean: float, *, shrink: float | None
) -> tuple[float, ...]:
    """个股估计向组均值收缩；`shrink` 缺省（None）即拒绝（KQ-3 未答复）。"""
    if shrink is None:
        raise MissingBacktestConfigError(
            "partial_pooling 缺 shrink：收缩强度未确认（KQ-3），禁止预埋默认值"
        )
    ratio = float(shrink)
    if not 0.0 <= ratio <= 1.0:
        raise BacktestError(f"shrink 非法: {shrink}（应在 [0,1]）")
    target = float(group_mean)
    return tuple((1.0 - ratio) * float(value) + ratio * target for value in estimates)


def group_percentiles(estimates: Sequence[float]) -> tuple[float, ...]:
    """组内分位（0..1，R16 只输出组内分位，不输出绝对收益预测）。"""
    values = [float(value) for value in estimates]
    n = len(values)
    if n == 0:
        return ()
    if n == 1:
        return (0.5,)
    ordered = sorted(range(n), key=lambda index: (values[index], index))
    percentiles = [0.0] * n
    for rank, index in enumerate(ordered):
        percentiles[index] = rank / float(n - 1)
    return tuple(percentiles)


# --------------------------------------------------------------------------
# R14 稳定性分档
# --------------------------------------------------------------------------


def _significant(stats: WindowStats) -> bool:
    lower, upper = stats.ci
    return lower > 0.0 or upper < 0.0


def stability(result: EventStudyResult, *, cfg: BacktestConfig) -> StabilityResult:
    """分年度 / 分市场状态 / 分市值组；仅一段显著→标注「仅在 X 段有效」（R14）。"""
    if not result.windows:
        return StabilityResult(
            by_year={}, by_market_state={}, by_cap_tier={}, scope_note="无窗口数据"
        )
    window_key = str(max(int(key) for key in result.windows))
    per_benchmark = result.windows[window_key]
    kind = "market_portfolio" if "market_portfolio" in per_benchmark else sorted(per_benchmark)[0]
    primary = per_benchmark[kind]

    by_year = dict(primary.by_year)
    by_cap = dict(primary.by_cap_tier)
    by_state: dict[str, WindowStats] = {}
    state_note = ""
    state_map = cfg.get("stability.market_state")
    if not state_map:
        state_note = "市场状态口径未定（KQ-7），该维度不参与判定"
    else:
        grouped: dict[str, list[WindowStats]] = {}
        for year, stats in by_year.items():
            state = str(dict(state_map).get(year, ""))
            if not state:
                state_note = f"市场状态映射缺 {year} 年（KQ-7）"
                continue
            grouped.setdefault(state, []).append(stats)
        for state, items in grouped.items():
            by_state[state] = _aggregate(items)

    notes: list[str] = []
    significant_years = [year for year, stats in by_year.items() if _significant(stats)]
    if len(significant_years) == 1:
        notes.append(f"仅在 {significant_years[0]} 年有效")
    elif not significant_years and by_year:
        notes.append("全期无显著分档")
    insufficient = [year for year, stats in by_year.items() if stats.n < MIN_GROUP_SIZE]
    if insufficient:
        notes.append("样本不足: " + ", ".join(sorted(insufficient)))
    if by_year and len(by_year) < MIN_YEARS:
        notes.append(f"跨度不足 {MIN_YEARS} 年")
    if state_note:
        notes.append(state_note)
    return StabilityResult(
        by_year=by_year,
        by_market_state=by_state,
        by_cap_tier=by_cap,
        scope_note="；".join(notes),
    )


def _aggregate(items: Sequence[WindowStats]) -> WindowStats:
    n = sum(item.n for item in items)
    mean = sum(item.mean * item.n for item in items) / n if n else 0.0
    return WindowStats(
        n=n,
        mean=mean,
        median=_median([item.median for item in items]),
        std=max((item.std for item in items), default=0.0),
        ci=(min(item.ci[0] for item in items), max(item.ci[1] for item in items)),
        effective_n=sum(item.effective_n for item in items),
    )
