"""test/qa/allocation/test_plan_output.py — T4 QA 盲测用例（`ips plan` 的金额/判定/拒绝/边界）。

盲测：断言只来自 spec R1–R10（28 Scenario）、proposal 成功/失败标准、design「CLI 契约 / 金额公式与取整 /
判定顺序 / 退出码」，未读 `src/service/allocation/`、`src/apps/cli.py` 的 ips 分支实现、`test/service/`。
逐条溯源见 `openspec/changes/add-allocation-executor/test-design.md` §1（TC 表）。

覆盖分布（37 条）：
- R1 单一来源：2（政策改动重算 / 派生字段不作输入）
- R2 执行日：3（11 月 / 12 月 / 不择时）
- R3 缺口与月数：3（手算+回显 / 幂等 / 缺权益市值拒绝）
- R4 金额取整与期末：7（均摊 / 目标月补齐 / 期末结束 / 负缺口 / `.5` 向上 / `.4` 向下 / 不超缺口）
- R5 类别：3（迁移月 / 定投月宽基 / 迁移后不再出迁移）
- R6 顺延：4（0.36 / 0.42 提示 / 不产生待补额度 / 恰好 0.35 不顺延）
- R7 时效：4（过期 14 天 / 恰好 7 天 / 缺 as_of / 未来快照）
- R8 再平衡：3（超 5pp 提示 / 带内不提示 / 提示不产调仓金额）
- R9 现金：2（不足金额 / 充足不提示）
- R10 零 LLM 与边界：3（离线零 LLM / 不下单选股 / 不重建账本体检）
- 配置缺键 / 坏日期：3（缺政策键 / 缺 pool.total / `--as-of` 坏格式）
"""

from __future__ import annotations

import re
import socket
from decimal import Decimal

import pytest

ALLOWED_CATEGORY_TOKENS = ("宽基", "ETF", "固收", "迁移", "现金", "权益")


def _leaves(obj) -> list:
    """递归收集叶子值（与键名无关）。"""
    out: list = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        else:
            out.append(node)

    walk(obj)
    return out


def _has_number(obj, target, tol: str = "1e-9") -> bool:
    """输出里是否回显了某个数（与键名无关，容 1e-9 浮点尾巴）。"""
    goal = Decimal(str(target))
    for value in _leaves(obj):
        try:
            number = Decimal(str(value))
        except Exception:  # noqa: BLE001 - 非数字叶子跳过
            continue
        if abs(number - goal) <= Decimal(tol):
            return True
    return False


def _hint_text(hint: dict) -> str:
    """提示的桶名/说明拼成一段文本（键名宽容：bucket/label/message 任一含中文即可）。"""
    return " ".join(str(value) for value in _leaves(hint))


def _looks_like_security_code(value) -> bool:
    """6 位纯数字**字符串**才算证券代码（金额是数字叶子，不算）。"""
    return isinstance(value, str) and re.fullmatch(r"\d{6}", value) is not None


def _text(res) -> str:
    return res.combined


# ── R1 政策与快照单一来源 ──────────────────────────────────────────────────────

def test_tc_r1_01_policy_change_recomputes_amount(run_plan, helpers):
    """R1 Scenario 1：把 allocation.target.equity 改为 0.40，金额按新政策重算并回显来源比例。"""
    baseline = run_plan("2026-12-01")
    assert baseline.code == 0, _text(baseline)
    base_plan = helpers.plan_data(baseline)
    assert helpers.equity_amount(base_plan) == Decimal("4167")

    changed = run_plan("2026-12-01", policy={"allocation": {"target": {"equity": 0.40}}})
    assert changed.code == 0, _text(changed)
    plan = helpers.plan_data(changed)
    # gap = 0.40 × 1,000,000 − 250,000 = 150,000；remaining = 24 → 150000/24 = 6250
    assert helpers.yuan(helpers.field(plan, "gap", "equity_gap")) == Decimal("150000")
    assert helpers.equity_amount(plan) == Decimal("6250")
    echo = helpers.field(plan, "echo", "inputs", "echo_inputs", "policy")
    assert _has_number(echo, 0.40), f"回显里没有新政策比例 0.40；echo={echo}"


