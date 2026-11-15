"""T2.12/T2.13/T2.14 指标：事件研究 / block bootstrap / 多重比较 / 归因 / 部分池化 / 稳定性。"""

from __future__ import annotations

import math

import pytest

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.metrics import (
    attribution,
    block_bootstrap,
    compute_event_study,
    group_percentiles,
    insufficient_sample,
    multiple_testing_correction,
    partial_pooling,
    stability,
)
from service.backtest.models import Benchmark, EventObservation, WindowStats

BENCHMARKS = (Benchmark(kind="buy_and_hold", label="买入持有"), Benchmark(kind="market_portfolio", label="市场组合"))


def observation(code="000001", date="2016-06-01", window=20, kind="buy_and_hold", excess=-0.02, tier=0):
    return EventObservation(
        code=code, event_date=date, window=window, benchmark_kind=kind, excess=excess, cap_tier=tier
    )


def make_events(count=5):
    events = []
    for index in range(count):
        for window in (20, 60):
            for benchmark in BENCHMARKS:
                events.append(
                    observation(
                        code=f"{index:06d}",
                        date=f"2016-0{index + 1}-01",
                        window=window,
                        kind=benchmark.kind,
                        excess=-0.02 - index * 0.001,
                        tier=index % 2,
                    )
                )
    return events


def test_event_study_two_windows_two_benchmarks(cfg):
    result = compute_event_study(make_events(), BENCHMARKS, cfg=cfg)
    assert set(result.windows) == {"20", "60"}
    for window in ("20", "60"):
        assert set(result.windows[window]) == {"buy_and_hold", "market_portfolio"}
        stats = result.windows[window]["buy_and_hold"]
        assert stats.n == 5
        assert stats.effective_n == math.ceil(5 / 5)
        assert set(stats.by_year) == {"2016"}
        assert set(stats.by_cap_tier) == {"0", "1"}
    assert result.n_events == 5
    assert result.inference_method == "block_bootstrap"
    assert result.block_length == 5
    assert result.n_bootstrap == 200


def test_event_study_custom_window_rejected(cfg):
    events = make_events() + [observation(window=120)]
    with pytest.raises(BacktestError) as exc:
        compute_event_study(events, BENCHMARKS, cfg=cfg)
    assert "窗口" in str(exc.value)


def test_event_study_missing_benchmark_rejected(cfg):
    with pytest.raises(BacktestError):
        compute_event_study(make_events(), (), cfg=cfg)


def test_insufficient_sample_flags(cfg):
    events = [observation(window=20, kind="buy_and_hold", excess=-0.02)]
    result = compute_event_study(events, (Benchmark("buy_and_hold", "买入持有"),), cfg=cfg)
    assert insufficient_sample(result, cfg=cfg)


def test_block_bootstrap_reports_effective_n_and_is_deterministic():
    values = [-0.02, -0.03, -0.01, -0.02, -0.04, -0.02]
    first, effective_n = block_bootstrap(values, block_length=2, n_bootstrap=300, seed=0)
    second, _ = block_bootstrap(values, block_length=2, n_bootstrap=300, seed=0)
    assert effective_n == 3
    assert first == second
    assert first[0] <= first[1]


def test_multiple_testing_k_flips_verdict(cfg):
    k1 = multiple_testing_correction([0.01], 1, "bonferroni", cfg=cfg)[0]
    k50 = multiple_testing_correction([0.01], 50, "bonferroni", cfg=cfg)[0]
    assert k1 == pytest.approx(0.01)
    assert k50 == pytest.approx(0.5)
    assert k1 <= 0.05 < k50


def test_missing_k_cannot_be_corrected(cfg):
    with pytest.raises(BacktestError):
        multiple_testing_correction([0.01], None, "bonferroni", cfg=cfg)
    with pytest.raises(BacktestError):
        multiple_testing_correction([0.01], 0, "bonferroni", cfg=cfg)


def test_attribution_four_exposures():
    returns = [0.01, 0.02, -0.01, 0.03, 0.0]
    factors = {
        "beta": [1.0, 1.0, 1.0, 1.0, 1.0],
        "size": [0.0, 1.0, 0.0, 1.0, 0.0],
        "value": [1.0, 0.0, 1.0, 0.0, 1.0],
        "momentum": [0.5] * 5,
    }
    result = attribution(returns, factors, BENCHMARKS)
    assert set(result.exposures) == {"beta", "size", "value", "momentum"}
    assert result.beta == 0.0  # 常量因子方差为 0 → 暴露按 0 处理（不猜斜率）
    assert set(result.contributions) == {"beta", "size", "value", "momentum"}
    assert math.isfinite(result.unexplained)


def test_attribution_requires_benchmark():
    with pytest.raises(BacktestError):
        attribution([0.01], {"beta": [1.0], "size": [1.0], "value": [1.0], "momentum": [1.0]}, ())


def test_partial_pooling_requires_shrink():
    with pytest.raises(MissingBacktestConfigError):
        partial_pooling([1.0], 2.0, shrink=None)


def test_partial_pooling_and_percentiles():
    shrunk = partial_pooling([1.0, 3.0], 2.0, shrink=0.5)
    assert shrunk == (1.5, 2.5)
    assert group_percentiles([10.0, 20.0, 30.0]) == (0.0, 0.5, 1.0)


def year_stats(mean, ci, n=100):
    return WindowStats(n=n, mean=mean, median=mean, std=0.02, ci=ci, effective_n=n // 5)


def test_stability_scope_note_single_year(cfg):
    from service.backtest.models import EventStudyResult

    result = EventStudyResult(
        windows={
            "60": {
                "market_portfolio": WindowStats(
                    n=300,
                    mean=-0.02,
                    median=-0.02,
                    std=0.02,
                    ci=(-0.03, -0.01),
                    effective_n=60,
                    by_year={"2015": year_stats(-0.05, (-0.08, -0.02)), "2016": year_stats(0.0, (-0.01, 0.01))},
                    by_cap_tier={"0": year_stats(-0.02, (-0.03, -0.01))},
                )
            }
        },
        n_events=300,
        inference_method="block_bootstrap",
    )
    stability_result = stability(result, cfg=cfg)
    assert "仅在 2015 年有效" in stability_result.scope_note
    assert "市场状态口径未定" in stability_result.scope_note
    assert stability_result.by_market_state == {}
