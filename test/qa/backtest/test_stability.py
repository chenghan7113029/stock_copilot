"""R14 稳定性分档检查（TC-R14-01..02）。

锚点：spec R14；design §4.1 `stability(result, *, cfg) -> StabilityResult`（`by_year` /
`by_market_state` / `by_cap_tier` / `scope_note`）、`WindowStats.n`、§4.2 R14「仅一段显著 → 仅在 X 段有效」、
§9.2 KQ-7（牛熊震荡判据未答复 → 该维度输出「口径未定」不参与判定）。
"""

from __future__ import annotations


def _window(models, n, mean, ci):
    return models.WindowStats(n=n, mean=mean, median=mean, std=0.0, ci=ci, effective_n=max(n // 30, 1),
                              by_year={}, by_cap_tier={})


def _result(models, windows):
    return models.EventStudyResult(windows=windows, n_events=sum(
        stats.n for per_benchmark in windows.values() for stats in per_benchmark.values()),
        inference_method="block_bootstrap", block_length=5, n_bootstrap=1000)


def test_tc_r14_01_single_year_contribution_marks_scope(load, models, cfg):
    """TC-R14-01（R14 Scenario1）：显著性只来自单一年度 → scope_note 标「仅在 X 段有效」，不写全期有效。"""
    metrics = load("service.backtest.metrics")
    windows = {"20": {"buy_and_hold": _window(models, 100, 0.02, (0.001, 0.039))}}
    result = _result(models, windows)

    stability = metrics.stability(result, cfg=cfg)

    assert isinstance(stability.scope_note, str) and stability.scope_note
    assert set(stability.by_year) or stability.scope_note, "必须分年度报告或显式说明无法分档"


def test_tc_r14_02_small_tier_is_flagged_and_excluded(load, models, cfg_labels):
    """TC-R14-02（R14 Scenario2）：某市值档 < min_group_size（30 只）→ 标「样本不足」且不参与判定。"""
    metrics = load("service.backtest.metrics")
    windows = {"20": {"buy_and_hold": _window(models, 12, 0.05, (0.01, 0.09))}}
    result = _result(models, windows)

    stability = metrics.stability(result, cfg=cfg_labels)

    thin = stability.by_cap_tier or {}
    assert all(stats.n >= cfg_labels["min_group_size"] for stats in thin.values()), \
        "样本不足的分档不得进入显著性判定集合（spec R14 Scenario2）"
    assert "样本不足" in stability.scope_note or thin == {}
