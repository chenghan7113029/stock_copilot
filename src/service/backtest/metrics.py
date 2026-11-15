"""指标 / 统计推断 / 归因 / 部分池化 / 稳定性（design §4.1，R5/R6/R13/R14/R16/R17）。

全部纯函数、确定性：
- 事件研究只消费 `EventObservation`（T2-fix-4：`EventSignal` 只判条件成立，不载收益）；
- 推断默认 block bootstrap（R6；禁止 iid t 检验下结论）；块长/重采样次数来自 cfg，缺值即拒绝；
- 固定随机种子只为可复现，不是业务口径。
"""

from __future__ import annotations

import math
import random
from typing import Mapping, Sequence

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.models import (
    AttributionResult,
    BacktestConfig,
    Benchmark,
    EventObservation,
    EventStudyResult,
    StabilityResult,
    WindowStats,
)

FACTOR_KEYS = ("size", "value", "momentum")
MARKET_BENCHMARK_KIND = "market_portfolio"
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


def window_excess(observation: EventObservation, window: int) -> float:
    """窗口累计超额 = 事件日后前 `window` 个交易日逐日超额之和（CAR）。"""
    if window < 1:
        raise MissingBacktestConfigError(f"窗口非法: {window}")
    if len(observation.excess_returns) < window:
        raise BacktestError(
            f"{observation.code} {observation.event_date} 的 excess_returns 不足 {window} 日"
        )
    return float(sum(observation.excess_returns[:window]))


def window_excess_series(
    observations: Sequence[EventObservation], window: int, benchmark_kind: str
) -> tuple[float, ...]:
    return tuple(
        window_excess(item, window)
        for item in observations
        if item.benchmark_kind == benchmark_kind
    )


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
    return ((_quantile(means, CI_LOWER_Q), _quantile(means, CI_UPPER_Q)), effective_n)


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
# R17/R13 事件研究（入 EventObservation，T2-fix-4）
# --------------------------------------------------------------------------


def _inference_cfg(cfg: BacktestConfig) -> tuple[int, int]:
    block_length = cfg.block_length
    n_bootstrap = cfg.n_bootstrap
    if block_length is None:
        raise MissingBacktestConfigError("回测配置缺值: block_length（KQ-2）")
    if n_bootstrap is None:
        raise MissingBacktestConfigError("回测配置缺值: n_bootstrap（KQ-2）")
    return int(block_length), int(n_bootstrap)


def _window_stats(
    values: Sequence[float], *, block_length: int, n_bootstrap: int
) -> WindowStats:
    ci, effective_n = block_bootstrap(
        values, block_length=block_length, n_bootstrap=n_bootstrap, seed=BOOTSTRAP_SEED
    )
    return WindowStats(
        n=len(values),
        mean=_mean(values),
        median=_median(values),
        std=_std(values),
        ci=ci,
        effective_n=effective_n,
    )


def _stats_with_breakdown(
    observations: Sequence[EventObservation],
    window: int,
    *,
    block_length: int,
    n_bootstrap: int,
) -> WindowStats:
    values = [window_excess(item, window) for item in observations]
    stats = _window_stats(values, block_length=block_length, n_bootstrap=n_bootstrap)
    by_year: dict[str, WindowStats] = {}
    grouped: dict[str, list[float]] = {}
    for item in observations:
        grouped.setdefault(item.event_date[:4], []).append(window_excess(item, window))
    for year, year_values in grouped.items():
        by_year[year] = _window_stats(
            year_values, block_length=block_length, n_bootstrap=n_bootstrap
        )
    return WindowStats(
        n=stats.n,
        mean=stats.mean,
        median=stats.median,
        std=stats.std,
        ci=stats.ci,
        effective_n=stats.effective_n,
        by_year=by_year,
        by_cap_tier={},
    )


def compute_event_study(
    observations: Sequence[EventObservation], *, cfg: BacktestConfig
) -> EventStudyResult:
    """按 benchmark_kind × window 聚合超额分布（R17/R13，T2-fix-4）。

    - 窗口来自 `cfg.windows`；每个观测的窗口超额 = `excess_returns[:window]` 之和（CAR）；
    - 块长 / 重采样次数来自 `cfg`（KQ-2），缺值即 `MissingBacktestConfigError`；
    - 入参只收 `EventObservation`，不直接读价格。
    """
    if not observations:
        raise BacktestError("事件研究无观测：不得产出结论（R17）")
    block_length, n_bootstrap = _inference_cfg(cfg)
    kinds = sorted({item.benchmark_kind for item in observations})
    windows: dict[str, dict[str, WindowStats]] = {}
    for window in cfg.windows:
        usable = [item for item in observations if len(item.excess_returns) >= window]
        if not usable:
            continue
        per_kind: dict[str, WindowStats] = {}
        for kind in kinds:
            items = [item for item in usable if item.benchmark_kind == kind]
            if not items:
                continue
            per_kind[kind] = _stats_with_breakdown(
                items, window, block_length=block_length, n_bootstrap=n_bootstrap
            )
        if per_kind:
            windows[str(window)] = per_kind
    if not windows:
        raise BacktestError("没有任何窗口有足够的事件收益：不得产出结论（R17）")
    return EventStudyResult(
        windows=windows,
        n_events=len({(item.code, item.event_date, item.condition_id) for item in observations}),
        inference_method="block_bootstrap",
        block_length=block_length,
        n_bootstrap=n_bootstrap,
    )


