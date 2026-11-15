"""T2.15/T2.16 台账：append-only + 执行行/结果行 + 哈希 + 烧毁 + K + 导出。"""

from __future__ import annotations

import json

import pytest

from common.exceptions import (
    BacktestError,
    RegistryCorruptedError,
    RegistryImmutableError,
)
from service.backtest.models import (
    AdjustMode,
    ExperimentRecord,
    LedgerExportRow,
    PreregistrationSpec,
    RunRecord,
    RunStatus,
    Segment,
    Verdict,
)
from service.backtest.registry import write_preregistration_file


def result_record(registry, hypothesis_id="hid", params=None, burnt=False, experiment_id=None, parent=None):
    identifier = experiment_id or registry.next_experiment_id(hypothesis_id)
    return ExperimentRecord(
        experiment_id=identifier,
        hypothesis_id=hypothesis_id,
        params=params or {"ma": 60},
        segment=Segment.OUT_OF_SAMPLE if burnt else Segment.VALIDATION,
        K=1,
        verdict=Verdict.INCONCLUSIVE,
        metrics={"mean": -0.01},
        prereg_commit="deadbeef",
        data_version="test-v1",
        adjust_mode=AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-01T00:00:00", "finished_at": "2026-01-01T00:00:01"},
        burnt=burnt,
        parent_experiment_id=parent,
    )


def test_two_executions_two_rows_with_sequential_ids(registry):
    first = result_record(registry)
    registry.append(first)
    second = result_record(registry)
    registry.append(second)
    assert first.experiment_id == "hid-0001"
    assert second.experiment_id == "hid-0002"
    assert len(registry.result_rows()) == 2


def test_tampered_row_rejected(registry):
    registry.append(result_record(registry))
    path = registry.store_path
    lines = path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["K"] = 99
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(RegistryCorruptedError) as exc:
        registry.rows()
    assert "损坏" in str(exc.value) or "哈希" in str(exc.value)


def test_duplicate_experiment_id_rejected(registry):
    record = result_record(registry)
    registry.append(record)
    with pytest.raises(RegistryImmutableError):
        registry.append(record)


def test_changed_params_requires_new_experiment_with_parent(registry):
    registry.append(result_record(registry, params={"ma": 60}))
    changed = result_record(registry, params={"ma": 61})
    with pytest.raises(RegistryImmutableError):
        registry.append(changed)
    parented = ExperimentRecord(
        **{**changed.__dict__, "experiment_id": "hid-0002", "parent_experiment_id": "hid-0001"}
    )
    registry.append(parented)
    assert registry.get("hid-0002").parent_experiment_id == "hid-0001"


def test_run_record_rejected_and_failed_are_persisted(registry):
    registry.append_run(
        RunRecord(
            run_id="hid-0001",
            status=RunStatus.REJECTED,
            at="2026-01-01T00:00:00",
            hypothesis_id="hid",
            reason="预注册缺失",
        )
    )
    registry.append_run(
        RunRecord(
            run_id="hid-0002",
            status=RunStatus.FAILED,
            at="2026-01-01T00:00:01",
            hypothesis_id="hid",
            reason="数据缺口",
        )
    )
    rows = registry.rows()
    assert [row.status for row in rows] == [RunStatus.REJECTED, RunStatus.FAILED]
    assert registry.result_rows() == ()


def test_validate_preregistration_reports_missing_field_names(registry):
    spec = PreregistrationSpec(
        hypothesis_id="hid",
        statement="",
        params={},
        metrics=(),
        segments=(),
        benchmarks=(),
        correction_method="bonferroni",
        k_definition="",
        created_at="",
    )
    with pytest.raises(BacktestError) as exc:
        registry.validate_preregistration(spec)
    message = str(exc.value)
    assert "statement" in message
    assert "k_definition" in message


def test_out_of_sample_burn_once_and_rejection_traced(registry):
    registry.assert_not_burnt("hid", Segment.OUT_OF_SAMPLE)  # 首次允许
    record = result_record(registry)
    registry.append(record)
    assert registry.mark_burnt("hid", record.experiment_id) is None  # T2-fix-4：追加执行行
    markers = [
        row
        for row in registry.rows()
        if isinstance(row, RunRecord) and row.reason == "样本外已烧毁"
    ]
    assert len(markers) == 1
    assert markers[0].status is RunStatus.RUNNING
    assert markers[0].experiment_id == record.experiment_id
    assert markers[0].hypothesis_id == "hid"
    with pytest.raises(RegistryImmutableError) as exc:
        registry.assert_not_burnt("hid", Segment.OUT_OF_SAMPLE)
    assert "样本外已烧毁" in str(exc.value)
    rejected = [
        row
        for row in registry.rows()
        if isinstance(row, RunRecord) and row.status is RunStatus.REJECTED
    ]
    assert len(rejected) == 1
    exported = registry.export_ledger(hypothesis_id="hid")
    assert sum(1 for row in exported if row.burnt) == 1  # 导出 burnt 由执行行派生


