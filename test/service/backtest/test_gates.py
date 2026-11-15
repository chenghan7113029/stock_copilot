"""T2.18 三级门禁状态机（R19：不跳级、判据缺键拒绝、唯一状态可查）。"""

from __future__ import annotations

import json

import pytest

from common.exceptions import GateSkipError, MissingBacktestConfigError
from service.backtest.gates import GateStateMachine
from service.backtest.models import BacktestConfig, GateStage


class Clock:
    def __init__(self, value="2026-01-01T00:00:00"):
        self.value = value

    def __call__(self) -> str:
        return self.value


def make_machine(tmp_path, cfg, clock=None):
    return GateStateMachine(tmp_path / "gates.ndjson", cfg=cfg, clock=clock or Clock())


def test_new_rule_starts_pending(tmp_path, cfg):
    record = make_machine(tmp_path, cfg).current("rule-1")
    assert record.stage is GateStage.BACKTEST_PENDING
    assert record.stage_timestamps == {}


def test_skip_rejected_and_traced(tmp_path, cfg):
    machine = make_machine(tmp_path, cfg)
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.SHADOW_RUNNING, {"experiment_id": "e1"})
    lines = (tmp_path / "gates.ndjson").read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    assert payload["accepted"] is False
    assert payload["stage"] == "shadow_running"
    assert machine.current("rule-1").stage is GateStage.BACKTEST_PENDING


def test_full_ladder_requires_shadow_months(tmp_path, cfg):
    clock = Clock()
    machine = make_machine(tmp_path, cfg, clock)
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
    machine = make_machine(tmp_path, cfg, clock)
    machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
    machine.transition("rule-1", GateStage.SHADOW_RUNNING, {"experiment_id": "e1"})
    clock.value = "2027-01-01T00:00:00"
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.LIVE_SMALL, {"experiment_id": "e1"})


def test_missing_gate_criteria_rejects_transition(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(**{"gates.backtest_pass": None}), base_dir=tmp_path, require_pipeline=False
    )
    machine = make_machine(tmp_path, cfg)
    with pytest.raises(MissingBacktestConfigError):
        machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})


def test_rejected_is_terminal(tmp_path, cfg):
    machine = make_machine(tmp_path, cfg)
    record = machine.transition("rule-1", GateStage.REJECTED, {"reason": "方向不一致"})
    assert record.stage is GateStage.REJECTED
    with pytest.raises(GateSkipError):
        machine.transition("rule-1", GateStage.BACKTEST_PASSED, {"experiment_id": "e1"})
