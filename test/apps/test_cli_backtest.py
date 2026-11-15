"""T2.19 CLI 装配：`backtest preregister|run|calibrate|ledger|gate` + 配置解析 + 退出码。"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import yaml

from apps.cli import main
from service.backtest.models import (
    AdjustMode,
    ExperimentRecord,
    Segment,
    Verdict,
)
from service.backtest.registry import ExperimentRegistry

FULL_CONFIG = {
    "results_dir": "results",
    "registry_store_path": "registry.ndjson",
    "prereg_dir": "preregistrations",
    "data_version": "test-v1",
    "commission": {"rate": 2.5e-4, "min": 5},
    "stamp_tax": {"sell_rate": 5e-4},
    "transfer_fee": {"included": False},
    "slippage_tiers": [{"amount_lower": 0, "amount_upper": 1_000_000, "bps": 10}],
    "liquidity_cap": [{"amount_lower": 0, "amount_upper": None, "max_participation": 0.01}],
    "max_delay_days": 5,
    "alpha": 0.05,
    "block_length": 5,
    "n_bootstrap": 100,
    "min_events": 2,
    "correction_method": "bonferroni",
    "k_components": [1],
    "cut_basis": "point_in_time_cross_section",
    "tier_count": 3,
    "min_group_size": 1,
    "recompute_freq": "quarterly",
    "gates": {
        "backtest_pass": {"metric": "excess"},
        "shadow_min_months": 6,
        "direction_agree": {"metric": "excess"},
        "small_position_max_pct": 5,
    },
    "calibration": {
        "short_history_policy": "ma20_substitute",
        "horizon_days": 2,
        "k": 1,
        "notional": 100_000,
        "codes": ["000001", "000002"],
        "start": "2020-01-01",
        "end": "2020-12-31",
    },
}

PREREG = {
    "hypothesis_id": "hid",
    "statement": "跌破 MA60 后卖出跑输买入持有",
    "params": {"ma": 60, "K": 1, "codes": ["000001"], "start": "2020-01-01", "end": "2020-12-31"},
    "metrics": ["mean_excess"],
    "segments": ["validation"],
    "benchmarks": ["buy_and_hold"],
    "correction_method": "bonferroni",
    "k_definition": "规则×参数网格",
    "created_at": "2026-01-01T00:00:00",
}


def write_config(tmp_path, **overrides):
    section = copy.deepcopy(FULL_CONFIG)
    for dotted, value in overrides.items():
        parts = dotted.split(".")
        target = section
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "app.yaml").write_text(
        yaml.safe_dump({"backtest": section}, allow_unicode=True), encoding="utf-8"
    )
    return section


def test_ledger_unknown_experiment_exit_1(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    code = main(["backtest", "ledger", "--experiment", "no-such-id"])
    captured = capsys.readouterr()
    assert code == 1
    assert code != 2
    assert captured.err.strip()


def test_preregister_writes_file(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    source = tmp_path / "hid.yaml"
    source.write_text(yaml.safe_dump(PREREG, allow_unicode=True), encoding="utf-8")
    code = main(["backtest", "preregister", "--file", str(source)])
    assert code == 0
    destination = tmp_path / "preregistrations" / "hid.yaml"
    assert destination.exists()
    saved = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert saved["statement"] == PREREG["statement"]
    assert saved["segments"] == ["validation"]


def test_run_without_prereg_exits_1_and_logs_rejection(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    code = main(["backtest", "run", "--hypothesis", "missing-hypothesis"])
    captured = capsys.readouterr()
    assert code == 1
    assert "预注册缺失" in captured.err
    rows = (tmp_path / "registry.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["row_type"] == "run"
    assert payload["status"] == "rejected"
    assert not (tmp_path / "results").exists()


def test_ledger_exports_13_fields_json(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    registry = ExperimentRegistry(
        tmp_path / "registry.ndjson",
        clock=lambda: "2026-01-01T00:00:00",
        data_version="test-v1",
        results_dir=tmp_path / "results",
    )
    registry.append(
        ExperimentRecord(
            experiment_id="hid-0001",
            hypothesis_id="hid",
            params={"ma": 60},
            segment=Segment.VALIDATION,
            K=1,
            verdict=Verdict.INCONCLUSIVE,
            metrics={"mean": -0.01},
            prereg_commit="deadbeef",
            data_version="test-v1",
            adjust_mode=AdjustMode.HFQ,
            timestamps={"created_at": "2026-01-01T00:00:00"},
        )
    )
    code = main(["backtest", "ledger", "--hypothesis", "hid", "--format", "json"])
    captured = capsys.readouterr()
    assert code == 0
    rows = json.loads(captured.out)
    assert isinstance(rows, list) and len(rows) == 1
    assert set(rows[0]) == {
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


def _rows_for(closes: list[float], code: str):
    current = date(2020, 1, 1)
    dates = []
    while len(dates) < len(closes):
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return tuple(
        {
            "code": code,
            "trade_date": day,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "factor": 1.0,
            "amount": 1_000_000.0,
            "limit_up_price": close * 2,
            "limit_down_price": close / 2,
            "suspended": False,
        }
        for day, close in zip(dates, closes)
    )


class SyntheticLoader:
    def __init__(self, closes):
        self.closes = closes

    def load_price_rows(self, codes, start, end, adjust):
        return {code: _rows_for(self.closes, code) for code in codes}

    def load_universe_codes(self, as_of):
        return ("000001", "000002")


RALLY = [10.0] * 60 + [9.0, 11.0, 12.0]
DROP = [10.0] * 60 + [9.0, 8.0, 7.0]


def test_calibrate_success_exit_0(monkeypatch, tmp_path, capsys):
    import apps.cli as cli

    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    monkeypatch.setattr(cli, "build_backtest_loader", lambda cfg: SyntheticLoader(RALLY))
    code = cli.main(["backtest", "calibrate"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["passed"] is True
    written = json.loads((tmp_path / "results" / "calibration.json").read_text(encoding="utf-8"))
    assert written["passed"] is True


def test_calibrate_failure_exit_2(monkeypatch, tmp_path, capsys):
    import apps.cli as cli

    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    monkeypatch.setattr(cli, "build_backtest_loader", lambda cfg: SyntheticLoader(DROP))
    code = cli.main(["backtest", "calibrate"])
    captured = capsys.readouterr()
    assert code == 2
    assert "先修台子" in captured.err
    written = json.loads((tmp_path / "results" / "calibration.json").read_text(encoding="utf-8"))
    assert written["passed"] is False


def test_gate_query_returns_pending(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path)
    code = main(["backtest", "gate", "--rule", "rule-1"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["stage"] == "backtest_pending"