def test_tc_r1_02_derived_fields_are_not_copied(run_plan, helpers):
    """R1 Scenario 2：快照里的 gap_to_target / monthly_amount 改成错误值，输出金额不变。"""
    res = run_plan("2026-12-01", snapshot={"deployment": {"gap_to_target": 9_999_999, "monthly_amount": 7}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.yuan(helpers.field(plan, "gap", "equity_gap")) == Decimal("100000")
    assert helpers.equity_amount(plan) == Decimal("4167")


# ── R2 固定执行日与指令时点 ────────────────────────────────────────────────────

def test_tc_r2_01_last_thursday_november(run_plan, helpers):
    """R2 Scenario 1：计算日 2026-11-15 → 执行日 2026-11-26。"""
    res = run_plan("2026-11-15")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert str(helpers.field(plan, "execution_day", "exec_day", "day")) == "2026-11-26"
    assert str(helpers.field(plan, "execution_month", "exec_month", "month")) == "2026-11"


def test_tc_r2_02_execution_day_passed_takes_next_month(run_plan, helpers):
    """R2 Scenario 2：计算日 2026-12-01 → 执行日 2026-12-31、执行月 2026-12。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert str(helpers.field(plan, "execution_day", "exec_day", "day")) == "2026-12-31"
    assert str(helpers.field(plan, "execution_month", "exec_month", "month")) == "2026-12"


def test_tc_r2_03_no_market_timing(run_plan, helpers):
    """R2 Scenario 3：同一快照在 2026-12-30 与 2026-12-31 两次请求同一执行月，金额/类别/顺延一致。"""
    before = run_plan("2026-12-30")
    on_day = run_plan("2026-12-31")
    assert before.code == 0 and on_day.code == 0, _text(before) + _text(on_day)
    first, second = helpers.plan_data(before), helpers.plan_data(on_day)
    assert helpers.equity_amount(first) == helpers.equity_amount(second), "同一执行月金额不一致（存在择时依赖）"
    assert helpers.categories(first) == helpers.categories(second), "同一执行月类别不一致"
    assert helpers.defer_state(first) == helpers.defer_state(second)


# ── R3 缺口与剩余投放月数 ──────────────────────────────────────────────────────

def test_tc_r3_01_gap_and_remaining_months_hand_calc(run_plan, helpers):
    """R3 Scenario 1：pool=1e6、eq_mv=250k、执行月 2026-12 → 缺口 100,000、剩余 24，且回显公式输入。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.yuan(helpers.field(plan, "gap", "equity_gap")) == Decimal("100000")
    assert int(helpers.field(plan, "remaining_months", "remaining", "months_left")) == 24
    echo = helpers.field(plan, "echo", "inputs", "echo_inputs", "policy")
    for expected in (0.35, 1_000_000, 250_000, 24):
        assert _has_number(echo, expected), f"回显缺公式输入 {expected}；echo={echo}"
    # 「可手算到元」：缺口结果与剩余月数必须出现在输出里（scenario 的 `= 100,000` 与 `24 个月`）
    assert _has_number(plan, 100_000), f"输出缺缺口结果 100,000；plan={plan}"


def test_tc_r3_02_idempotent(run_plan):
    """R3 Scenario 2：同输入连续执行两次，输出逐字段一致（JSON 与文本都一致）。"""
    first = run_plan("2026-12-01")
    second = run_plan("2026-12-01")
    assert first.code == 0 and second.code == 0, _text(first) + _text(second)
    assert first.data == second.data
    assert first.out == second.out


def test_tc_r3_03_missing_equity_market_value_rejects(run_plan):
    """R3 Scenario 3：快照缺 holdings.total_market_value → 非零退出码，不产出金额与类别。"""
    res = run_plan("2026-12-01", drop_snapshot=[("holdings", "total_market_value")])
    assert res.code != 0, _text(res)
    assert res.data is None
    assert re.search(r"total_market_value|权益市值|缺", res.combined), res.combined


# ── R4 当月金额、取整与期末归零 ────────────────────────────────────────────────

def test_tc_r4_01_regular_month_rounds_to_yuan(run_plan, helpers):
    """R4 Scenario 1：缺口 100,000、剩余 24 → 当月 4,167 元，并回显取整规则。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.equity_amount(plan) == Decimal("4167")
    echo = helpers.field(plan, "echo", "inputs", "echo_inputs", "policy")
    echo_text = " ".join(str(value) for value in helpers.values(echo)).lower()
    assert "四舍五入" in echo_text or "round" in echo_text or "取整" in echo_text, echo


def test_tc_r4_02_target_month_fills_gap(run_plan, helpers):
    """R4 Scenario 2：执行月 = 目标月 2028-11 → 当月买入 = 当期全部缺口，并标注投放期结束。"""
    res = run_plan("2028-11-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    gap = helpers.yuan(helpers.field(plan, "gap", "equity_gap"))
    assert helpers.equity_amount(plan) == gap
    assert "投放期结束" in _text(res), _text(res)


def test_tc_r4_03_after_period_ends_no_buy(run_plan, helpers):
    """R4 Scenario 3：执行月晚于目标月（2028-12）→ 当月金额 0，说明投放期已结束，不产类别建议。"""
    res = run_plan("2028-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.equity_amount(plan) == Decimal("0")
    assert "已结束" in _text(res), _text(res)


def test_tc_r4_04_negative_gap_no_sell(run_plan, helpers):
    """R4 Scenario 4：权益市值高于目标（缺口 −50,000）→ 当月金额 0，不产出卖出/减仓金额。"""
    res = run_plan("2026-12-01", snapshot={"holdings": {"total_market_value": 400_000}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.yuan(helpers.field(plan, "gap", "equity_gap")) == Decimal("-50000")
    assert helpers.equity_amount(plan) == Decimal("0")
    for name, amount in helpers.categories(plan):
        if amount is not None:
            assert helpers.yuan(amount) >= 0, f"出现负金额类别 {name}={amount}"


def test_tc_r4_05_round_half_up(run_plan, helpers):
    """R4 取整边界：缺口 5、剩余 2 → 5/2 = 2.5 → `.5` 向上 = 3 元（proposal A2）。"""
    res = run_plan(
        "2028-10-01",
        snapshot={"pool": {"total": 1000}, "holdings": {"total_market_value": 345},
                  "allocation": {"current": {"equity": 0.30, "fixed_income": 0.50, "cash": 0.20}}},
    )
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.yuan(helpers.field(plan, "gap", "equity_gap")) == Decimal("5")
    assert int(helpers.field(plan, "remaining_months", "remaining", "months_left")) == 2
    assert helpers.equity_amount(plan) == Decimal("3")


def test_tc_r4_06_round_below_half_down(run_plan, helpers):
    """R4 取整边界：缺口 12、剩余 5 → 2.4 → 2 元（向下）。"""
    res = run_plan(
        "2028-07-01",
        snapshot={"pool": {"total": 1000}, "holdings": {"total_market_value": 338},
                  "allocation": {"current": {"equity": 0.30, "fixed_income": 0.50, "cash": 0.20}}},
    )
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert int(helpers.field(plan, "remaining_months", "remaining", "months_left")) == 5
    assert helpers.equity_amount(plan) == Decimal("2")


def test_tc_r4_07_monthly_amount_not_exceed_gap(run_plan, helpers):
    """R4「MUST NOT 因取整使某一月超出当期缺口」：常规月金额 ≤ 当期缺口。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    gap = helpers.yuan(helpers.field(plan, "gap", "equity_gap"))
    amount = helpers.equity_amount(plan)
    assert 0 < amount <= gap, f"当月 {amount} 超出缺口 {gap}"


# ── R5 类别分配 ───────────────────────────────────────────────────────────────

def test_tc_r5_01_migration_month_only_fixed_income(run_plan, helpers):
    """R5 Scenario 1：执行月 2026-11、pool=1e6 → 权益 0、固收迁移 135,000，标注定投自 2026-12 起。"""
    res = run_plan("2026-11-15")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.equity_amount(plan) == Decimal("0")
    assert helpers.amount_of(plan, "固收", "迁移") == Decimal("135000")
    assert "2026-12" in _text(res), _text(res)


def test_tc_r5_02_investment_month_buys_broad_etf_only(run_plan, helpers):
    """R5 Scenario 2：执行月 2026-12 → 权益类别为「宽基 ETF」，金额 = 当月买入额，输出无具体代码。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    amount = helpers.equity_amount(plan)
    equity_names = [name for name, value in helpers.categories(plan) if "宽基" in name or "ETF" in name]
    assert equity_names, f"没有「宽基 ETF」类别；实际 = {helpers.categories(plan)}"
    assert helpers.amount_of(plan, "宽基", "ETF") == amount
    for value in helpers.values(plan):
        assert not _looks_like_security_code(value), f"输出出现 6 位代码：{value}"


def test_tc_r5_03_no_migration_after_start(run_plan, helpers):
    """R5 Scenario 3：执行月 2026-12 及之后 → 不再出现固收迁移金额，现金新增为 0。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    for name, amount in helpers.categories(plan):
        if "迁移" in name or "固收" in name:
            assert amount is None or helpers.yuan(amount) == 0, f"定投月仍输出迁移金额 {name}={amount}"
    for name, amount in helpers.categories(plan):
        if "现金" in name and amount is not None:
            assert helpers.yuan(amount) == 0


# ── R6 权益超限顺延 ───────────────────────────────────────────────────────────

def test_tc_r6_01_defer_when_equity_above_35(run_plan, helpers):
    """R6 Scenario 1：权益 0.36（> 0.35）且缺口为正 → 当月 0 + 顺延理由，不出现买入金额。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.36, "fixed_income": 0.44, "cash": 0.20}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    deferred, reason = helpers.defer_state(plan)
    assert deferred is True, f"未判定顺延；plan={plan}"
    assert reason, "顺延缺理由"
    assert helpers.equity_amount(plan) == Decimal("0")
    assert re.search(r"顺延|0\.36|36%", _text(res)), _text(res)


def test_tc_r6_02_over_40_percent_hints_only(run_plan, helpers):
    """R6 Scenario 2：权益 0.42 → 仍顺延，并追加「权益超过 R1 上限 40%（仅提示）」；不产减仓金额。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.42, "fixed_income": 0.38, "cash": 0.20}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    deferred, _ = helpers.defer_state(plan)
    assert deferred is True
    text = _text(res)
    assert "40" in text, text
    assert "提示" in text, text
    for name, amount in helpers.categories(plan):
        assert "减仓" not in name and "调仓" not in name
        if amount is not None:
            assert helpers.yuan(amount) >= 0


def test_tc_r6_03_no_carryover_bucket(run_plan, helpers):
    """R6 Scenario 3：2026-12 顺延、2027-01 权益回落 0.34 → 剩余 23，金额按新缺口重算，无「待补」额度。"""
    december = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.36, "fixed_income": 0.44, "cash": 0.20}}})
    assert december.code == 0, _text(december)
    assert helpers.defer_state(helpers.plan_data(december))[0] is True

    january = run_plan("2027-01-01", snapshot={"allocation": {"current": {
        "equity": 0.34, "fixed_income": 0.46, "cash": 0.20}}})
    assert january.code == 0, _text(january)
    plan = helpers.plan_data(january)
    assert int(helpers.field(plan, "remaining_months", "remaining", "months_left")) == 23
    # 缺口 100,000 / 23 = 4347.8… → 4348（无上期待补额度，否则会明显偏离）
    assert helpers.equity_amount(plan) == Decimal("4348")
    assert not re.search(r"待补|上期结转|累积", _text(january)), _text(january)


