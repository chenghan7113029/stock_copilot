"""R13 基准对比与因子归因（TC-R13-01..03）。

锚点：spec R13；design §4.1（T2-fix-4 后）`EventObservation{code,event_date,condition_id,benchmark_kind,
excess_returns}`、`compute_event_study(observations, *, cfg)`、`EventStudyResult.windows[window][benchmark_kind]`、
`attribution(returns, factors: dict[str, Sequence[float]], benchmarks)`：
beta 由 `market_portfolio` 基准回归**推导**（不入参）、`factors` 键集固定 `{size,value,momentum}`、
缺因子键 → `MissingBacktestConfigError`、缺 `market_portfolio` → 归因 `INCONCLUSIVE`。
"""

from __future__ import annotations

import pytest


def test_tc_r13_01_event_study_reports_both_benchmarks(load, make_observations, cfg_event):
    """TC-R13-01（R13 Scenario1）：结果同时给「相对买入持有」与「相对市场组合」两套超额统计。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(), cfg=cfg_event)

    for window in ("20", "60"):
        assert window in result.windows, f"缺少 {window} 日窗口"
        assert set(result.windows[window]) == {"buy_and_hold", "market_portfolio"}
        for stats in result.windows[window].values():
            assert stats.ci[0] <= stats.mean <= stats.ci[1]
            assert stats.n >= 0 and stats.effective_n >= 0


def test_tc_r13_02_missing_benchmark_is_inconclusive(load, models, make_observations, cfg_event):
    """TC-R13-02（R13 Scenario2）：无基准 → 不得产出超额统计，实验判定只能 INCONCLUSIVE。

    同时覆盖 `attribution` 的契约：只给 `buy_and_hold`（缺 `market_portfolio`）→ 归因 INCONCLUSIVE。
    """
    metrics = load("service.backtest.metrics")
    single = make_observations(benchmark_kinds=("buy_and_hold",))
    result = metrics.compute_event_study((), cfg=cfg_event)  # 空观测：无基准可聚合

    assert result.windows["20"] == {} and result.windows["60"] == {}, "无基准时不得产出超额统计"
    assert single and all(obs.benchmark_kind == "buy_and_hold" for obs in single)

    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE, metrics={},
        prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)
    assert record.verdict is models.Verdict.INCONCLUSIVE
    assert record.verdict is not models.Verdict.VALID, "基准缺失的实验不得标为有效（spec R13 Scenario2）"

    benchmarks = [models.Benchmark(kind="buy_and_hold", label="买入持有")]
    with pytest.raises(models.MissingBacktestConfigError):
        metrics.attribution([0.01, -0.02, 0.0], {"size": [0.1, 0.0, -0.1],
                                                 "value": [0.0, 0.1, -0.1],
                                                 "momentum": [0.2, -0.1, 0.0]}, benchmarks)


def test_tc_r13_03_attribution_has_four_factor_contributions(load, benchmarks):
    """TC-R13-03（R13 Scenario3）：beta（推导）+ 规模/价值/动量三项因子，贡献合计 + 未解释 = 全部收益。"""
    metrics = load("service.backtest.metrics")
    returns = [0.01, -0.02, 0.015, 0.0, -0.005]
    factors = {"size": [0.2, -0.1, 0.0, 0.1, -0.2], "value": [0.1, 0.0, -0.1, 0.2, 0.05],
               "momentum": [0.3, 0.1, -0.2, 0.0, 0.1]}

    result = metrics.attribution(returns, factors, benchmarks)

    assert set(result.exposures) == {"beta", "size", "value", "momentum"}
    assert set(result.contributions) == {"beta", "size", "value", "momentum"}
    assert isinstance(result.unexplained, float)
    assert pytest.approx(sum(result.contributions.values()) + result.unexplained,
                         abs=1e-6) == pytest.approx(1.0, abs=1e-6)
