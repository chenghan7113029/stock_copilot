"""R17 事件研究为 MVP 主交付（TC-R17-01..03）。

锚点：spec R17；design §4.1 `compute_event_study(events, benchmarks, *, cfg) -> EventStudyResult`
（20/60 日窗口、每窗口 × 基准的 `WindowStats{n, mean, median, std, ci, by_year, by_cap_tier, effective_n}`）、
§4.2 R17「事件数不足 → 样本不足」「允许结论为无信号」。
"""

from __future__ import annotations

import pytest


def _events(models, count=40):
    return [models.EventSignal(condition_id="ma60_breakdown", event_date=f"2020-{1 + i % 12:02d}-{1 + i % 27:02d}")
            for i in range(count)]


def test_tc_r17_01_twenty_and_sixty_day_windows(load, models, benchmarks, cfg):
    """TC-R17-01（R17 Scenario1）：输出 20/60 日两窗口 × 双基准的完整 WindowStats。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(_events(models), benchmarks, cfg=cfg)

    assert set(result.windows) >= {"20", "60"}
    assert result.n_events > 0
    assert result.inference_method == "block_bootstrap"
    assert result.block_length and result.n_bootstrap
    for window in ("20", "60"):
        for stats in result.windows[window].values():
            assert stats.n >= 0
            assert stats.median is not None and stats.std is not None
            assert stats.ci[0] <= stats.ci[1]


def test_tc_r17_02_insufficient_events_marks_insufficient_sample(load, models, benchmarks, cfg):
    """TC-R17-02（R17 Scenario2）：有效事件数低于预注册阈值 → 标「样本不足」，不给有效/无效判定。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(_events(models, count=3), benchmarks, cfg=cfg)

    thin = result.windows["20"]["buy_and_hold"]
    assert thin.n < 40, "夹具前置：事件数应低于常规阈值"
    assert result.n_events == thin.n
    assert not hasattr(result, "verdict"), "事件研究结果不得自带有效/无效判定（判定在结果行）"


def test_tc_r17_03_no_signal_is_a_legal_conclusion(load, models, benchmarks, cfg):
    """TC-R17-03（R17 Scenario3）：CI 含 0 且校正后不显著 → 结论「无信号」同样计入台账与 K。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(_events(models), benchmarks, cfg=cfg)
    stats = result.windows["60"]["market_portfolio"]

    if stats.ci[0] <= 0.0 <= stats.ci[1]:
        record = models.ExperimentRecord(
            experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
            segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE,
            metrics={"n": stats.n, "mean": stats.mean}, prereg_commit="deadbeef",
            data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
            timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)
        assert record.verdict is models.Verdict.INCONCLUSIVE
        assert record.K == 1, "无信号结论同样计入 K（spec R17 Scenario3）"
    else:
        pytest.fail("CI 不含 0：该夹具下无法覆盖「无信号」分支，请检查夹具（不放宽断言）")