def test_tc_r6_04_exactly_35_percent_is_not_deferred(run_plan, helpers):
    """R6 边界：权益恰好 0.35（等于阈值）→ 不顺延（spec「高于」= 严格大于）。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.35, "fixed_income": 0.45, "cash": 0.20}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.defer_state(plan)[0] is False
    assert helpers.equity_amount(plan) == Decimal("4167")


# ── R7 快照时效拒绝 ───────────────────────────────────────────────────────────

def test_tc_r7_01_stale_snapshot_rejected(run_plan):
    """R7 Scenario 1：as_of=2026-11-01、计算日 2026-11-15（14 天）→ 非零退出 + 数据过期说明，不出金额。"""
    res = run_plan("2026-11-15", snapshot={"holdings": {"as_of": "2026-11-01"}})
    assert res.code != 0, _text(res)
    text = _text(res)
    assert "数据过期" in text, text
    assert "2026-11-01" in text and "14" in text and "7" in text, text
    assert res.data is None


def test_tc_r7_02_exactly_seven_days_allowed(run_plan, helpers):
    """R7 Scenario 2：as_of 距计算日恰好 7 天 → 正常产出，不出现过期拒绝。"""
    res = run_plan("2026-12-09", snapshot={"holdings": {"as_of": "2026-12-02"}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.stale_days_of(plan) == Decimal("7")
    assert helpers.equity_amount(plan) > 0


def test_tc_r7_03_missing_as_of_rejected(run_plan):
    """R7 Scenario 3：快照未提供 as_of → 非零退出码并说明缺少快照日期，不产出指令。"""
    res = run_plan("2026-11-15", drop_snapshot=[("holdings", "as_of")])
    assert res.code != 0, _text(res)
    assert re.search(r"as_of|快照日期|缺", _text(res)), _text(res)
    assert res.data is None


def test_tc_r7_04_future_snapshot_rejected(run_plan):
    """R7「as_of 晚于计算日同样拒绝」：未来快照 2026-11-20 vs 计算日 2026-11-15 → 拒绝。"""
    res = run_plan("2026-11-15", snapshot={"holdings": {"as_of": "2026-11-20"}})
    assert res.code != 0, _text(res)
    assert res.data is None


# ── R8 再平衡提示 ─────────────────────────────────────────────────────────────

def test_tc_r8_01_deviation_over_5pp_hints(run_plan, helpers):
    """R8 Scenario 1：固收 0.30 vs 目标 0.45（−15pp）→ 再平衡提示；当月权益买入额与无提示时相同。"""
    baseline = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.35, "fixed_income": 0.45, "cash": 0.20}}})
    hinted = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.25, "fixed_income": 0.30, "cash": 0.45}}})
    assert baseline.code == 0 and hinted.code == 0, _text(baseline) + _text(hinted)
    plan = helpers.plan_data(hinted)
    hints = helpers.rebalance_hints(plan)
    assert hints, f"偏离 15pp 却没有再平衡提示；plan={plan}"
    fixed_income_hints = [hint for hint in hints if "固收" in _hint_text(hint)]
    assert fixed_income_hints, f"没有固收桶的再平衡提示；hints={hints}"
    deviations = [helpers.hint_deviation(hint) for hint in fixed_income_hints]
    assert any(abs(value) == Decimal("15") for value in deviations), deviations
    base_amount = helpers.yuan(helpers.field(helpers.plan_data(baseline), "equity_buy_amount",
                                             "equity_amount", "equity_buy", "monthly_amount"))
    hint_amount = helpers.equity_amount(plan)
    assert hint_amount == base_amount, "再平衡提示改变了当月权益买入额"


def test_tc_r8_02_within_band_no_hint(run_plan, helpers):
    """R8 Scenario 2：三桶偏离绝对值均 ≤ 5pp → 无再平衡提示、无调仓建议。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.33, "fixed_income": 0.47, "cash": 0.20}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    assert helpers.rebalance_hints(plan) == [], f"带内仍给出提示：{helpers.rebalance_hints(plan)}"


