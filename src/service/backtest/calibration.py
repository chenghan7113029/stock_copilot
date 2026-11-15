"""R18 已知答案校准门禁（design §4.1，QA-F9 / QA-F11）。

失败表达二分（design「失败表达二分」）：
- **库层**：`assert_calibrated()` 直接 `raise CalibrationFailedError`（单测只断异常，不断
  `SystemExit`）；
- **CLI 层**：捕获后打印 stderr 并退出码 `2`。

校准题（spec R18）：以「跌破 MA60 卖出」跑全 A（扣成本、T+1、涨跌停顺延），结果必须显著
跑输买入持有。未复现 → 台子不可信（封锁全部研究输出），**不得**表述为某条策略无效。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from common.exceptions import BacktestDataGapError, BacktestError, CalibrationFailedError
from service.backtest.broker import CostCalculator
from service.backtest.data import load_price_series
from service.backtest.metrics import (
    block_bootstrap,
    multiple_testing_correction,
    p_value_from_t,
    t_statistic,
)
from service.backtest.models import (
    AdjustMode,
    BacktestConfig,
    CalibrationResult,
    ConditionSpec,
    OrderSide,
    PointInTimeSnapshot,
    RunRecord,
    RunStatus,
    Verdict,
)
from service.backtest.signal import (
    MA_FALLBACK_WINDOW,
    MA_WINDOW,
    SHORT_HISTORY_POLICIES,
    evaluate_condition,
)

CALIBRATION_FILE = "calibration.json"
CALIBRATION_SCOPE = "calibration"
UNTRUSTED_MESSAGE = "台子不可信，先修台子"


def write_calibration_result(
    result: CalibrationResult, results_dir: Path, *, run_id: str, at: str
) -> Path:
    """原子写 `<results_dir>/calibration.json`（无论成败都写，QA-F11）。"""
    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / CALIBRATION_FILE
    reason = None if result.passed else (result.notes[-1] if result.notes else UNTRUSTED_MESSAGE)
    payload: dict[str, Any] = {
        "passed": result.passed,
        "direction": result.direction,
        "ci": list(result.ci) if result.ci is not None else None,
        "K": result.K,
        "corrected_p": result.corrected_p,
        "verdict": result.verdict.value,
        "params": dict(result.params),
        "notes": list(result.notes),
        "run_id": run_id,
        "at": at,
        "reason": reason,
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)
    return destination


def run_calibration(*, cfg: BacktestConfig, loader: Any, registry: Any) -> CalibrationResult:
    """跑校准题；成败都写 `calibration.json` + 执行行，返回结果（失败不在此抛异常）。"""
    horizon = int(cfg.require("calibration.horizon_days"))
    k_value = int(cfg.require("calibration.k"))
    notional = float(cfg.require("calibration.notional"))
    start = str(cfg.require("calibration.start"))
    end = str(cfg.require("calibration.end"))
    policy = str(cfg.require("calibration.short_history_policy"))
    if policy not in SHORT_HISTORY_POLICIES:
        raise BacktestError(f"calibration.short_history_policy 非法: {policy!r}（KQ-1）")
    correction_method = str(cfg.require("correction_method"))
    alpha = float(cfg.require("alpha"))
    block_length = int(cfg.require("block_length"))
    n_bootstrap = int(cfg.require("n_bootstrap"))
    if horizon < 1:
        raise BacktestError(f"calibration.horizon_days 非法: {horizon}")

    codes = _calibration_codes(cfg, loader, end)
    prices = load_price_series(codes, start, end, AdjustMode.HFQ, loader=loader)
    condition = ConditionSpec(
        condition_id="ma60_breakdown",
        kind="ma_breakdown",
        params={
            "window": MA_WINDOW,
            "fallback_window": MA_FALLBACK_WINDOW,
            "short_history_policy": policy,
        },
    )
    calculator = CostCalculator.from_config(cfg)
    buy_cost, _ = calculator.cost(notional, OrderSide.BUY)
    sell_cost, _ = calculator.cost(notional, OrderSide.SELL)
    cost_rate = (buy_cost.total + sell_cost.total) / notional if notional else 0.0

    excess: list[float] = []
    for code in codes:
        bars = prices.get(code, ())
        for index in range(1, len(bars)):
            snapshot = PointInTimeSnapshot(as_of=bars[index].trade_date, price=tuple(bars[: index + 1]))
            signal = evaluate_condition(snapshot, condition)
            if signal is None:
                continue
            exit_index = index + horizon
            if exit_index >= len(bars):
                continue
            entry_price = bars[index].close
            exit_price = bars[exit_index].close
            if entry_price <= 0:
                continue
            hold_return = exit_price / entry_price - 1.0
            # 规则：事件后离场（空仓）→ 组合收益 0；相对买入持有的超额 = -hold - 成本
            excess.append(-hold_return - cost_rate)

    params = {
        "horizon_days": horizon,
        "K": k_value,
        "notional": notional,
        "correction_method": correction_method,
        "alpha": alpha,
        "short_history_policy": policy,
        "codes": len(codes),
        "events": len(excess),
    }
    if excess:
        ci, _effective_n = block_bootstrap(
            excess, block_length=block_length, n_bootstrap=n_bootstrap, seed=0
        )
        p_value = p_value_from_t(t_statistic(excess))
        corrected_p = multiple_testing_correction([p_value], k_value, correction_method, cfg=cfg)[0]
        mean_excess = sum(excess) / len(excess)
        passed = mean_excess < 0.0 and ci[1] < 0.0 and corrected_p < alpha
    else:
        ci = None
        corrected_p = None
        passed = False
    direction = "显著跑输" if passed else "未复现"
    notes: list[str] = []
    if passed:
        notes.append("台子可信：校准题复现显著跑输（R18 Scenario 1）")
    else:
        notes.append(f"{UNTRUSTED_MESSAGE}：校准题未复现显著跑输（R18 Scenario 2）")
    result = CalibrationResult(
        passed=passed,
        direction=direction,
        params=params,
        notes=tuple(notes),
        ci=ci,
        K=k_value,
        corrected_p=corrected_p,
        verdict=Verdict.INVALID if passed else Verdict.INCONCLUSIVE,
    )
    run_id = registry.next_experiment_id(CALIBRATION_SCOPE)
    at = registry.clock()
    write_calibration_result(result, registry.results_dir, run_id=run_id, at=at)
    registry.append_run(
        RunRecord(
            run_id=run_id,
            status=RunStatus.PASSED if passed else RunStatus.FAILED,
            at=at,
            hypothesis_id=CALIBRATION_SCOPE,
            reason=None if passed else notes[-1],
        )
    )
    return result


def _calibration_codes(cfg: BacktestConfig, loader: Any, as_of: str) -> tuple[str, ...]:
    explicit = cfg.get("calibration.codes")
    if explicit:
        return tuple(str(code) for code in explicit)
    method = getattr(loader, "load_universe_codes", None)
    if method is None:
        raise BacktestDataGapError(
            "校准题无法取样本：既无 calibration.codes，loader 也无 load_universe_codes（R18）"
        )
    return tuple(method(as_of))


def assert_calibrated(registry: Any) -> None:
    """库层门闩：最近一次校准未过/缺失 → `raise CalibrationFailedError`（QA-F9）。"""
    path = Path(registry.results_dir) / CALIBRATION_FILE
    if not path.exists():
        raise _failed("无校准记录：先跑 backtest calibrate（R18）", None, Verdict.INCONCLUSIVE)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is True:
        return
    verdict = Verdict(str(payload.get("verdict", Verdict.INCONCLUSIVE.value)))
    reason = str(payload.get("reason") or "校准未通过")
    corrected = payload.get("corrected_p")
    raise _failed(reason, None if corrected is None else float(corrected), verdict)


def _failed(reason: str, corrected_p: float | None, verdict: Verdict) -> CalibrationFailedError:
    exc = CalibrationFailedError(f"{UNTRUSTED_MESSAGE}：{reason}")
    exc.reason = reason  # type: ignore[attr-defined]
    exc.corrected_p = corrected_p  # type: ignore[attr-defined]
    exc.verdict = verdict  # type: ignore[attr-defined]
    return exc


def calibration_payload(result: CalibrationResult) -> Mapping[str, Any]:
    """供 CLI 打印的 JSON（与写盘字段一致，但不含 run_id/at）。"""
    return {
        "passed": result.passed,
        "direction": result.direction,
        "ci": None if result.ci is None else list(result.ci),
        "K": result.K,
        "corrected_p": result.corrected_p,
        "verdict": result.verdict.value,
        "params": dict(result.params),
        "notes": list(result.notes),
    }
