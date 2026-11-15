"""test/qa/allocation — QA 盲测夹具（T4，盲测；未读 `src/service/allocation/` 与 `test/`）。

盲测声明（只读清单）
--------------------
本套夹具与用例的断言只来自：
1. `openspec/changes/add-allocation-executor/specs/allocation-executor/spec.md`（R1–R10 / 28 Scenario）
2. `openspec/changes/add-allocation-executor/proposal.md`（成功标准 5 条 / 失败标准·反目标 / 假设 A1–A6、Q1–Q5）
3. `openspec/changes/add-allocation-executor/design.md`（CLI 契约、金额公式与取整、判定顺序、退出码 0/1/2）
4. 本目录 `test-design.md`（TC 表 + 机检契约 + 夹具口径）

**未读**：`src/service/allocation/`、`src/apps/cli.py` 的 ips 分支实现、`test/service/`、`test/apps/`。
夹具在 `tmp_path` 下自建 `config/ips.yaml`（政策：公开政策值）+ `config/ips.local.yaml`（合成快照），
**不依赖、不读取**仓库里的 `config/ips.local.yaml`（私人数值）；其余数字全部是本文件的合成数，
可手算复核（`test-design.md` §3）。

夹具假设（design 未逐字写明、按仓库先例 + 盲测可行性）
------------------------------------------------------
- 入口 = 既有 `src/apps/cli.py` 的 CLI（design「CLI 契约」），argv = `["ips", "plan", "--as-of", …] [--json]`；
  夹具以**子进程**调用 `python -m apps.cli`（黑盒，不 import 实现、不改实现）。
- 输入文件是 cwd 下的 `config/ips.yaml` / `config/ips.local.yaml`（design「输入」表，无路径覆盖参数）。
  为避免读到仓库里的**私人快照**（gitignored `config/ips.local.yaml`），会话级夹具把 `src/` 复制到临时仓库，
  在临时仓库根写合成 `config/`，再以 `cwd=临时仓库` 跑子进程——实现按它自己的根解析配置，测试只读合成数。
  若输出里找不到夹具快照的 `holdings.as_of`，夹具会报「配置未被隔离」而不是静默用仓库真值。
- `--json` 键名由 T3 定，本夹具按 `test-design.md` §2 的机检契约**宽容归一**（文档化别名 + 类型归一），
  值仍严格断言；缺字段时报出实际键名，便于 T5 对齐，不静默通过。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
#: 覆盖被测源码树（仅用于 T4/T5 的「断言能红」变异实验：指向一份被故意改坏的 src 副本，不碰仓库 src）。
SRC_UNDER_TEST = Path(os.environ.get("IPS_QA_SRC", str(REPO_ROOT / "src")))
_SKIP_DIRS = {"__pycache__", ".pytest_cache"}

_MISS = object()

#: 政策默认值 = 公开政策值（`config/ips.yaml` 25-30/41/45-53/57-67 的 tracked 值；无私人数据）。
POLICY = {
    "schema_version": "0.1",
    "allocation": {
        "target": {"equity": 0.35, "fixed_income": 0.45, "cash": 0.20},
        "equity_band": [0.30, 0.40],
    },
    "fixed_income_detail": {"migration": {"trial_ratio": 0.30}},
    "deployment": {
        "mode": "monthly_dca",
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

#: 合成快照默认值：与 spec R3 Scenario 同数（pool=1,000,000 / eq_mv=250,000），
#: 另带两个**派生字段陷阱值**（R1 Scenario 2：`gap_to_target` / `monthly_amount` 不得被当结果抄出）。
SNAPSHOT = {
    "updated_at": "2026-11-15",
    "pool": {"total": 1_000_000},
    "allocation": {"current": {"equity": 0.25, "fixed_income": 0.55, "cash": 0.20}},
    "holdings": {"total_market_value": 250_000, "as_of": "2026-11-15"},
    "deployment": {"gap_to_target": 987_654, "monthly_amount": 1},
}


def _clone(obj):
    return json.loads(json.dumps(obj))


def _deep_update(dst: dict, src: dict) -> dict:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_update(dst[key], value)
        else:
            dst[key] = value
    return dst


def _drop(doc: dict, path: tuple) -> None:
    node = doc
    for key in path[:-1]:
        node = node[key]
    node.pop(path[-1], None)


def _pick(mapping, *names):
    """按别名取字段（大小写不敏感）；未命中返回 `_MISS`。"""
    if not isinstance(mapping, dict):
        return _MISS
    for name in names:
        if name in mapping:
            return mapping[name]
    lower = {str(k).lower(): k for k in mapping}
    for name in names:
        key = lower.get(name.lower())
        if key is not None:
            return mapping[key]
    return _MISS


def _fail_missing(names: tuple, actual) -> None:
    pytest.fail(
        f"输出缺少机检字段 {names}（契约见 openspec/changes/add-allocation-executor/test-design.md §2）；"
        f"实际键 = {sorted(actual) if isinstance(actual, dict) else type(actual).__name__}"
    )


def field(obj, *names):
    value = _pick(obj, *names)
    if value is _MISS:
        _fail_missing(names, obj)
    return value


def nested(obj, *names):
    """取嵌套字段，未命中也返回 `_MISS`（供「可选字段」判断）。"""
    return _pick(obj, *names)


def values(obj) -> list:
    """递归收集所有叶子值（用于「回显里有没有这个数」这类与键名无关的断言）。"""
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


def numbers(obj) -> list:
    """叶子值中能转成数字的那些（含数字字符串）。"""
    out = []
    for value in values(obj):
        try:
            out.append(Decimal(str(value)))
        except Exception:  # noqa: BLE001 - 非数字叶子直接跳过
            continue
    return out


def yuan(value) -> Decimal:
    """金额归一到「元」（整数元）；非整数即判失败，避免用浮点容差掩盖取整错误。"""
    amount = Decimal(str(value))
    if amount != amount.to_integral_value():
        pytest.fail(f"金额不是整数元：{value!r}（spec R4：金额四舍五入到元）")
    return amount.quantize(Decimal("1"))


def plan_data(res) -> dict:
    """取 `--json` 解析结果；CLI 失败或输出不可解析时给出可执行失败信息。"""
    if res.data is None:
        pytest.fail(
            f"CLI 未返回可解析 JSON（rc={res.code}）；stdout={res.out[:400]!r}；stderr={res.err[:400]!r}"
            "（`--json` 契约见 test-design.md §2.1）"
        )
    return res.data


def equity_amount(plan) -> Decimal:
    """当月权益买入额（元）——键名宽容，值严格。"""
    value = _pick(plan, "equity_buy_amount", "equity_amount", "equity_buy", "monthly_amount", "buy_amount")
    if value is _MISS:
        _fail_missing(("equity_buy_amount", "equity_amount", "equity_buy", "monthly_amount"), plan)
    return yuan(value)


def categories(plan) -> list[tuple[str, object]]:
    """类别分配归一为 `[(类别名, 金额), …]`；支持 list[dict] 与 dict 两种形态。"""
    raw = field(plan, "categories", "allocation", "category_allocation", "category")
    if isinstance(raw, dict):
        return [(str(k), v) for k, v in raw.items()]
    out: list[tuple[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            out.append((str(item), None))
            continue
        name = _pick(item, "category", "name", "label", "kind", "bucket")
        amount = _pick(item, "amount", "value", "yuan", "buy_amount", "money")
        out.append(("" if name is _MISS else str(name), None if amount is _MISS else amount))
    return out


def amount_of(plan, *needles) -> Decimal:
    """取类别分配里名字包含任一关键词的金额；找不到即失败。"""
    for name, amount in categories(plan):
        if any(needle in name for needle in needles):
            if amount is None:
                pytest.fail(f"类别「{name}」缺金额字段（见 test-design.md §2.2）")
            return yuan(amount)
    pytest.fail(f"类别分配中找不到含 {needles} 的类别；实际 = {categories(plan)}")


def defer_state(plan) -> tuple[bool, str]:
    """顺延判定归一为 (是否顺延, 理由文本)。"""
    raw = nested(plan, "defer", "deferral", "deferred", "skip")
    if raw is _MISS:
        raw = nested(plan, "deferred")
    reasons = nested(plan, "reasons", "reason", "notes", "explanations")
    reason_text = ""
    if isinstance(reasons, str):
        reason_text = reasons
    elif isinstance(reasons, (list, tuple)):
        reason_text = "；".join(str(item) for item in reasons)
    if isinstance(raw, bool):
        return raw, reason_text
    if isinstance(raw, dict):
        flag = _pick(raw, "deferred", "is_deferred", "active", "flag", "skip", "value")
        own_reason = _pick(raw, "reason", "why", "detail")
        if isinstance(own_reason, str) and own_reason:
            reason_text = own_reason if not reason_text else f"{reason_text}；{own_reason}"
        if flag is _MISS:
            return False, reason_text
        return bool(flag), reason_text
    if isinstance(raw, str):
        return bool(raw.strip()) and raw.strip().lower() not in {"none", "no", "无"}, reason_text
    return bool(raw is not _MISS and raw), reason_text


def rebalance_hints(plan) -> list[dict]:
    raw = field(plan, "rebalance_hints", "rebalance", "rebalance_hint", "rebalance_alerts")
    return [item for item in raw if isinstance(item, dict)]


def hint_deviation(hint: dict) -> Decimal:
    value = _pick(hint, "deviation_pp", "deviation", "pp", "delta_pp", "delta", "gap_pp")
    if value is _MISS:
        pytest.fail(f"再平衡提示缺偏离字段（见 test-design.md §2.2）；提示 = {hint}")
    return Decimal(str(value))


def hint_bucket(hint: dict) -> str:
    value = _pick(hint, "bucket", "name", "category", "label", "target_bucket")
    if value is _MISS:
        pytest.fail(f"再平衡提示缺桶名字段（见 test-design.md §2.2）；提示 = {hint}")
    return str(value)


def staleness(plan) -> dict:
    return field(plan, "staleness", "freshness", "timeliness", "stale", "data_freshness")


def stale_days_of(plan) -> Decimal:
    info = staleness(plan)
    value = _pick(info, "days", "diff_days", "days_diff", "age_days", "elapsed_days")
    if value is _MISS:
        pytest.fail(f"时效字段缺「天数差」（见 test-design.md §2.2）；实际 = {info}")
    return Decimal(str(value))


def stale_threshold_of(plan) -> Decimal:
    info = staleness(plan)
    value = _pick(info, "threshold_days", "threshold", "stale_days", "limit_days", "max_days")
    if value is _MISS:
        pytest.fail(f"时效字段缺「阈值」（见 test-design.md §2.2）；实际 = {info}")
    return Decimal(str(value))


def cash_state(plan) -> tuple[bool, object]:
    """现金不足提示归一为 (是否触发, 补足金额或 None)。"""
    raw = nested(plan, "cash_hint", "cash", "cash_shortfall", "cash_insufficient")
    if raw is _MISS:
        raw = nested(plan, "cash_floor_hint")
    if raw is _MISS or raw is None:
        return False, None
    if isinstance(raw, bool):
        return raw, None
    if isinstance(raw, dict):
        flag = _pick(raw, "insufficient", "triggered", "short", "active", "is_insufficient")
        amount = _pick(raw, "shortfall", "top_up", "needed", "amount", "insufficient_amount", "to_fill")
        return bool(flag is not _MISS and flag), (None if amount is _MISS else amount)
    if isinstance(raw, (int, float, str)):
        return True, raw
    return False, None


def _assert_isolated(data: dict, snapshot: dict) -> None:
    """确认 CLI 真的读到了夹具写的快照（而不是仓库里的 `config/ips.local.yaml`）。"""
    expected_as_of = snapshot["holdings"]["as_of"]
    if expected_as_of in {str(v) for v in values(data)}:
        return
    pytest.fail(
        f"配置未被隔离：输出里找不到夹具快照的 holdings.as_of={expected_as_of}，"
        "CLI 可能按仓库根（而非 cwd）解析 config/ips.yaml|ips.local.yaml —— 夹具无法注入合成快照，"
        "请 T5 与实现对齐（test-design.md §2.4）"
    )


@pytest.fixture
def helpers():
    """归一化读取器集合（值断言严格，键名宽容）。"""
    return SimpleNamespace(
        field=field,
        nested=nested,
        values=values,
        numbers=numbers,
        yuan=yuan,
        plan_data=plan_data,
        equity_amount=equity_amount,
        categories=categories,
        amount_of=amount_of,
        defer_state=defer_state,
        rebalance_hints=rebalance_hints,
        hint_deviation=hint_deviation,
        hint_bucket=hint_bucket,
        staleness=staleness,
        stale_days_of=stale_days_of,
        stale_threshold_of=stale_threshold_of,
        cash_state=cash_state,
    )


@pytest.fixture(scope="session")
def repo_copy(tmp_path_factory):
    """会话级「临时仓库」：复制 `src/`，`config/` 留空（每个用例自己写合成政策与快照）。

    为什么要复制：`ips plan` 的输入是 `config/ips.yaml` + `config/ips.local.yaml`（design「CLI 契约」，
    无路径覆盖参数）。在仓库原地跑会读到**真实的私人快照** `config/ips.local.yaml`（gitignored），
    既不可控也不该被测试触碰。复制 `src/` 后在临时仓库里跑子进程，即可让实现按它自己的根目录解析配置，
    同时保证测试只读夹具合成数（实现无需为 QA 加测试专用参数）。
    """
    root = tmp_path_factory.mktemp("ips-repo")
    shutil.copytree(
        SRC_UNDER_TEST, root / "src",
        ignore=shutil.ignore_patterns(*_SKIP_DIRS),
    )
    (root / "config").mkdir()
    example = REPO_ROOT / "config" / "app.example.yaml"
    if example.exists():  # 既有 config_loader 可能需要 app.yaml（缺失时 bootstrap from example）
        (root / "config" / "app.yaml").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    return root


@pytest.fixture
def run_plan(repo_copy):
    """跑一次 `ips plan`（黑盒，子进程）：在临时仓库的 `config/` 写合成政策与快照，返回执行结果。

    参数
    ----
    as_of: 计算日（`--as-of`）
    policy / snapshot: 深合并进默认政策 / 默认快照（合成数）
    drop_policy / drop_snapshot: 要删除的键路径列表（测缺键 → 拒绝），
        如 `[("allocation", "target", "cash")]` / `[("holdings", "as_of")]`
    as_of_arg: 覆写传给 CLI 的 `--as-of`（测坏日期格式）
    json_out: False 时走人类可读文本（测 stderr / 文案）
    extra_argv: 追加参数
    """
    config_dir = repo_copy / "config"

    def _run(as_of: str = "2026-11-15", *, policy=None, snapshot=None, drop_policy=(), drop_snapshot=(),
             json_out=True, as_of_arg=None, extra_argv=()) -> SimpleNamespace:
        policy_doc = _deep_update(_clone(POLICY), policy or {})
        snapshot_doc = _deep_update(_clone(SNAPSHOT), snapshot or {})
        if "as_of" not in ((snapshot or {}).get("holdings") or {}):
            snapshot_doc["holdings"]["as_of"] = as_of
        for path in drop_policy:
            _drop(policy_doc, path)
        for path in drop_snapshot:
            _drop(snapshot_doc, path)

        (config_dir / "ips.yaml").write_text(json.dumps(policy_doc, ensure_ascii=False), encoding="utf-8")
        (config_dir / "ips.local.yaml").write_text(
            json.dumps(snapshot_doc, ensure_ascii=False), encoding="utf-8")

        argv = ["ips", "plan", "--as-of", as_of_arg or as_of]
        if json_out:
            argv.append("--json")
        argv.extend(extra_argv)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_copy / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-m", "apps.cli", *argv],
            cwd=str(repo_copy), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120, stdin=subprocess.DEVNULL,
        )
        data = None
        if json_out and proc.stdout.strip():
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                data = None
        result = SimpleNamespace(
            code=int(proc.returncode),
            out=proc.stdout,
            err=proc.stderr,
            combined=proc.stdout + proc.stderr,
            data=data,
            snapshot=snapshot_doc,
            policy=policy_doc,
        )
        if result.code == 0 and isinstance(data, dict):
            _assert_isolated(data, snapshot_doc)
        return result

    return _run

