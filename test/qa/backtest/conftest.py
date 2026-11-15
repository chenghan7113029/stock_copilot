"""test/qa/backtest — QA 盲测夹具（T4-exec）。

盲测声明（只读清单）
--------------------
本套件的断言只来自：
1. `openspec/changes/add-backtest-engine/specs/backtest-engine/spec.md`（19 Requirement / 56 Scenario）
2. `openspec/changes/add-backtest-engine/proposal.md`（成功标准 S1–S5 / 失败标准 F1–F8）
3. `openspec/changes/add-backtest-engine/design.md` 冻结版（822 行）的 §4.1 契约：dataclass / 函数签名 /
   异常清单 / 「失败表达二分」/ §6.3 CLI 入口与退出码 / §4.1 台账存储机制
4. `openspec/changes/add-backtest-engine/test-design.md`（§1 TC 表 / §2.3 退出码 / §10 夹具）
5. `test/qa/README.md`（目录约定：按被测模块镜像 `test/qa/<module>/`）

**未读**：`src/service/backtest/`、`src/data_provider/backtest/`、`test/service/backtest/`（engineer 并行实现）。
因此本套件允许先红：被测模块不存在时，用例以 ImportError / 明确失败暴露「实现未就绪」，而不是静默 skip。
一条 TC = 一个测试函数（共 56 条，按 `test-design.md` §1.2 的 TC ID 落位）。
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

#: 测试输入配置（**非生产默认值**；Q4–Q8 由 Owner 定值前，测试只声明自己的输入）
CFG_RAW = {
    "commission": {"rate": 2.5e-4, "min": 5.0},
    "stamp_tax": {"sell_rate": 5e-4},
    "transfer_fee": {"rate": 1e-5},
    "slippage_tiers": [{"max_amount": 1_000_000.0, "rate": 1e-3}],
    "liquidity_cap": {"max_pct_of_avg_amount": 0.01},
    "alpha": 0.05,
    "k_definition": "rule+param+cut+window",
    "correction_method": "bonferroni",
    "segments": {"train": ["2015-01-01", "2020-12-31"], "validation": ["2021-01-01", "2023-12-31"],
                 "out_of_sample": ["2024-01-01", "2026-11-30"]},
}

FIXED_NOW = "2026-01-02T09:30:00+08:00"


def _import(module: str):
    """按设计 §4.0 的模块路径导入被测对象（延迟导入，保证 --collect-only 可收集）。"""
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    return importlib.import_module(module)


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
def clock():
    return lambda: FIXED_NOW


@pytest.fixture
def registry_path(tmp_path):
    return tmp_path / "registry.ndjson"


@pytest.fixture
def results_dir(tmp_path):
    return tmp_path / "results"


@pytest.fixture
def cfg_raw(results_dir, registry_path):
    raw = json.loads(json.dumps(CFG_RAW))
    raw["results_dir"] = str(results_dir)
    raw["registry_store_path"] = str(registry_path)
    return raw


@pytest.fixture
def cfg(load, cfg_raw):
    return load("service.backtest.config").BacktestConfig.from_config(cfg_raw)


@pytest.fixture
def registry(registry_module, registry_path, clock, results_dir):
    """设计 §4.1：`ExperimentRegistry(store_path, *, clock, data_version, results_dir)`，全部落 tmp_path。"""
    return registry_module.ExperimentRegistry(
        store_path=registry_path, clock=clock, data_version="test-v1", results_dir=results_dir)


@pytest.fixture
def make_bar(models):
    def _bar(trade_date: str, *, code: str = "000001", close: float = 10.0, open_: float | None = None,
             high: float | None = None, low: float | None = None, amount: float | None = 1_000_000.0,
             limit_up: float | None = None, limit_down: float | None = None,
             suspended: bool = False, delisted: bool = False, st: bool = False):
        px = close if open_ is None else open_
        return models.PriceBar(
            code=code, trade_date=trade_date, open=px, high=px if high is None else high,
            low=px if low is None else low, close=close, amount=amount, limit_up_price=limit_up,
            limit_down_price=limit_down, suspended=suspended, delisted=delisted, st=st)

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
    `MissingBacktestConfigError`（退出码 1）。夹具在 cwd 下写最小合法骨架（JSON 即合法 YAML）。
    """
    def _run(argv, *, cwd: Path | None = None):
        root = Path(cwd) if cwd is not None else tmp_path
        cfg_dir = root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "app.yaml").write_text(json.dumps(cfg_raw), encoding="utf-8")
        monkeypatch.chdir(root)
        apps_cli = load("apps.cli")
        code = apps_cli.main(["backtest", *list(argv)])
        captured = capsys.readouterr()
        return SimpleNamespace(returncode=int(code or 0), stdout=captured.out, stderr=captured.err)

    return _run


@pytest.fixture
def gate_sm(load, registry):
    return load("service.backtest.gates").GateStateMachine(registry)


@pytest.fixture
def rule_id():
    return "rule-demo"


@pytest.fixture
def benchmarks(models):
    return [models.Benchmark(kind="buy_and_hold", label="买入持有"),
            models.Benchmark(kind="market_portfolio", label="全A等权")]


@pytest.fixture
def common_factor_series():
    """30 只 × 100 日同共因子序列（名义 3000 个观测，有效样本只能是时间块数）。"""
    import numpy as np

    rng = np.random.default_rng(7)
    factor = rng.normal(0.0, 0.01, size=100)
    return {f"code{i:02d}": np.repeat(factor[None, :], 1, axis=0) + rng.normal(0, 0.002, size=100)
            for i in range(30)}


@pytest.fixture
def cfg_inference(cfg_raw):
    raw = json.loads(json.dumps(cfg_raw))
    raw.update({"n_time_blocks": 100, "block_length": 5, "n_bootstrap": 1000, "seed": 7})
    return raw


@pytest.fixture
def cfg_labels(cfg_raw):
    raw = json.loads(json.dumps(cfg_raw))
    raw.update({"tier_count": 3, "cut_basis": "cross_section_quantile", "recompute_freq": "quarter",
                "min_group_size": 30})
    return raw


@pytest.fixture
def cfg_gates(cfg_raw):
    raw = json.loads(json.dumps(cfg_raw))
    raw.update({"shadow": {"min_months": 6, "max_months": 12}, "live_small": {"max_position_pct": 0.05}})
    return raw