def test_tc_r8_03_hints_do_not_create_trade_amounts(run_plan, helpers):
    """R8：提示不得产出调仓/买卖/减仓金额——类别里只能是权益/固收/现金三桶。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.25, "fixed_income": 0.30, "cash": 0.45}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    for name, _amount in helpers.categories(plan):
        assert any(token in name for token in ALLOWED_CATEGORY_TOKENS), f"出现非三桶类别：{name}"
        assert "调仓" not in name and "减仓" not in name
    assert not re.search(r"调仓金额|减仓金额|卖出金额", _text(res)), _text(res)


# ── R9 现金不足提示 ───────────────────────────────────────────────────────────

def test_tc_r9_01_cash_shortfall_amount(run_plan, helpers):
    """R9 Scenario 1：pool=1e6、现金市值 150,000（15% < 20%）→ 提示 + 补足 50,000，权益买入额不变。"""
    baseline = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.35, "fixed_income": 0.45, "cash": 0.20}}})
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.25, "fixed_income": 0.60, "cash": 0.15}}})
    assert baseline.code == 0 and res.code == 0, _text(baseline) + _text(res)
    plan = helpers.plan_data(res)
    triggered, amount = helpers.cash_state(plan)
    assert triggered is True, f"现金 15% 未提示；plan={plan}"
    assert helpers.yuan(amount) == Decimal("50000")
    expected = helpers.yuan(helpers.field(helpers.plan_data(baseline), "equity_buy_amount",
                                          "equity_amount", "equity_buy", "monthly_amount"))
    actual = helpers.equity_amount(plan)
    assert actual == expected, "现金不足提示改变了当月权益买入额（不得升格为硬门禁）"


def test_tc_r9_02_cash_sufficient_no_hint(run_plan, helpers):
    """R9 Scenario 2：现金占比 0.22（≥ 20%）→ 不提示、不出现补足金额。"""
    res = run_plan("2026-12-01", snapshot={"allocation": {"current": {
        "equity": 0.33, "fixed_income": 0.45, "cash": 0.22}}})
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    triggered, amount = helpers.cash_state(plan)
    assert triggered is False, f"现金充足仍提示；plan={plan}"
    assert amount is None or helpers.yuan(amount) == 0


# ── R10 零 LLM 与工单边界 ─────────────────────────────────────────────────────

def test_tc_r10_01_offline_and_zero_llm(run_plan, monkeypatch):
    """R10 Scenario 1：全过程不发起网络请求、不调用 LLM，金额只由输入与 ips 决定。"""
    def _no_network(*_args, **_kwargs):
        raise AssertionError("执行器发起了网络连接（spec R10：MUST NOT 联网取数）")

    monkeypatch.setattr(socket, "socket", _no_network)
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    lowered = _text(res).lower()
    for token in ("openai", "llm", "gpt", "anthropic", "chat/completions"):
        assert token not in lowered, f"输出出现 LLM 痕迹：{token}"


def test_tc_r10_02_no_order_or_underlying_picks(run_plan, helpers):
    """R10 Scenario 2：输出只含类别与金额，不含具体代码、下单指令或交易动作。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    plan = helpers.plan_data(res)
    text = _text(res)
    for token in ("下单", "买入指令", "清仓", "减仓建议", "推荐股票", "股票代码"):
        assert token not in text, f"输出越界出现「{token}」"
    for value in helpers.values(plan):
        assert not _looks_like_security_code(value), f"输出出现 6 位证券代码：{value}"
    for name, _amount in helpers.categories(plan):
        assert any(token in name for token in ALLOWED_CATEGORY_TOKENS), f"出现具体标的类别：{name}"


