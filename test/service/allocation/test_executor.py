"""T3 单测：配置执行器纯算术（手算对照 / 幂等 / 顺延 / 时效 / 提示 / loader）。

所有金额对照都是手算数：`0.35 × 1,000,000 − 250,000 = 100,000`、
`100,000 ÷ 24 = 4,166.67 → 4,167`、`0.45 × 1,000,000 × 0.30 = 135,000`、
`0.20 × 1,000,000 − 150,000 = 50,000`。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from service.allocation import loader
from service.allocation.executor import (
    assert_fresh,
    cash_floor_hint,
    compute_gap,
    compute_plan,
    compute_remaining_months,
    decide_defer,
    rebalance_hints,
    render_plan,
    render_plan_json,
    resolve_execution_month_day,
    round_yuan,
)
from service.allocation.loader import load_ips_policy, load_snapshot
from service.allocation.models import (
    AllocationConfigError,
    AllocationStaleError,
    IpsPolicy,
    Snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def make_policy(**overrides: object) -> IpsPolicy:
    """与 `config/ips.yaml` 同口径的政策（数值显式写出，手算对照不受文件改动影响）。"""
    base = IpsPolicy(
        target_equity=Decimal("0.35"),
        target_fixed_income=Decimal("0.45"),
        target_cash=Decimal("0.20"),
        start_month=2,
        horizon_months=24,
        target_date=date(2028, 11, 30),
        execution_day="last_thursday",
        skip_if_equity_above=Decimal("0.35"),
        trial_ratio=Decimal("0.30"),
        equity_cap=Decimal("0.40"),
        rebalance_band=Decimal("0.05"),
        cash_floor=Decimal("0.20"),
        stale_days=7,
    )
    return replace(base, **overrides)


def make_snapshot(**overrides: object) -> Snapshot:
    """合成快照：pool=1,000,000、权益市值=250,000（缺口手算 100,000）。"""
    base = Snapshot(
        pool_total=Decimal("1000000"),
        current_equity=Decimal("0.25"),
        current_fixed_income=Decimal("0.55"),
        current_cash=Decimal("0.20"),
        holdings_market_value=Decimal("250000"),
        holdings_as_of=date(2026, 11, 30),
    )
    return replace(base, **overrides)


# ── R2 执行日 ────────────────────────────────────────────────────────────────


def test_resolve_execution_day_is_last_thursday():
    assert resolve_execution_month_day(date(2026, 11, 15)) == (date(2026, 11, 1), date(2026, 11, 26))
    assert resolve_execution_month_day(date(2026, 12, 1)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_resolve_execution_day_on_the_day_and_after():
    day = date(2026, 11, 26)
    assert resolve_execution_month_day(day) == (date(2026, 11, 1), day)
    assert resolve_execution_month_day(date(2026, 11, 27)) == (date(2026, 12, 1), date(2026, 12, 31))


# ── R3 缺口与月数 ────────────────────────────────────────────────────────────


def test_compute_gap_hand_calc():
    assert compute_gap(make_policy(), make_snapshot()) == Decimal("100000")
    assert compute_gap(make_policy(), make_snapshot(holdings_market_value=Decimal("400000"))) == Decimal("-50000")


def test_compute_remaining_months_inclusive():
    policy = make_policy()
    assert compute_remaining_months(policy, date(2026, 12, 1)) == 24
    assert compute_remaining_months(policy, date(2027, 1, 1)) == 23
    assert compute_remaining_months(policy, date(2028, 11, 1)) == 1
    assert compute_remaining_months(policy, date(2028, 12, 1)) == 0
    # 迁移月早于首个定投月：max(执行月, 首个定投月) = 2026-12 → 24
    assert compute_remaining_months(policy, date(2026, 11, 1)) == 24


# ── R4 金额与取整 ────────────────────────────────────────────────────────────


def test_round_yuan_half_up_to_yuan():
    assert round_yuan(Decimal("4158.5")) == Decimal("4159")
    assert round_yuan(Decimal("4158.4")) == Decimal("4158")
    assert round_yuan(Decimal("100000") / Decimal("24")) == Decimal("4167")
    assert round_yuan(Decimal("135000")) == Decimal("135000")


def test_regular_month_buys_gap_over_remaining_months():
    plan = compute_plan(make_policy(), make_snapshot(), date(2026, 12, 1))
    assert plan.execution_month == date(2026, 12, 1)
    assert plan.execution_day == date(2026, 12, 31)
    assert plan.gap == Decimal("100000")
    assert plan.remaining_months == 24
    assert plan.equity_amount == Decimal("4167")
    assert plan.defer.deferred is False
    categories = {category.bucket: category.amount for category in plan.categories}
    assert categories == {
        "equity": Decimal("4167"),
        "fixed_income": Decimal("0"),
        "cash": Decimal("0"),
    }
    text = render_plan(plan)
    assert "0.35 × 1,000,000 − 250,000 = 100,000" in text
    assert "剩余投放月数: 24" in text
    assert "当月权益买入额: 4,167 元" in text
    assert "ROUND_HALF_UP" in text
    assert "0.35" in text and "2028-11-30" in text and "2026-11-30" in text


def test_plan_is_idempotent():
    policy, snapshot = make_policy(), make_snapshot()
    first = compute_plan(policy, snapshot, date(2026, 12, 1))
    second = compute_plan(policy, snapshot, date(2026, 12, 1))
    assert first == second
    assert render_plan(first) == render_plan(second)
    assert render_plan_json(first) == render_plan_json(second)


def test_target_month_buys_rest_of_gap_and_ends():
    # 目标月 2028-11：权益市值 345,841 → 缺口 4,159，全额买入后按该快照缺口归零
    snapshot = make_snapshot(
        holdings_market_value=Decimal("345841"),
        current_equity=Decimal("0.30"),
        holdings_as_of=date(2028, 11, 1),
    )
    plan = compute_plan(make_policy(), snapshot, date(2028, 11, 2))
    assert plan.execution_day == date(2028, 11, 30)
    assert plan.remaining_months == 1
    assert plan.gap == Decimal("4159")
    assert plan.equity_amount == Decimal("4159")
    assert plan.gap - plan.equity_amount == Decimal("0")
    assert "投放期结束" in plan.reasons[0]


def test_after_target_month_no_buy():
    plan = compute_plan(make_policy(), make_snapshot(holdings_as_of=date(2028, 11, 30)), date(2028, 12, 1))
    assert plan.execution_month == date(2028, 12, 1)
    assert plan.remaining_months == 0
    assert plan.equity_amount == Decimal("0")
    assert all(category.amount == Decimal("0") for category in plan.categories)
    assert "投放期已结束" in plan.reasons[0]


def test_negative_gap_never_sells():
    snapshot = make_snapshot(holdings_market_value=Decimal("400000"), current_equity=Decimal("0.30"))
    plan = compute_plan(make_policy(), snapshot, date(2026, 12, 1))
    assert plan.gap == Decimal("-50000")
    assert plan.equity_amount == Decimal("0")
    assert all(category.amount >= 0 for category in plan.categories)
    assert "缺口为负" in plan.reasons[0]


def test_before_migration_month_no_equity_buy():
    # 首个定投月（2026-12）之前不产出权益买入（spec R5）
    snapshot = make_snapshot(holdings_as_of=date(2026, 10, 10))
    plan = compute_plan(make_policy(), snapshot, date(2026, 10, 15))
    assert plan.execution_month == date(2026, 10, 1)
    assert plan.equity_amount == Decimal("0")
    assert all(category.amount == Decimal("0") for category in plan.categories)
    assert "未开始" in plan.reasons[0]


# ── R5 类别分配 ──────────────────────────────────────────────────────────────


def test_migration_month_only_migrates_fixed_income():
    snapshot = make_snapshot(holdings_as_of=date(2026, 11, 13))
    plan = compute_plan(make_policy(), snapshot, date(2026, 11, 15))
    assert plan.execution_day == date(2026, 11, 26)
    assert plan.equity_amount == Decimal("0")
    categories = {category.bucket: category.amount for category in plan.categories}
    assert categories == {
        "equity": Decimal("0"),
        "fixed_income": Decimal("135000"),
        "cash": Decimal("0"),
    }
    assert "定投自 2026-12 起" in plan.reasons[0]
    assert "固收迁移: 135,000 元" in render_plan(plan)


def test_dca_month_has_no_migration_amount():
    plan = compute_plan(make_policy(), make_snapshot(), date(2026, 12, 1))
    categories = {category.bucket: category.amount for category in plan.categories}
    assert categories["fixed_income"] == Decimal("0")
    assert categories["cash"] == Decimal("0")


def test_categories_never_name_codes():
    text = render_plan(compute_plan(make_policy(), make_snapshot(), date(2026, 12, 1)))
    assert "宽基 ETF" in text
    for code in ("002027", "600072", "600036", "510300", "000001"):
        assert code not in text


# ── R6 顺延 ──────────────────────────────────────────────────────────────────


def test_defer_when_equity_above_skip():
    snapshot = make_snapshot(current_equity=Decimal("0.36"), current_fixed_income=Decimal("0.44"))
    plan = compute_plan(make_policy(), snapshot, date(2026, 12, 1))
    assert plan.defer.deferred is True
    assert plan.equity_amount == Decimal("0")
    assert all(category.amount == Decimal("0") for category in plan.categories)
    assert "顺延" in plan.defer.reason
    assert "36%" in plan.defer.reason and "35%" in plan.defer.reason
    assert plan.defer.cap_warning is None
    assert "顺延: 是" in render_plan(plan)


def test_defer_is_strictly_above_skip_threshold():
    at_threshold = make_snapshot(current_equity=Decimal("0.35"), current_fixed_income=Decimal("0.45"))
    assert decide_defer(make_policy(), at_threshold).deferred is False


def test_defer_over_cap_adds_hint_only():
    snapshot = make_snapshot(current_equity=Decimal("0.42"), current_fixed_income=Decimal("0.38"))
    plan = compute_plan(make_policy(), snapshot, date(2026, 12, 1))
    assert plan.defer.deferred is True
    assert plan.defer.cap_warning is not None
    assert "权益超过 R1 上限 40%（未经回测验证，仅提示" in plan.defer.cap_warning
    assert plan.equity_amount == Decimal("0")
    assert all(category.amount >= 0 for category in plan.categories)
    assert "提示: 权益超过 R1 上限 40%" in render_plan(plan)


def test_defer_does_not_carry_over_quota():
    deferred = compute_plan(
        make_policy(), make_snapshot(current_equity=Decimal("0.36")), date(2026, 12, 1)
    )
    resumed = compute_plan(
        make_policy(),
        make_snapshot(current_equity=Decimal("0.34"), holdings_as_of=date(2026, 12, 28)),
        date(2027, 1, 1),
    )
    assert deferred.equity_amount == Decimal("0")
    assert resumed.remaining_months == 23
    assert resumed.equity_amount == round_yuan(Decimal("100000") / Decimal("23"))  # 4,348
    assert "待补" not in render_plan(resumed)
    assert "上期" not in resumed.reasons[0]


# ── R7 时效 ──────────────────────────────────────────────────────────────────


def test_assert_fresh_rejects_stale_snapshot():
    snapshot = make_snapshot(holdings_as_of=date(2026, 11, 1))
    with pytest.raises(AllocationStaleError) as excinfo:
        assert_fresh(make_policy(), snapshot, date(2026, 11, 15))
    message = str(excinfo.value)
    assert "as_of 2026-11-01" in message
    assert "14 天" in message
    assert "R8_stale_days 7" in message
    with pytest.raises(AllocationStaleError):
        compute_plan(make_policy(), snapshot, date(2026, 11, 15))


def test_assert_fresh_allows_exactly_stale_days():
    snapshot = make_snapshot(holdings_as_of=date(2026, 11, 8))
    info = assert_fresh(make_policy(), snapshot, date(2026, 11, 15))
    assert info.days == 7
    assert info.threshold == 7


def test_assert_fresh_rejects_future_snapshot():
    snapshot = make_snapshot(holdings_as_of=date(2026, 11, 20))
    with pytest.raises(AllocationStaleError) as excinfo:
        assert_fresh(make_policy(), snapshot, date(2026, 11, 15))
    assert "晚于计算日" in str(excinfo.value)


# ── R8 再平衡提示 ────────────────────────────────────────────────────────────


def test_rebalance_hint_over_band_does_not_change_amount():
    with_hint = make_snapshot(
        current_equity=Decimal("0.25"),
        current_fixed_income=Decimal("0.30"),
        current_cash=Decimal("0.45"),
    )
    without_hint = make_snapshot(
        current_equity=Decimal("0.35"),
        current_fixed_income=Decimal("0.45"),
        current_cash=Decimal("0.20"),
    )
    hints = rebalance_hints(make_policy(), with_hint)
    messages = [hint.message for hint in hints]
    assert any("固收低于目标 15pp" in message for message in messages)
    assert any("权益低于目标 10pp" in message for message in messages)

    plan_with = compute_plan(make_policy(), with_hint, date(2026, 12, 1))
    plan_without = compute_plan(make_policy(), without_hint, date(2026, 12, 1))
    assert plan_with.equity_amount == plan_without.equity_amount == Decimal("4167")
    assert plan_without.rebalance_hints == ()
    assert "再平衡提示: 无" in render_plan(plan_without)


def test_rebalance_hint_within_band_is_silent():
    snapshot = make_snapshot(
        current_equity=Decimal("0.35"),
        current_fixed_income=Decimal("0.45"),
        current_cash=Decimal("0.20"),
    )
    assert rebalance_hints(make_policy(), snapshot) == ()


# ── R9 现金不足提示 ──────────────────────────────────────────────────────────


def test_cash_floor_hint_gives_shortfall_without_changing_amount():
    low_cash = make_snapshot(
        current_cash=Decimal("0.15"), current_equity=Decimal("0.25"), current_fixed_income=Decimal("0.60")
    )
    hint = cash_floor_hint(make_policy(), low_cash)
    assert hint.triggered is True
    assert hint.cash_market_value == Decimal("150000")
    assert hint.floor_amount == Decimal("200000")
    assert hint.shortfall == Decimal("50000")
    assert "现金不足" in hint.message and "50,000" in hint.message

    plan_with_hint = compute_plan(make_policy(), low_cash, date(2026, 12, 1))
    assert plan_with_hint.equity_amount == Decimal("4167")
    assert "现金不足提示: 现金不足" in render_plan(plan_with_hint)


def test_cash_floor_hint_silent_when_above_floor():
    hint = cash_floor_hint(make_policy(), make_snapshot(current_cash=Decimal("0.22")))
    assert hint.triggered is False
    assert hint.shortfall == Decimal("0")
    plan = compute_plan(make_policy(), make_snapshot(current_cash=Decimal("0.22")), date(2026, 12, 1))
    assert "现金不足提示: 无" in render_plan(plan)


# ── R1 loader：真源、派生字段隔离、缺键拒绝 ─────────────────────────────────


def test_loader_policy_matches_tracked_ips_yaml():
    policy = load_ips_policy()
    assert _REPO_ROOT.joinpath("config", "ips.yaml").is_file()
    assert policy.target_equity == Decimal("0.35")
    assert policy.target_fixed_income == Decimal("0.45")
    assert policy.target_cash == Decimal("0.20")
    assert policy.start_month == 2
    assert policy.horizon_months == 24
    assert policy.target_date == date(2028, 11, 30)
    assert policy.execution_day == "last_thursday"
    assert policy.skip_if_equity_above == Decimal("0.35")
    assert policy.trial_ratio == Decimal("0.30")
    assert policy.equity_cap == Decimal("0.40")
    assert policy.rebalance_band == Decimal("0.05")
    assert policy.cash_floor == Decimal("0.20")
    assert policy.stale_days == 7


SNAPSHOT_FIXTURE = {
    "pool": {"total": 1000000},
    "allocation": {"current": {"equity": 0.25, "fixed_income": 0.55, "cash": 0.20}},
    "holdings": {"as_of": "2026-11-30", "total_market_value": 250000},
    "deployment": {"gap_to_target": 2167373, "monthly_amount": 90307},
}


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _drop(dotted: str) -> dict:
    """返回删掉点号路径字段的快照 fixture（不改原 dict）。"""
    import copy

    data = copy.deepcopy(SNAPSHOT_FIXTURE)
    keys = dotted.split(".")
    node = data
    for key in keys[:-1]:
        node = node[key]
    del node[keys[-1]]
    return data


def test_loader_snapshot_reads_raw_fields(monkeypatch, tmp_path):
    snapshot_path = _write_yaml(tmp_path / "ips.local.yaml", SNAPSHOT_FIXTURE)
    monkeypatch.setattr(loader, "_IPS_LOCAL_YAML", snapshot_path)
    snapshot = load_snapshot()
    assert snapshot.pool_total == Decimal("1000000")
    assert snapshot.holdings_market_value == Decimal("250000")
    assert snapshot.holdings_as_of == date(2026, 11, 30)
    assert snapshot.current_equity == Decimal("0.25")
    assert compute_plan(make_policy(), snapshot, date(2026, 12, 1)).gap == Decimal("100000")


def test_loader_snapshot_ignores_derived_deployment_fields(monkeypatch, tmp_path):
    bogus = dict(SNAPSHOT_FIXTURE, deployment={"gap_to_target": 1, "monthly_amount": 2})
    monkeypatch.setattr(
        loader, "_IPS_LOCAL_YAML", _write_yaml(tmp_path / "a.yaml", bogus)
    )
    first = compute_plan(make_policy(), load_snapshot(), date(2026, 12, 1))
    monkeypatch.setattr(
        loader, "_IPS_LOCAL_YAML", _write_yaml(tmp_path / "b.yaml", SNAPSHOT_FIXTURE)
    )
    second = compute_plan(make_policy(), load_snapshot(), date(2026, 12, 1))
    assert first.gap == second.gap == Decimal("100000")
    assert first.equity_amount == second.equity_amount == Decimal("4167")


@pytest.mark.parametrize(
    "dotted",
    [
        "pool.total",
        "allocation.current.equity",
        "allocation.current.fixed_income",
        "allocation.current.cash",
        "holdings.total_market_value",
        "holdings.as_of",
    ],
)
def test_loader_snapshot_rejects_missing_field(monkeypatch, tmp_path, dotted):
    snapshot_path = _write_yaml(tmp_path / "ips.local.yaml", _drop(dotted))
    monkeypatch.setattr(loader, "_IPS_LOCAL_YAML", snapshot_path)
    with pytest.raises(AllocationConfigError) as excinfo:
        load_snapshot()
    assert dotted in str(excinfo.value)


def test_loader_snapshot_rejects_bad_yaml(monkeypatch, tmp_path):
    bad = tmp_path / "ips.local.yaml"
    bad.write_text("pool: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(loader, "_IPS_LOCAL_YAML", bad)
    with pytest.raises(AllocationConfigError) as excinfo:
        load_snapshot()
    assert "YAML 解析失败" in str(excinfo.value)


def test_loader_policy_rejects_unsupported_execution_day(monkeypatch, tmp_path):
    raw = yaml.safe_load((_REPO_ROOT / "config" / "ips.yaml").read_text(encoding="utf-8"))
    raw["deployment"]["execution_day"] = "first_monday"
    policy_path = _write_yaml(tmp_path / "ips.yaml", raw)
    monkeypatch.setattr(loader, "_IPS_YAML", policy_path)
    with pytest.raises(AllocationConfigError) as excinfo:
        load_ips_policy()
    assert "execution_day" in str(excinfo.value)
