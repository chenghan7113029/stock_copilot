"""R1 预注册先于跑数 / R2 台账 append-only（TC-R01-01..03、TC-R02-01..03）。

锚点：spec R1/R2；design §4.1 `PreregistrationSpec`/`RunRecord`/`ExperimentRecord`/
`ExperimentRegistry.validate_preregistration/append_run/append/get/next_experiment_id`、
§4.1「台账存储机制」、§6.3 退出码（1 = 参数/配置/数据错误）。
"""

from __future__ import annotations

import json

import pytest


def _spec(models, **overrides):
    fields = dict(
        hypothesis_id="hyp-001",
        statement="跌破 MA60 后 60 日跑输买入持有",
        params={"ma_days": 60},
        metrics=("excess_mean",),
        segments=(models.Segment.VALIDATION, models.Segment.OUT_OF_SAMPLE),
        benchmarks=("buy_and_hold", "market_portfolio"),
        correction_method="bonferroni",
        k_definition="rule+param+cut+window",
        created_at="2026-01-02T09:30:00+08:00",
    )
    fields.update(overrides)
    return models.PreregistrationSpec(**fields)


def _record(models, experiment_id, **overrides):
    fields = dict(
        experiment_id=experiment_id, hypothesis_id="hyp-001", params={"ma_days": 60},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE, metrics={},
        prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None,
    )
    fields.update(overrides)
    return models.ExperimentRecord(**fields)


def test_tc_r01_01_preregistered_run_records_commit_and_params(registry, models):
    """TC-R01-01（R1 Scenario1）：预注册校验通过 → 结果行记录 commit / 假设 / 参数。"""
    spec = _spec(models)
    registry.validate_preregistration(spec)  # 9 必填齐全 → 不抛（R1 Scenario1）

    experiment_id = registry.next_experiment_id(spec.hypothesis_id)
    registry.append(_record(models, experiment_id))

    got = registry.get(experiment_id)
    assert got.prereg_commit == "deadbeef"
    assert got.hypothesis_id == spec.hypothesis_id
    assert got.params == spec.params
    assert experiment_id == f"{spec.hypothesis_id}-0001"  # design §4.1 experiment_id 规则（QA-F8）


def test_tc_r01_02_missing_preregistration_rejected(cli_runner):
    """TC-R01-02（R1 Scenario2）：台账无对应预注册 → 退出码非 0，且不新增结果行。"""
    run = cli_runner(["run", "--hypothesis", "hyp-absent"])
    assert run.returncode == 1, run.stderr  # 设计 §6.3：参数/数据错误 = 1
    assert "hyp-absent" in run.stderr or "预注册" in run.stderr
    assert run.returncode != 0


def test_tc_r01_03_uncommitted_preregistration_rejected(cli_runner, tmp_path, result_rows, registry_path):
    """TC-R01-03（R1 Scenario3）：预注册只在工作区未提交 → 拒绝并提示「未提交」。"""
    prereg_dir = tmp_path / "config" / "backtest" / "preregistrations"
    prereg_dir.mkdir(parents=True, exist_ok=True)
    (prereg_dir / "hyp-uncommitted.yaml").write_text(json.dumps({
        "hypothesis_id": "hyp-uncommitted",
        "statement": "跌破 MA60 后 60 日跑输买入持有",
        "params": {"ma_days": 60},
        "metrics": ["excess_mean"],
        "segments": ["validation", "out_of_sample"],
        "benchmarks": ["buy_and_hold", "market_portfolio"],
        "correction_method": "bonferroni",
        "k_definition": "rule+param+cut+window",
        "created_at": "2026-01-02T09:30:00+08:00",
    }), encoding="utf-8")
    before = len(result_rows(registry_path))

    run = cli_runner(["run", "--hypothesis", "hyp-uncommitted"])

    assert run.returncode == 1, run.stderr
    assert "未提交" in run.stderr
    assert len(result_rows(registry_path)) == before  # 不产生结果记录（R1）


def test_tc_r02_01_each_run_appends_one_row_with_unique_id(registry, models, result_rows, registry_path):
    """TC-R02-01（R2 Scenario1）：同一预注册执行两次 → 两行、experiment_id 不同且递增。"""
    spec = _spec(models)
    ids = []
    for _ in range(2):
        experiment_id = registry.next_experiment_id(spec.hypothesis_id)  # 追加后再取下一个序号
        registry.append(_record(models, experiment_id))
        ids.append(experiment_id)

    rows = result_rows(registry_path)
    assert len(rows) == 2
    assert len(set(ids)) == 2
    assert ids[0].endswith("-0001") and ids[1].endswith("-0002")
    assert [row["experiment_id"] for row in rows] == ids


def test_tc_r02_02_tampered_ledger_row_rejected(registry, models, registry_path):
    """TC-R02-02（R2 Scenario2）：篡改已写入行的 K → 读取抛 RegistryCorruptedError（不留假成功）。"""
    experiment_id = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, experiment_id))

    lines = registry_path.read_text(encoding="utf-8").splitlines()
    assert lines, "夹具前置：台账至少 1 行"
    tampered = lines[0].replace('"K": 1', '"K": 2')
    assert tampered != lines[0], "夹具前置：首行必须含 K 字段"
    registry_path.write_text(tampered + "\n", encoding="utf-8")

    corrupted = load_exc(registry, "RegistryCorruptedError")
    with pytest.raises(corrupted) as exc:
        registry.get(experiment_id)
    assert "台账" in str(exc.value) or "损坏" in str(exc.value)


def test_tc_r02_03_assumption_change_requires_new_experiment(registry, models, registry_path):
    """TC-R02-03（R2 Scenario3）：改假设/参数 → RegistryImmutableError，必须新开并写 parent。"""
    experiment_id = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, experiment_id))
    immutable = load_exc(registry, "RegistryImmutableError")

    with pytest.raises(immutable):
        registry.append(_record(models, experiment_id, params={"ma_days": 61}))
    assert registry.get(experiment_id).params == {"ma_days": 60}

    child_id = registry.next_experiment_id("hyp-001")
    registry.append(_record(models, child_id, params={"ma_days": 61},
                            parent_experiment_id=experiment_id))
    assert registry.get(child_id).parent_experiment_id == experiment_id
    assert registry.get(child_id).params == {"ma_days": 61}


def load_exc(registry, name):
    """从被测异常模块取具体异常类（design §4.1 异常清单：`service.backtest.models`）。"""
    module = __import__(registry.__class__.__module__, fromlist=[name])
    return getattr(module, name)
