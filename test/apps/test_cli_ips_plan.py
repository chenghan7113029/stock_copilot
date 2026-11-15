"""T3 CLI 装配：`ips plan` 的退出码 0/1/2、stderr 文案与 `--json` 结构。

用 tmp_path 下的政策/快照 fixture（不读 `config/ips.local.yaml` 私人快照），
金额对照手算：`0.35 × 1,000,000 − 250,000 = 100,000`、`100,000 ÷ 24 = 4,167`。
"""

from __future__ import annotations

import json

import pytest
import yaml

from apps.cli import main
from service.allocation import loader


def _policy(*, equity: float = 0.35) -> dict:
    return {
        "allocation": {"target": {"equity": equity, "fixed_income": 0.45, "cash": 0.20}},
        "fixed_income_detail": {"migration": {"trial_ratio": 0.30}},
        "deployment": {
            "start_month": 2,
            "horizon_months": 24,
            "target_date": "2028-11-30",
            "execution_day": "last_thursday",
            "skip_if_equity_above": 0.35,
        },
        "rules": {
            "R1_equity_cap": 0.40,
            "R4_rebalance_band": 0.05,
            "R7_cash_floor": 0.20,
            "R8_stale_days": 7,
        },
    }


def _snapshot(
    *,
    as_of: str = "2026-11-30",
    market_value: int = 250000,
    equity: float = 0.25,
    fixed_income: float = 0.55,
    cash: float = 0.20,
) -> dict:
    return {
        "pool": {"total": 1000000},
        "allocation": {"current": {"equity": equity, "fixed_income": fixed_income, "cash": cash}},
        "holdings": {"as_of": as_of, "total_market_value": market_value},
        # 派生字段故意填错：不得被当结果抄出（R1）
        "deployment": {"gap_to_target": 999999, "monthly_amount": 888888},
    }


@pytest.fixture()
def ips_files(monkeypatch, tmp_path):
    """把 loader 的两个输入指向 tmp_path fixture，并按需重写。"""
    policy_path = tmp_path / "ips.yaml"
    snapshot_path = tmp_path / "ips.local.yaml"
    monkeypatch.setattr(loader, "_IPS_YAML", policy_path)
    monkeypatch.setattr(loader, "_IPS_LOCAL_YAML", snapshot_path)

    def configure(*, policy: dict | None = None, snapshot: dict | None = None) -> None:
        policy_path.write_text(
            yaml.safe_dump(policy if policy is not None else _policy(), allow_unicode=True),
            encoding="utf-8",
        )
        snapshot_path.write_text(
            yaml.safe_dump(snapshot if snapshot is not None else _snapshot(), allow_unicode=True),
            encoding="utf-8",
        )

    configure()
    return configure


def test_plan_exit_0_and_workorder(ips_files, capsys):
    code = main(["ips", "plan", "--as-of", "2026-12-01"])
    captured = capsys.readouterr()
    assert code == 0
    assert "执行日: 2026-12-31" in captured.out
    assert "剩余投放月数: 24" in captured.out
    assert "当月权益买入额: 4,167 元" in captured.out
    assert "0.35 × 1,000,000 − 250,000 = 100,000" in captured.out
    assert "ROUND_HALF_UP" in captured.out
    # 派生字段不得出现在结果里
    assert "888888" not in captured.out and "999999" not in captured.out


def test_plan_json_output_is_structured(ips_files, capsys):
    code = main(["ips", "plan", "--as-of", "2026-12-01", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["execution_month"] == "2026-12"
    assert payload["execution_day"] == "2026-12-31"
    assert payload["gap"] == 100000
    assert payload["remaining_months"] == 24
    assert payload["equity_buy_amount"] == 4167
    assert [category["bucket"] for category in payload["categories"]] == [
        "equity",
        "fixed_income",
        "cash",
    ]
    assert payload["defer"] == {"deferred": False, "reason": None, "cap_warning": None}
    # 快照 0.25/0.55/0.20：权益 −10pp、固收 +10pp 超带 → 两条只提示
    assert [hint["bucket"] for hint in payload["rebalance_hints"]] == ["equity", "fixed_income"]
    assert payload["rebalance_hints"][0]["direction"] == "低于"
    assert payload["cash_hint"]["triggered"] is False
    assert payload["stale"] == {"days": 1, "threshold": 7}
    assert payload["echo"]["target"]["equity"] == 0.35
    assert payload["echo"]["thresholds"]["stale_days"] == 7
    assert payload["echo"]["rounding_rule"].startswith("四舍五入到整数元")


def test_plan_migration_month_output(ips_files, capsys):
    ips_files(snapshot=_snapshot(as_of="2026-11-13"))
    code = main(["ips", "plan", "--as-of", "2026-11-15"])
    captured = capsys.readouterr()
    assert code == 0
    assert "执行日: 2026-11-26" in captured.out
    assert "固收迁移: 135,000 元" in captured.out
    assert "当月权益买入额: 0 元" in captured.out
    assert "定投自 2026-12 起" in captured.out


def test_plan_stale_snapshot_exits_2(ips_files, capsys):
    ips_files(snapshot=_snapshot(as_of="2026-11-01"))
    code = main(["ips", "plan", "--as-of", "2026-11-15"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "数据过期" in captured.err
    assert "as_of 2026-11-01" in captured.err
    assert "14 天" in captured.err
    assert "R8_stale_days 7" in captured.err


def test_plan_future_snapshot_exits_2(ips_files, capsys):
    ips_files(snapshot=_snapshot(as_of="2026-11-20"))
    code = main(["ips", "plan", "--as-of", "2026-11-15"])
    captured = capsys.readouterr()
    assert code == 2
    assert "晚于计算日" in captured.err


def test_plan_bad_as_of_exits_1(ips_files, capsys):
    code = main(["ips", "plan", "--as-of", "2026-13-01"])
    captured = capsys.readouterr()
    assert code == 1
    assert "--as-of" in captured.err
    assert captured.out == ""


def test_plan_missing_market_value_exits_1(ips_files, capsys):
    snapshot = _snapshot()
    del snapshot["holdings"]["total_market_value"]
    ips_files(snapshot=snapshot)
    code = main(["ips", "plan", "--as-of", "2026-12-01"])
    captured = capsys.readouterr()
    assert code == 1
    assert "total_market_value" in captured.err
    assert captured.out == ""


def test_plan_missing_snapshot_date_exits_1(ips_files, capsys):
    snapshot = _snapshot()
    del snapshot["holdings"]["as_of"]
    ips_files(snapshot=snapshot)
    code = main(["ips", "plan", "--as-of", "2026-12-01"])
    captured = capsys.readouterr()
    assert code == 1
    assert "holdings.as_of" in captured.err


def test_plan_recomputes_when_policy_changes(ips_files, capsys):
    # 政策 0.40：缺口 = 0.40 × 1,000,000 − 250,000 = 150,000 → 150,000 ÷ 24 = 6,250
    ips_files(policy=_policy(equity=0.40))
    code = main(["ips", "plan", "--as-of", "2026-12-01", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["gap"] == 150000
    assert payload["equity_buy_amount"] == 6250
    assert payload["echo"]["target"]["equity"] == 0.40


def test_plan_defer_printed_with_reason(ips_files, capsys):
    ips_files(snapshot=_snapshot(equity=0.36, fixed_income=0.44))
    code = main(["ips", "plan", "--as-of", "2026-12-01"])
    captured = capsys.readouterr()
    assert code == 0
    assert "顺延: 是" in captured.out
    assert "36%" in captured.out
    assert "当月权益买入额: 0 元" in captured.out
