"""R4 样本外一次性烧毁（TC-R04-01..03）。

锚点：spec R4；design §4.1（T2-fix-4 后）`mark_burnt` = **追加执行行**
`RunRecord(status=RUNNING, reason="样本外已烧毁", hypothesis_id, experiment_id, at)`（append-only、不可撤销）；
`ExperimentRecord.burnt` 是结果行 append 时固化的冗余快照；`export_ledger` 的 `burnt` 由「是否存在
`reason="样本外已烧毁"` 的执行行」派生；`assert_not_burnt` 二次请求抛 `RegistryImmutableError`。
"""

from __future__ import annotations

import json

import pytest

BURNT_REASON = "样本外已烧毁"


def _record(models, experiment_id, *, segment=None, burnt=False, **overrides):
    fields = dict(
        experiment_id=experiment_id, hypothesis_id="hyp-001", params={"ma_days": 60},
        segment=segment or models.Segment.OUT_OF_SAMPLE, K=1, verdict=models.Verdict.INCONCLUSIVE,
        metrics={}, prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None, burnt=burnt,
    )
    fields.update(overrides)
    return models.ExperimentRecord(**fields)


def _burnt_markers(run_rows, registry_path, hypothesis_id="hyp-001"):
    return [row for row in run_rows(registry_path)
            if row.get("reason") == BURNT_REASON and row.get("hypothesis_id") == hypothesis_id]


def test_tc_r04_01_first_use_marks_burnt_and_exports(registry, models, results_dir, ledger_rows, run_rows,
                                                     registry_path):
    """TC-R04-01（R4 Scenario1）：首次用样本外 → 追加烧毁执行行（唯一）+ 导出 `burnt=True` + 结果 JSON 落盘。"""
    experiment_id = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, experiment_id))
    registry.mark_burnt("hyp-001", experiment_id)

    markers = _burnt_markers(run_rows, registry_path)
    assert len(markers) == 1, "烧毁标记必须是唯一一条 append-only 执行行（T2-fix-4）"
    assert markers[0]["experiment_id"] == experiment_id
    assert markers[0]["at"], "烧毁执行行须带时间戳（R4）"

    burnt_rows = [row for row in ledger_rows(hypothesis_id="hyp-001") if row.burnt]
    assert len(burnt_rows) == 1, "导出 burnt 由烧毁执行行派生（额度已用尽）"
    assert burnt_rows[0].experiment_id == experiment_id

    written = registry.write_result(experiment_id, {"verdict": "inconclusive"})
    assert written.parent == results_dir
    assert json.loads(written.read_text(encoding="utf-8"))["verdict"] == "inconclusive"


def test_tc_r04_02_second_out_of_sample_request_rejected(registry, models, run_rows, registry_path):
    """TC-R04-02（R4 Scenario2）：同实验二次请求（换参数/换指标）→ RegistryImmutableError 并留痕。"""
    experiment_id = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, experiment_id))
    registry.mark_burnt("hyp-001", experiment_id)
    immutable = _exception(registry, "RegistryImmutableError")

    for _variant in ({"params": {"ma_days": 61}}, {"metrics": ["sharpe"]}):
        with pytest.raises(immutable):
            registry.assert_not_burnt("hyp-001", models.Segment.OUT_OF_SAMPLE)

    assert len(_burnt_markers(run_rows, registry_path)) == 1, "标记唯一且不可撤销（append-only，不重复写）"


def test_tc_r04_03_new_experiment_has_independent_quota(registry, models, ledger_rows, run_rows, registry_path):
    """TC-R04-03（R4 Scenario3）：新假设拥有独立额度，不重置也不共享旧假设的烧毁标记。"""
    first = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, first))
    registry.mark_burnt("hyp-001", first)

    second = registry.next_experiment_id("hyp-002")
    registry.append(_record(models, second, hypothesis_id="hyp-002", burnt=False))

    registry.assert_not_burnt("hyp-002", models.Segment.OUT_OF_SAMPLE)  # 新假设首次 → 允许

    assert len(_burnt_markers(run_rows, registry_path, "hyp-002")) == 0
    assert len(_burnt_markers(run_rows, registry_path, "hyp-001")) == 1
    assert len([row for row in ledger_rows(hypothesis_id="hyp-002") if row.burnt]) == 0
    assert len([row for row in ledger_rows(hypothesis_id="hyp-001") if row.burnt]) == 1


def _exception(registry, name):
    """按 design §4.1 异常清单，从被测异常模块取具体异常类。"""
    module = __import__(registry.__class__.__module__, fromlist=[name])
    return getattr(module, name)
