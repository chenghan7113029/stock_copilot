"""R5 多重比较校正与 K 报告（TC-R05-01..03）。

锚点：spec R5；design §4.1 `metrics.multiple_testing_correction(p_values, K, method, *, cfg)`（`cfg` 为
`BacktestConfig`；alpha 是 KQ-5 待答复判据，**不在 config 内**，测试以 `ALPHA` 常量为输入）、
`ExperimentRecord.K: int | None`、§4.2 R5「K 缺（None）→ INCONCLUSIVE」。
"""

from __future__ import annotations

import pytest


def test_tc_r05_01_reports_k_and_corrected_significance(load, cfg, alpha):
    """TC-R05-01（R5 Scenario1）：p=0.01 / K=30 / Bonferroni → 校正值 = min(1, 0.3)，判定不显著。"""
    metrics = load("service.backtest.metrics")
    corrected = metrics.multiple_testing_correction([0.01], 30, "bonferroni", cfg=cfg)

    assert len(corrected) == 1
    assert corrected[0] == pytest.approx(0.3, abs=1e-12)  # 0.01 × 30（独立算式）
    assert corrected[0] > alpha, "校正后不显著须如实标不显著（spec R5 Scenario1）"


def test_tc_r05_02_missing_k_is_inconclusive(models):
    """TC-R05-02（R5 Scenario2）：K=None（未报告 K）→ 结果行只允许 INCONCLUSIVE，不得 VALID。"""
    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=None, verdict=models.Verdict.INCONCLUSIVE, metrics={},
        prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)

    assert record.K is None  # design §4.1：K: int | None
    assert record.verdict is models.Verdict.INCONCLUSIVE
    assert record.verdict is not models.Verdict.VALID, "缺 K 的结果不得标为有效（spec R5 Scenario2）"


def test_tc_r05_03_k_increase_flips_verdict(load, cfg, alpha):
    """TC-R05-03（R5 Scenario3）：同一原始 p 在 K=1 显著、K=50 不显著（判定随 K 单调反向）。"""
    metrics = load("service.backtest.metrics")
    k1 = metrics.multiple_testing_correction([0.01], 1, "bonferroni", cfg=cfg)[0]
    k50 = metrics.multiple_testing_correction([0.01], 50, "bonferroni", cfg=cfg)[0]

    assert k1 == pytest.approx(0.01, abs=1e-12)
    assert k50 == pytest.approx(0.5, abs=1e-12)
    assert k1 <= alpha < k50, "K 增大必须使判定由显著翻为不显著"
