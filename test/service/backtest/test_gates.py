"""T2.18 三级门禁状态机（T2-fix-4：`GateStateMachine(registry, *, cfg)` + gate_criteria 判据）。"""

from __future__ import annotations

import json

import pytest

from common.exceptions import GateSkipError, MissingBacktestConfigError
from service.backtest.gates import GateStateMachine
from service.backtest.models import BacktestConfig, GateStage, RunStatus
from service.backtest.registry import ExperimentRegistry


class Clock:
    def __init__(self, value="2026-01-01T00:00:00"):
        self.value = value

    def __call__(self) -> str:
        return self.value


def make_registry(tmp_path, clock):
    return ExperimentRegistry(
        tmp_path / "registry.ndjson",
        clock=clock,
        data_version="test-v1",
        results_dir=tmp_path / "results",
    )


def make_machine(tmp_path, cfg, clock=None):
    registry = make_registry(tmp_path, clock or Clock())
    return registry, GateStateMachine(registry, cfg=cfg)


def test_new_rule_starts_pending(tmp_path, cfg):
    _registry, machine = make_machine(tmp_path, cfg)
    record = machine.current("rule-1")
    assert record.stage is GateStage.BACKTEST_PENDING
    assert record.stage_timestamps == {}


def test_skip_rejected_and_traced(tmp_path, cfg):
    registry, machine = make_machine(tmp_path, cfg)
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.SHADOW_RUNNING, {"experiment_id": "e1"})
    gate_lines = (tmp_path / "gates.ndjson").read_text(encoding="utf-8").splitlines()
    payload = json.loads(gate_lines[0])
    assert payload["accepted"] is False
    rejected = [
        row
        for row in registry.rows()
        if getattr(row, "status", None) is RunStatus.REJECTED
    ]
    assert len(rejected) == 1
    assert machine.current("rule-1").stage is GateStage.BACKTEST_PENDING


def test_full_ladder_requires_shadow_months(tmp_path, cfg):
    clock = Clock()
    _registry, machine = make_machine(tmp_path, cfg, clock)
    machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
    machine.transition("rule-1", GateStage.SHADOW_RUNNING, {"experiment_id": "e1"})
    with pytest.raises(GateSkipError) as exc:
        machine.transition(
            "rule-1", GateStage.LIVE_SMALL, {"experiment_id": "e1", "direction_agree": True}
        )
    assert "影子期未满" in str(exc.value)
    clock.value = "2026-08-01T00:00:00"
    record = machine.transition(
        "rule-1", GateStage.LIVE_SMALL, {"experiment_id": "e1", "direction_agree": True}
    )
    assert record.stage is GateStage.LIVE_SMALL
    assert record.stage_timestamps["shadow"] == "2026-01-01T00:00:00"
    assert record.evidence_experiment_ids["backtest"] == "e1"


def test_live_requires_direction_agree(tmp_path, cfg):
    clock = Clock()
    _registry, machine = make_machine(tmp_path, cfg, clock)
    machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
    machine.transition("rule-1", GateStage.SHADOW_RUNNING, {"experiment_id": "e1"})
    clock.value = "2027-01-01T00:00:00"
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.LIVE_SMALL, {"experiment_id": "e1"})


def test_missing_gate_criteria_rejects_transition(tmp_path, config_factory):
    raw = config_factory()
    raw.pop("gates")
    cfg = BacktestConfig.from_config(raw, base_dir=tmp_path)
    registry = make_registry(tmp_path, Clock())
    machine = GateStateMachine(registry, cfg=cfg)
    with pytest.raises(MissingBacktestConfigError) as exc:
        machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
    assert "gate_criteria" in str(exc.value)
    assert not (tmp_path / "gates.ndjson").exists()


def test_missing_cfg_rejects_transition(tmp_path):
    registry = make_registry(tmp_path, Clock())
    machine = GateStateMachine(registry)
    with pytest.raises(MissingBacktestConfigError):
        machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})


def test_rejected_is_terminal(tmp_path, cfg):
    _registry, machine = make_machine(tmp_path, cfg)
    record = machine.transition("rule-1", GateStage.REJECTED, {"reason": "方向不一致"})
    assert record.stage is GateStage.REJECTED
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