def test_new_hypothesis_has_independent_burn(registry):
    registry.append(result_record(registry, hypothesis_id="h1", burnt=True))
    registry.assert_not_burnt("h2", Segment.OUT_OF_SAMPLE)  # 新假设独立额度


def test_burn_marker_is_idempotent_for_same_experiment(registry):
    record = result_record(registry)
    registry.append(record)
    registry.mark_burnt("hid", record.experiment_id)
    registry.mark_burnt("hid", record.experiment_id)  # 幂等
    markers = [
        row
        for row in registry.rows()
        if isinstance(row, RunRecord) and row.reason == "样本外已烧毁"
    ]
    assert len(markers) == 1
    other = result_record(registry)
    registry.append(other)
    with pytest.raises(RegistryImmutableError):
        registry.mark_burnt("hid", other.experiment_id)


def test_cumulative_k_from_components(registry):
    assert registry.cumulative_K({"k_components": [1, 2, 3]}) == 6
    with pytest.raises(BacktestError):
        registry.cumulative_K({"hypothesis_id": "hid"})


def test_cumulative_k_sums_result_rows(registry):
    registry.append(result_record(registry))
    registry.append(result_record(registry))
    assert registry.cumulative_K("hid") == 2


def test_write_result_to_injected_results_dir(registry, tmp_path):
    path = registry.write_result("hid-0001", {"mean": -0.01})
    assert path == tmp_path / "results" / "hid-0001.json"
    assert json.loads(path.read_text(encoding="utf-8"))["mean"] == -0.01


def test_export_ledger_13_fields_and_statement_from_prereg(registry, tmp_path):
    prereg_dir = tmp_path / "preregistrations"
    spec = PreregistrationSpec(
        hypothesis_id="hid",
        statement="跌破 MA60 后卖出会跑输持有",
        params={"ma": 60},
        metrics=("mean_excess",),
        segments=(Segment.VALIDATION,),
        benchmarks=("buy_and_hold", "market_portfolio"),
        correction_method="bonferroni",
        k_definition="规则×参数网格",
        created_at="2026-01-01T00:00:00",
    )
    write_preregistration_file(spec, prereg_dir / "hid.yaml")
    registry.append(result_record(registry))
    rows = registry.export_ledger(hypothesis_id="hid", prereg_dir=prereg_dir)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, LedgerExportRow)
    assert row.statement == spec.statement
    assert row.segments == ("validation",)
    assert row.run_status is None  # 无执行行时留空（不伪造状态）
    assert set(row.__dict__) == {
        "experiment_id",
        "hypothesis_id",
        "statement",
        "params",
        "segments",
        "K",
        "metrics",
        "verdict",
        "burnt",
        "prereg_commit",
        "run_status",
        "data_version",
        "adjust_mode",
    }


def test_export_ledger_missing_prereg_uses_placeholder(registry, tmp_path):
    registry.append(result_record(registry))
    with pytest.warns(RuntimeWarning):
        rows = registry.export_ledger(hypothesis_id="hid", prereg_dir=tmp_path / "missing")
    assert rows[0].statement == "[prereg-missing]"


def test_export_ledger_run_only_row_has_no_verdict(registry, tmp_path):
    prereg_dir = tmp_path / "preregistrations"
    spec = PreregistrationSpec(
        hypothesis_id="hid",
        statement="假设陈述",
        params={"ma": 60},
        metrics=("mean_excess",),
        segments=(Segment.VALIDATION,),
        benchmarks=("buy_and_hold",),
        correction_method="bonferroni",
        k_definition="规则",
        created_at="2026-01-01T00:00:00",
    )
    write_preregistration_file(spec, prereg_dir / "hid.yaml")
    registry.append_run(
        RunRecord(
            run_id="hid-0001",
            experiment_id="hid-0001",
            hypothesis_id="hid",
            status=RunStatus.FAILED,
            at="2026-01-01T00:00:00",
            reason="数据缺口",
        )
    )
    rows = registry.export_ledger(hypothesis_id="hid", prereg_dir=prereg_dir)
    assert len(rows) == 1
    assert rows[0].verdict is None
    assert rows[0].run_status == "failed"
    assert rows[0].params == {"ma": 60}
