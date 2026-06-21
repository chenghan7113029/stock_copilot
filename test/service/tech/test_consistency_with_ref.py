"""技术面一致性校验：本层 vs ref/daily_stock_analysis StockTrendAnalyzer（0.1% 容差）。

设计约束：
- 仅对比 ref 共有的指标因子（MA / 乖离率 / MACD / RSI / 量能 / 趋势 / 支撑）
- KDJ 为 stock_copilot 扩展项，ref 无对应实现，不纳入比对
- 综合评分使用 LegacyRefScorer（RSI 动量 10 分，无 KDJ）与 ref 对齐
- 相对误差 ≤ 0.1%；整数评分与枚举状态要求完全一致
- 生产代码不 import ref/，仅在测试内通过 importlib 加载参考实现
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import pytest

from service.tech.calculator import IndicatorCalculator
from service.tech.scorer import LegacyRefScorer

TOLERANCE = 0.001  # 0.1%

NUMERIC_FIELDS = [
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "current_price",
    "bias_ma5",
    "bias_ma10",
    "bias_ma20",
    "volume_ratio_5d",
    "macd_dif",
    "macd_dea",
    "macd_bar",
    "rsi_6",
    "rsi_12",
    "rsi_24",
    "trend_strength",
]

ENUM_FIELDS = [
    "trend_status",
    "volume_status",
    "macd_status",
    "rsi_status",
    "buy_signal",
]

BOOLEAN_FIELDS = [
    "support_ma5",
    "support_ma10",
]

FIXTURES = [
    ("uptrend_random", 42, 60),
    ("uptrend_linear", 7, 60),
    ("volatile", 123, 60),
    ("short_history", 99, 30),
]


def _get_ref_stock_analyzer_path() -> Optional[Path]:
    workspace = Path(__file__).parent.parent.parent.parent
    ref_path = workspace / "ref" / "daily_stock_analysis" / "src" / "stock_analyzer.py"
    return ref_path if ref_path.exists() else None


def _load_ref_stock_analyzer():
    """通过 importlib 加载 ref StockTrendAnalyzer，避免 import ref 包副作用。"""
    ref_path = _get_ref_stock_analyzer_path()
    if ref_path is None:
        pytest.skip("ref/daily_stock_analysis 不存在，跳过一致性检查")

    cfg_mod = types.ModuleType("src.config")

    class _Cfg:
        bias_threshold = 5.0

    cfg_mod.get_config = lambda: _Cfg()
    sys.modules.setdefault("src", types.ModuleType("src"))
    sys.modules["src.config"] = cfg_mod

    spec = importlib.util.spec_from_file_location("ref_stock_analyzer", ref_path)
    if spec is None or spec.loader is None:
        pytest.skip("无法加载 ref stock_analyzer")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.StockTrendAnalyzer


def _make_ohlcv(seed: int, n: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    base = 10.0
    closes = [base]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1 + rng.normal(0.003, 0.012)))
    prices = np.array(closes)
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices * (1 + rng.normal(0, 0.002, n)),
            "high": prices * (1 + rng.uniform(0.005, 0.025, n)),
            "low": prices * (1 - rng.uniform(0.005, 0.025, n)),
            "close": prices,
            "volume": rng.integers(800_000, 6_000_000, size=n).astype(float),
        }
    )


def _relative_error(our_val: float, ref_val: float) -> Optional[float]:
    if ref_val == 0:
        return 0.0 if our_val == 0 else None
    return abs(our_val - ref_val) / abs(ref_val)


def _enum_value(obj: Any, field: str) -> str:
    val = getattr(obj, field)
    return val.value if hasattr(val, "value") else str(val)


@pytest.fixture(scope="module")
def ref_analyzer():
    return _load_ref_stock_analyzer()


@pytest.fixture(scope="module")
def reports_dir() -> Path:
    path = Path(__file__).parent.parent.parent.parent / "reports"
    path.mkdir(exist_ok=True)
    return path


@pytest.mark.parametrize("name,seed,n_bars", FIXTURES)
def test_consistency_with_ref(
    name: str,
    seed: int,
    n_bars: int,
    ref_analyzer,
    reports_dir: Path,
):
    """对比本层指标计算与 ref StockTrendAnalyzer，相对误差 ≤ 0.1%。"""
    df = _make_ohlcv(seed, n_bars)
    code = "600519"

    ref = ref_analyzer().analyze(df.copy(), code)
    ours = IndicatorCalculator().calculate(df.copy(), code)
    legacy_score = LegacyRefScorer().score(ours)

    diffs: list[dict] = []
    failures: list[str] = []

    for field in NUMERIC_FIELDS:
        ref_val = float(getattr(ref, field))
        our_val = float(getattr(ours, field))
        rel_err = _relative_error(our_val, ref_val)
        if rel_err is None:
            failures.append(f"{field}: ref=0, ours={our_val}")
            diffs.append({"field": field, "status": "ref_zero"})
            continue
        status = "PASS" if rel_err <= TOLERANCE else "FAIL"
        diffs.append(
            {
                "field": field,
                "ref": ref_val,
                "ours": our_val,
                "rel_error": rel_err,
                "status": status,
            }
        )
        if status == "FAIL":
            failures.append(
                f"{field}: ours={our_val:.6f}, ref={ref_val:.6f}, rel_err={rel_err:.4%}"
            )

    for field in ENUM_FIELDS:
        if field == "buy_signal":
            ref_val = ref.buy_signal.value
            our_val = legacy_score.buy_signal.value
        else:
            ref_val = _enum_value(ref, field)
            our_val = _enum_value(ours, field)
        status = "PASS" if ref_val == our_val else "FAIL"
        diffs.append({"field": field, "ref": ref_val, "ours": our_val, "status": status})
        if status == "FAIL":
            failures.append(f"{field}: ours={our_val!r}, ref={ref_val!r}")

    for field in BOOLEAN_FIELDS:
        ref_val = bool(getattr(ref, field))
        our_val = bool(getattr(ours, field))
        status = "PASS" if ref_val == our_val else "FAIL"
        diffs.append({"field": field, "ref": ref_val, "ours": our_val, "status": status})
        if status == "FAIL":
            failures.append(f"{field}: ours={our_val}, ref={ref_val}")

    ref_score = int(ref.signal_score)
    our_score = int(legacy_score.signal_score)
    score_status = "PASS" if ref_score == our_score else "FAIL"
    diffs.append(
        {
            "field": "signal_score",
            "ref": ref_score,
            "ours": our_score,
            "status": score_status,
        }
    )
    if score_status == "FAIL":
        failures.append(f"signal_score: ours={our_score}, ref={ref_score}")

    report = {
        "fixture": name,
        "seed": seed,
        "n_bars": n_bars,
        "run_at": datetime.now().isoformat(),
        "tolerance": TOLERANCE,
        "diffs": diffs,
        "failures": failures,
        "notes": "KDJ 为扩展项，LegacyRefScorer 用于 signal_score 对齐 ref",
    }
    report_path = reports_dir / f"tech_consistency_{name}_{datetime.now().strftime('%Y%m%d')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        pytest.fail(
            f"{name} 一致性校验失败（{len(failures)} 项）:\n" + "\n".join(failures)
        )