def test_tc_r10_03_no_ledger_or_health_check(run_plan):
    """R10 Scenario 3：快照只有三桶占比 + pool + 权益市值（无成交明细）→ 照常产出，不推导账本/体检。"""
    res = run_plan("2026-12-01")
    assert res.code == 0, _text(res)
    text = _text(res)
    for token in ("账本", "持仓成本", "清仓", "减仓", "持有建议"):
        assert token not in text, f"输出越界出现「{token}」"


# ── 配置缺键 / 坏日期（proposal 失败标准：缺键不得按 0 继续） ─────────────────

def test_tc_cfg_01_missing_policy_key_rejects(run_plan):
    """缺政策键（allocation.target.cash）→ 非零退出码，不按默认值继续，不产出金额。"""
    res = run_plan("2026-12-01", drop_policy=[("allocation", "target", "cash")])
    assert res.code != 0, _text(res)
    assert res.data is None
    assert not re.search(r"当月|买入额", res.out), res.out


def test_tc_cfg_02_missing_pool_total_rejects(run_plan):
    """缺快照键（pool.total）→ 非零退出码，不产出金额与类别。"""
    res = run_plan("2026-12-01", drop_snapshot=[("pool", "total")])
    assert res.code != 0, _text(res)
    assert res.data is None


def test_tc_cfg_03_bad_as_of_format_rejects(run_plan):
    """`--as-of` 非 ISO 日期 → 退出码非 0（design：用法/数据错误 1），不得抛未捕获异常。"""
    res = run_plan("2026-12-01", as_of_arg="2026-13-40")
    assert res.code != 0, _text(res)
    assert "Traceback" not in res.err, res.err


if __name__ == "__main__":  # pragma: no cover - 便于本地单跑
    raise SystemExit(pytest.main([__file__]))
