"""R19 三级门禁状态机（TC-R19-01..03）。

锚点：spec R19；design §4.1（T2-fix-4 后）`GateStage`、`GateStateMachine(registry, *, cfg)`：
判据来自 `cfg.gate_criteria`（`backtest.gates`，Q7），`gate_criteria` 缺失 → `MissingBacktestConfigError`
且**不允许 transition**；跳级 → `GateSkipError` 并留痕；`GateRecord{stage, stage_timestamps,
evidence_experiment_ids, direction_agree}` 唯一可查。
"""

from __future__ import annotations

import pytest


def test_tc_r19_01_cannot_enter_shadow_without_backtest(gate_sm, gate_sm_no_criteria, models, rule_id,
                                                        registry_path, run_rows):
    """TC-R19-01（R19 Scenario1）：回测未通过就请求影子运行 → GateSkipError，状态不变，拒绝留痕；
    判据缺失时更早一层被拒（MissingBacktestConfigError，不允许降级放行）。"""
    with pytest.raises(models.MissingBacktestConfigError):
        gate_sm_no_criteria.transition(rule_id, models.GateStage.SHADOW_RUNNING,
                                       evidence={"experiment_id": "exp-001"})

    assert gate_sm.current(rule_id).stage is models.GateStage.BACKTEST_PENDING
    with pytest.raises(models.GateSkipError):
        gate_sm.transition(rule_id, models.GateStage.SHADOW_RUNNING,
                           evidence={"experiment_id": "exp-001"})

    assert gate_sm.current(rule_id).stage is models.GateStage.BACKTEST_PENDING
    assert any(row["status"] == "rejected" for row in run_rows(registry_path)), "拒绝必须落执行行"


def test_tc_r19_02_shadow_period_too_short_blocks_live(gate_sm, models, rule_id):
    """TC-R19-02（R19 Scenario2）：影子仅 2 个月请求实盘小仓位 → 拒绝并提示最低 6 个月/方向一致。"""
    gate_sm.transition(rule_id, models.GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})
    gate_sm.transition(rule_id, models.GateStage.SHADOW_RUNNING, evidence={"experiment_id": "exp-002"})

    with pytest.raises(models.GateSkipError) as exc:
        gate_sm.transition(rule_id, models.GateStage.LIVE_SMALL,
                           evidence={"experiment_id": "exp-002", "months": 2, "direction_agree": True})

    message = str(exc.value)
    assert "6" in message and ("方向" in message or "月" in message)
    assert gate_sm.current(rule_id).stage is models.GateStage.SHADOW_RUNNING


def test_tc_r19_03_gate_state_is_unique_and_queryable(gate_sm, models, rule_id):
    """TC-R19-03（R19 Scenario3）：查询返回唯一状态 + 每级通过时间与依据实验 ID。"""
    gate_sm.transition(rule_id, models.GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})

    record = gate_sm.current(rule_id)
    again = gate_sm.current(rule_id)

    assert isinstance(record, models.GateRecord)
    assert record.stage is models.GateStage.BACKTEST_PASSED
    assert again.stage is record.stage and again.rule_id == record.rule_id
    assert record.evidence_experiment_ids.get("backtest") == "exp-001"
    assert record.stage_timestamps, "每级通过时间必须可查（R19 Scenario3）"