def insufficient_sample(
    result: EventStudyResult, *, cfg: BacktestConfig
) -> tuple[str, ...]:
    """返回样本不足的 `窗口/基准` 标签（R17 Scenario2）。

    `min_events` 是必须键但数值待 Q；为 None 时按「未达阈值」处理（不出结论）。
    """
    threshold = cfg.min_events
    labels: list[str] = []
    for window, per_benchmark in result.windows.items():
        for kind, stats in per_benchmark.items():
            if threshold is None or stats.n < int(threshold):
                labels.append(f"{window}d/{kind}")
    return tuple(labels)


# --------------------------------------------------------------------------
# R13 归因（T2-fix-4：beta 由 market_portfolio 回归推导，factors 固定三键）
# --------------------------------------------------------------------------


def attribution(
    returns: Sequence[float] | Mapping[str, Sequence[float]],
    factors: Mapping[str, Sequence[float]],
    benchmarks: Sequence[Benchmark],
) -> AttributionResult:
    """四项归因（R13）：beta 由 returns 对 market_portfolio 基准收益回归推导（不入参）。

    - `returns`：策略收益序列；或映射 `{"strategy": [...], "market_portfolio": [...]}`
      （基准收益随 returns 传入，不作为独立参数）；
    - `factors` 键集固定 `{"size","value","momentum"}`；缺任一键 → `MissingBacktestConfigError`；
    - `benchmarks` 缺 `market_portfolio` → 归因不可判定（抛 `BacktestError`，结论 INCONCLUSIVE）。
    """
    missing = [key for key in FACTOR_KEYS if key not in factors]
    if missing:
        raise MissingBacktestConfigError(f"attribution 缺因子键: {missing}（R13 固定三因子）")
    if not any(benchmark.kind == MARKET_BENCHMARK_KIND for benchmark in benchmarks):
        raise BacktestError(
            "attribution 缺 market_portfolio 基准：归因不可判定（INCONCLUSIVE，R13）"
        )
    strategy, market = _split_returns(returns)
    if len(strategy) != len(market):
        raise BacktestError("strategy 与 market_portfolio 收益长度不一致（R13）")
    if not strategy:
        raise BacktestError("归因收益序列为空（R13）")
    exposures: dict[str, float] = {}
    contributions: dict[str, float] = {}
    market_variance = _variance(market)
    beta = _covariance(strategy, market) / market_variance if market_variance > 0 else 0.0
    exposures["beta"] = beta
    contributions["beta"] = beta * _mean(market)
    for key in FACTOR_KEYS:
        series = [float(value) for value in factors[key]]
        if len(series) != len(strategy):
            raise BacktestError(f"因子 {key} 长度 {len(series)} ≠ 收益长度 {len(strategy)}")
        variance = _variance(series)
        exposure = _covariance(strategy, series) / variance if variance > 0 else 0.0
        exposures[key] = exposure
        contributions[key] = exposure * _mean(series)
    return AttributionResult(
        beta=exposures["beta"],
        size=exposures["size"],
        value=exposures["value"],
        momentum=exposures["momentum"],
        exposures=exposures,
        contributions=contributions,
        unexplained=_mean(strategy) - sum(contributions.values()),
    )


def _split_returns(
    returns: Sequence[float] | Mapping[str, Sequence[float]],
) -> tuple[list[float], list[float]]:
    if isinstance(returns, Mapping):
        strategy = returns.get("strategy")
        market = returns.get(MARKET_BENCHMARK_KIND) or returns.get("market")
        if strategy is None or market is None:
            raise BacktestError(
                "attribution 缺市场基准收益：returns 需含 strategy 与 market_portfolio（R13）"
            )
        return [float(value) for value in strategy], [float(value) for value in market]
    raise BacktestError(
        "attribution 需要 returns 映射（strategy + market_portfolio）："
        "beta 必须由市场基准回归推导（T2-fix-4）"
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
    kind = MARKET_BENCHMARK_KIND if MARKET_BENCHMARK_KIND in per_benchmark else sorted(per_benchmark)[0]
    primary = per_benchmark[kind]

    by_year = dict(primary.by_year)
    by_cap = dict(primary.by_cap_tier)
    by_state: dict[str, WindowStats] = {}
    notes: list[str] = []
    # KQ-7 未答复：市场状态口径未定，该维度不参与判定
    notes.append("市场状态口径未定（KQ-7），该维度不参与判定")

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
    return StabilityResult(
        by_year=by_year,
        by_market_state=by_state,
        by_cap_tier=by_cap,
        scope_note="；".join(notes),
    )
