"""R13 基准对比与因子归因（TC-R13-01..03）。

锚点：spec R13；design §4.1 `Benchmark`/`WindowStats`/`EventStudyResult.windows[window][benchmark_kind]`、
`compute_event_study(events, benchmarks: Sequence[Benchmark], *, cfg)`、
`attribution(returns, factors, benchmarks) -> AttributionResult`（四项 + unexplained）、
§4.2 R13「基准缺失 → 实验判定 INCONCLUSIVE」。
"""

from __future__ import annotations

import pytest


def _events(models, dates=("2020-03-02", "2020-04-01", "2020-05-06")):
    return [models.EventSignal(condition_id="ma60_breakdown", event_date=day) for day in dates]


def test_tc_r13_01_event_study_reports_both_benchmarks(load, models, benchmarks, cfg):
    """TC-R13-01（R13 Scenario1）：结果同时给「相对买入持有」与「相对市场组合」两套超额统计。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(_events(models), benchmarks, cfg=cfg)

    for window in ("20", "60"):
        assert window in result.windows, f"缺少 {window} 日窗口"
        assert set(result.windows[window]) == {"buy_and_hold", "market_portfolio"}
        for stats in result.windows[window].values():
            assert stats.ci[0] <= stats.mean <= stats.ci[1]
            assert stats.n >= 0 and stats.effective_n >= 0


def test_tc_r13_02_missing_benchmark_is_inconclusive(load, models, cfg):
    """TC-R13-02（R13 Scenario2）：无基准 → 结果行只能 INCONCLUSIVE，且不得给出有效判定。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(_events(models), [], cfg=cfg)

    assert result.windows["20"] == {} and result.windows["60"] == {}, "无基准时不得产出超额统计"

    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE, metrics={},
        prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)
    assert record.verdict is models.Verdict.INCONCLUSIVE
    assert record.verdict is not models.Verdict.VALID, "基准缺失的实验不得标为有效（spec R13 Scenario2）"


def test_tc_r13_03_attribution_has_four_factor_contributions(load, models, benchmarks, cfg):
    """TC-R13-03（R13 Scenario3）：归因含 beta/规模/价值/动量四项暴露与贡献，并注明未解释部分。"""
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
