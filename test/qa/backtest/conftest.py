"""test/qa/backtest — QA 盲测夹具（T4-exec；已按 T2-fix-4 契约对齐）。

盲测声明（只读清单）
--------------------
断言只来自：
1. `specs/backtest-engine/spec.md`（19 Requirement / 56 Scenario）
2. `proposal.md`（成功标准 S1–S5 / 失败标准 F1–F8）
3. `design.md` §4.1 契约（T2-fix-4 后）：`BacktestConfig` 全量键 + `GateCriteria` + 成本 spec
   （`CommissionSpec/StampTaxSpec/TransferFeeSpec/SlippageTierSpec/LiquidityCapSpec`）、
   事件载体 `EventObservation` + `load_event_observations` + `compute_event_study(observations, *, cfg)`、
   `GateStateMachine(registry, *, cfg)`、`mark_burnt`（追加执行行）、`attribution(returns, factors, benchmarks)`、
   R11 `visible_from = ann_date`（缺才回退）、异常清单、§6.3 退出码、§6.4 配置契约源
4. `test-design.md`（§1 TC 表 / §2.3 退出码 / §10 夹具）
5. `test/qa/README.md`（目录约定）

**未读**：`src/service/backtest/`、`src/data_provider/backtest/`、`test/service/backtest/`。
配置**不依赖** `config/app.yaml` 存在（该文件被 gitignore；契约源是 `config/app.example.yaml` 与 design §4.1），
夹具在 `tmp_path` 下自建骨架。一条 TC = 一个测试函数（共 56 条）。
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"

#: 显著性阈值（**测试输入**：design 的 `BacktestConfig` 不承载 alpha——KQ-5 判据待 Owner 答复，不预埋进契约）
#: 通过 `alpha` fixture 暴露给用例（避免跨文件 import conftest）。
ALPHA = 0.05

#: 必须键（design §4.1 `BacktestConfig`：results_dir/registry_store_path/segments/windows/max_delay_days/min_events）
CFG_REQUIRED = {
    "segments": {"train": ["2015-01-01", "2020-12-31"],
                 "validation": ["2021-01-01", "2023-12-31"],
                 "out_of_sample": ["2024-01-01", "2026-11-30"]},
    "windows": [20, 60],
    "max_delay_days": 5,
    "min_events": 30,
}

#: 成本与撮合参数（**测试输入**；Q4/Q5 未答复前不落生产默认，缺值路径由用例真实缺失来测）
CFG_BROKER = {
    "commission": {"rate": 2.5e-4, "min": 5.0},
    "stamp_tax": {"side": "sell", "rate": 5e-4},
    "transfer_fee": {"rate": 1e-5, "included": False},
    "slippage_tiers": [{"amount_lower": 0.0, "amount_upper": 1_000_000.0, "bps": 10.0}],
    "liquidity_cap": [{"adv_tier": "default", "max_participation": 0.01}],
    "limit_pct": {"board": 0.1, "st": 0.05, "star": 0.2, "chinext": 0.2, "bj": 0.3},
    "seal_definition": "one_word_board",
    "suspend_source": "tushare",
}

#: 事件研究参数（R17/block bootstrap；值同样是测试输入）
CFG_EVENT = {"windows": [20, 60], "min_events": 30, "block_length": 5, "n_bootstrap": 1000}

#: 分组参数（R14/R15/R16）
CFG_LABELS = {"cut_basis": "cross_section_quantile", "tier_count": 3, "recompute_freq": "quarter",
              "min_group_size": 30}

#: 门禁判据（R19/Q7；`GateStateMachine(registry, *, cfg)` 从 `cfg.gate_criteria` 取）
CFG_GATES = {"gate_criteria": {
    "backtest_pass": {"metric": "excess_mean", "comparator": ">=", "threshold": 0.0,
                      "tail": "two-sided", "require_significance": True},
    "shadow": {"min_months": 6, "max_months": 12, "clock": "calendar"},
    "direction_agree": {"metric": "excess_mean", "tolerance": 0.0},
    "small_position": {"max_pct": 0.05},
}}

FIXED_NOW = "2026-01-02T09:30:00+08:00"


def _import(module: str):
    """按设计 §4.0 的模块路径导入被测对象（延迟导入，保证 --collect-only 可收集）。"""
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    return importlib.import_module(module)


def _merge(*parts: dict) -> dict:
    merged: dict = {}
    for part in parts:
        merged.update(json.loads(json.dumps(part)))
    return merged


@pytest.fixture
def load():
    """返回 `load("service.backtest.models")` 形式的延迟导入器。"""
    return _import


@pytest.fixture
def models(load):
    return load("service.backtest.models")


@pytest.fixture
def registry_module(load):
    return load("service.backtest.registry")


@pytest.fixture
def alpha():
    return ALPHA


@pytest.fixture
def clock():
    return lambda: FIXED_NOW


@pytest.fixture
def registry_path(tmp_path):
    return tmp_path / "registry.ndjson"


@pytest.fixture
def results_dir(tmp_path):
    return tmp_path / "results"


def _with_paths(raw: dict, results_dir: Path, registry_path: Path) -> dict:
    out = json.loads(json.dumps(raw))
    out["results_dir"] = str(results_dir)
    out["registry_store_path"] = str(registry_path)
    return out


@pytest.fixture
def cfg_raw(results_dir, registry_path):
    """CLI 夹具用的完整骨架（必须键 + 全部测试输入；不依赖仓库里的 `config/app.yaml`）。"""
    return _with_paths(_merge(CFG_REQUIRED, CFG_BROKER, CFG_EVENT, CFG_LABELS, CFG_GATES),
                       results_dir, registry_path)


@pytest.fixture
def cfg_from(load):
    """按 design §4.1 `BacktestConfig.from_config(raw)` 构造类型化配置（缺键即拒绝）。"""
    def _build(raw: dict):
        return load("service.backtest.config").BacktestConfig.from_config(raw)

    return _build


@pytest.fixture
def cfg(cfg_from, results_dir, registry_path):
    """**只含必须键**的配置：待 Q 键全部缺失，用于真实触发 `MissingBacktestConfigError`。"""
    return cfg_from(_with_paths(CFG_REQUIRED, results_dir, registry_path))


@pytest.fixture
def cfg_cost_raw(results_dir, registry_path):
    """成本手算用**输入值**（独立算式只读这份 raw，禁止调用被测成本函数反推）。"""
    return _with_paths(_merge(CFG_REQUIRED, CFG_BROKER), results_dir, registry_path)


@pytest.fixture
def cfg_cost(cfg_from, cfg_cost_raw):
    return cfg_from(cfg_cost_raw)


@pytest.fixture
def cfg_event(cfg_from, results_dir, registry_path):
    return cfg_from(_with_paths(_merge(CFG_REQUIRED, CFG_EVENT), results_dir, registry_path))


@pytest.fixture
def cfg_labels(cfg_from, results_dir, registry_path):
    return cfg_from(_with_paths(_merge(CFG_REQUIRED, CFG_LABELS), results_dir, registry_path))


@pytest.fixture
def cfg_gates(cfg_from, results_dir, registry_path):
    return cfg_from(_with_paths(_merge(CFG_REQUIRED, CFG_GATES), results_dir, registry_path))


@pytest.fixture
def cfg_gates_no_criteria(cfg):
    """判据缺失的配置（`gate_criteria` 天然缺失）——「缺判据 → 禁止 transition」负向分支。"""
    return cfg


@pytest.fixture
def cfg_calibration(cfg_from, results_dir, registry_path):
    """校准题配置：必须键 + 成本四分量（Q4 缺即拒绝）+ block_length/n_bootstrap（KQ-2，T2-fix-5 口径）。"""
    return cfg_from(_with_paths(_merge(CFG_REQUIRED, CFG_BROKER, CFG_EVENT), results_dir, registry_path))


def _business_days(start: str, end: str) -> list[str]:
    import datetime as dt

    day = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    out: list[str] = []
    while day <= stop:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += dt.timedelta(days=1)
    return out


class _CalibrationAdapter:
    """校准 loader 假件：`load_universe_codes` + `load_price_rows`（data.py 的两条注入通道）。"""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def load_universe_codes(self, as_of: str):
        return ("000001",)

    def load_price_rows(self, codes, start, end, mode):
        window = [row for row in self._rows if start <= row["trade_date"] <= end]
        return {code: list(window) for code in codes}


@pytest.fixture
def calibration_adapter():
    """校准题夹具数据：`whipsaw` = 上升趋势 + 周期性急跌（MA60 跌破后 60 日仍上涨 → 卖出跑输）；
    `no_signal` = 单调上涨（不触发 MA60 跌破 → 无事件、校准不可判定）。"""

    def _build(profile: str = "whipsaw"):
        import math

        days = _business_days("2015-01-05", "2026-12-31")
        close = 10.0
        rows: list[dict] = []
        phase, cycle = 0, 0
        for day in days:
            if profile == "whipsaw":
                # 上升趋势 + 每 60 个交易日 5 日急跌（触发 MA60 跌破）；
                # 每轮幅度做确定性微扰，使「跌破后 60 日仍上涨」在事件间有差异
                # （否则 excess 恒定 → CI 退化、t 值无定义）。实测：约 49 个事件、
                # mean_excess ≈ -0.013、CI = (-0.018, -0.009)（上界 < 0）、p ≈ 1.5e-9。
                dip = 0.03 + 0.003 * math.sin(cycle * 1.3)
                up = 0.003 + 0.0003 * math.sin(cycle * 0.7)
                close *= (1.0 - dip) if phase >= 55 else (1.0 + up)
                phase += 1
                if phase >= 60:
                    cycle, phase = cycle + 1, 0
            else:
                close *= 1.0005
            rows.append({
                "trade_date": day,
                "open": round(close * 1.0005, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "amount": 1e8,
                "avg_amount": 1e8,
                "limit_up_price": round(close * 1.1, 2),
                "limit_down_price": round(close * 0.9, 2),
                "suspended": False,
                "delisted": False,
                "st": False,
            })
        return _CalibrationAdapter(rows)

    return _build


@pytest.fixture
def calibration_loader(calibration_adapter):
    return calibration_adapter("whipsaw")


@pytest.fixture
def calibration_loader_no_signal(calibration_adapter):
    return calibration_adapter("no_signal")


@pytest.fixture
def registry(registry_module, registry_path, clock, results_dir):
    """设计 §4.1：`ExperimentRegistry(store_path, *, clock, data_version, results_dir)`，全部落 tmp_path。"""
    return registry_module.ExperimentRegistry(
        store_path=registry_path, clock=clock, data_version="test-v1", results_dir=results_dir)


@pytest.fixture
def make_bar(models):
    """按 design §4.1 `PriceBar`（T2-fix-4/5）构造：涨跌停价与日均成交额撮合必需，缺则实现报缺口。"""
    def _bar(trade_date: str, *, code: str = "000001", close: float = 10.0, open_: float | None = None,
             high: float | None = None, low: float | None = None, amount: float = 1_000_000.0,
             avg_amount: float | None = None, limit_up: float | None = None,
             limit_down: float | None = None, suspended: bool = False, delisted: bool = False,
             st: bool = False):
        px = close if open_ is None else open_
        return models.PriceBar(
            code=code, trade_date=trade_date, open=px, high=px if high is None else high,
            low=px if low is None else low, close=close, amount=amount,
            avg_amount=amount if avg_amount is None else avg_amount,
            limit_up_price=round(close * 1.1, 2) if limit_up is None else limit_up,
            limit_down_price=round(close * 0.9, 2) if limit_down is None else limit_down,
            suspended=suspended, delisted=delisted, st=st)

    return _bar


@pytest.fixture
def make_financial(models):
    def _fin(report_period: str = "20231231", *, code: str = "000001", ann_date: str | None = "2024-04-25",
             end_date: str | None = "2023-12-31", visible_from: str | None = None):
        return models.FinancialRecord(
            code=code, report_period=report_period, ann_date=ann_date, end_date=end_date,
            visible_from=visible_from or (ann_date or "2024-04-30"))

    return _fin


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def run_rows():
    """QA 侧台账读取器：按 `row_type` 判别符分出执行行（`RunRecord`，设计 §4.1）。"""
    def _rows(path: Path) -> list[dict]:
        return [row for row in _read_rows(Path(path)) if row.get("row_type", "result") == "run"]

    return _rows


@pytest.fixture
def result_rows():
    """QA 侧台账读取器：结果行（`ExperimentRecord`，设计 §4.1）。"""
    def _rows(path: Path) -> list[dict]:
        return [row for row in _read_rows(Path(path)) if row.get("row_type", "result") == "result"]

    return _rows


@pytest.fixture
def count_run_rows():
    def _count(path: Path, status: str) -> int:
        return sum(1 for row in _read_rows(Path(path))
                   if row.get("row_type", "result") == "run" and row.get("status") == status)

    return _count


@pytest.fixture
def ledger_rows(registry):
    """直接消费被测 `ExperimentRegistry.export_ledger`（设计 §4.1/§6.3）。"""
    def _export(**kwargs):
        return registry.export_ledger(**kwargs)

    return _export


@pytest.fixture
def cli_runner(load, monkeypatch, capsys, tmp_path, cfg_raw):
    """端到端 CLI 夹具（设计 §6.3）：入口 = 既有 `src/apps/cli.py` 的 `main(argv)->int`。

    配置解析顺序：`--config`（相对 cwd）> `cwd/config/app.yaml` > 缺键抛
    `MissingBacktestConfigError`（退出码 1）。夹具在 cwd 下自建最小骨架（JSON 即合法 YAML），
    **不依赖仓库 `config/app.yaml`**（gitignore；契约源是 `config/app.example.yaml` + design §4.1）。
    """
    def _run(argv, *, cwd: Path | None = None):
        root = Path(cwd) if cwd is not None else tmp_path
        cfg_dir = root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "app.yaml").write_text(json.dumps({"backtest": cfg_raw}), encoding="utf-8")
        monkeypatch.chdir(root)
        apps_cli = load("apps.cli")
        code = apps_cli.main(["backtest", *list(argv)])
        captured = capsys.readouterr()
        return SimpleNamespace(returncode=int(code or 0), stdout=captured.out, stderr=captured.err)

    return _run


@pytest.fixture
def gate_sm(load, registry, cfg_gates):
    """设计 §4.1（T2-fix-4）：`GateStateMachine(registry, *, cfg)`，判据来自 `cfg.gate_criteria`。"""
    return load("service.backtest.gates").GateStateMachine(registry, cfg=cfg_gates)


@pytest.fixture
def gate_sm_no_criteria(load, registry, cfg_gates_no_criteria):
    """判据缺失 → transition 必须抛 `MissingBacktestConfigError`（不允许降级放行）。"""
    return load("service.backtest.gates").GateStateMachine(registry, cfg=cfg_gates_no_criteria)


@pytest.fixture
def rule_id():
    return "rule-demo"


@pytest.fixture
def benchmarks(models):
    return [models.Benchmark(kind="buy_and_hold", label="买入持有"),
            models.Benchmark(kind="market_portfolio", label="全A等权")]


@pytest.fixture
def make_observations(models):
    """按 T2-fix-4 事件载体构造 `EventObservation`（双基准 × N 个事件 × 60 日逐日超额）。"""
    def _make(count: int = 40, *, benchmark_kinds=("buy_and_hold", "market_portfolio"),
              daily_excess: float = -0.002) -> tuple:
        observations = []
        for index in range(count):
            event_date = f"2020-{1 + index % 12:02d}-{1 + index % 27:02d}"
            for kind in benchmark_kinds:
                observations.append(models.EventObservation(
                    code="000001", event_date=event_date, condition_id="ma60_breakdown",
                    benchmark_kind=kind,
                    excess_returns=tuple(daily_excess for _ in range(60))))
        return tuple(observations)

    return _make


@pytest.fixture
def common_factor_series():
    """30 只 × 100 日同共因子序列（名义 3000 个观测，有效样本只能是时间块数）。"""
    import numpy as np

    rng = np.random.default_rng(7)
    factor = rng.normal(0.0, 0.01, size=100)
    return {f"code{i:02d}": factor + rng.normal(0, 0.002, size=100) for i in range(30)}


@pytest.fixture
def cfg_inference(cfg_event):
    """推断参数夹具（块长/重采样次数来自 `cfg`；`n_time_blocks` 是夹具构造参数）。"""
    return {"block_length": cfg_event.block_length, "n_bootstrap": cfg_event.n_bootstrap,
            "n_time_blocks": 100, "seed": 7}
