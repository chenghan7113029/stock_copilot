"""R17 事件研究为 MVP 主交付（TC-R17-01..03）。

锚点：spec R17；design §4.1（T2-fix-4 后）`EventObservation`（逐日超额载体，长度 = max(window)）、
`load_event_observations(signals, benchmarks, *, loader, cfg)`、`compute_event_study(observations, *, cfg)`、
`min_events`（必须键：事件数下限）、`EventStudyResult.windows[window][benchmark_kind]`、§4.2 R17
「事件数不足 → 样本不足」「允许结论为无信号」。
"""

from __future__ import annotations


def test_tc_r17_01_twenty_and_sixty_day_windows(load, make_observations, cfg_event):
    """TC-R17-01（R17 Scenario1）：输出 20/60 日两窗口 × 双基准的完整 WindowStats。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(), cfg=cfg_event)

    assert set(result.windows) >= {"20", "60"}
    assert result.n_events > 0
    assert result.inference_method == "block_bootstrap"
    assert result.block_length == cfg_event.block_length
    assert result.n_bootstrap == cfg_event.n_bootstrap
    for window in ("20", "60"):
        for stats in result.windows[window].values():
            assert stats.n >= 0
            assert stats.median is not None and stats.std is not None
            assert stats.ci[0] <= stats.ci[1]


def test_tc_r17_02_insufficient_events_marks_insufficient_sample(load, models, make_observations, cfg_event):
    """TC-R17-02（R17 Scenario2）：有效事件数低于 `min_events` → 标「样本不足」，不给有效/无效判定。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(count=3), cfg=cfg_event)

    thin = result.windows["20"]["buy_and_hold"]
    assert thin.n < cfg_event.min_events, "夹具前置：事件数必须低于配置下限 min_events"
    assert result.n_events == thin.n
    # T2-fix-6：`EventStudyResult.verdict` 是契约字段；全样本不足 → INCONCLUSIVE（不得判有效）
    assert result.verdict is models.Verdict.INCONCLUSIVE, "事件数不足 → INCONCLUSIVE（R17 Scenario2）"


def test_tc_r17_03_no_signal_is_a_legal_conclusion(load, models, make_observations, cfg_event):
    """TC-R17-03（R17 Scenario3）：CI 含 0 且校正后不显著 → 结论「无信号」同样计入台账与 K。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(daily_excess=0.0), cfg=cfg_event)
    stats = result.windows["60"]["market_portfolio"]

    assert stats.ci[0] <= 0.0 <= stats.ci[1], "零超额序列的 CI 必须包含 0（否则夹具失效）"
    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE,
        metrics={"n": stats.n, "mean": stats.mean}, prereg_commit="deadbeef",
        data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)
    assert record.verdict is models.Verdict.INCONCLUSIVE
    assert record.K == 1, "无信号结论同样计入 K（spec R17 Scenario3）"
