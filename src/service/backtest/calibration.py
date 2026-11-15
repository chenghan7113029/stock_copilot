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
from typing import Any

from common.exceptions import (
    BacktestDataGapError,
    BacktestError,
    CalibrationFailedError,
    MissingBacktestConfigError,
)
from service.backtest.broker import CostCalculator, execute_orders
from service.backtest.data import load_price_series
from service.backtest.metrics import (
    block_bootstrap,
    multiple_testing_correction,
    p_value_from_t,
    t_statistic,
)
from service.backtest.models import (
    LOT_SIZE,
    SEGMENT_YEAR_RANGES,
    AdjustMode,
    BacktestConfig,
    CalibrationResult,
    ConditionSpec,
    Order,
    OrderSide,
    PointInTimeSnapshot,
    RunRecord,
    RunStatus,
    Verdict,
)
from service.backtest.signal import MA_WINDOW, evaluate_condition

CALIBRATION_FILE = "calibration.json"
CALIBRATION_SCOPE = "calibration"
UNTRUSTED_MESSAGE = "台子不可信，先修台子"
# 校准题样本区间 = spec R3 的三段年份（A2：右边界取最后一段末年）
_MIN_TRAIN_YEAR = min(start for start, _end in SEGMENT_YEAR_RANGES.values())
_MAX_OOS_YEAR = max(end for _start, end in SEGMENT_YEAR_RANGES.values())
CALIBRATION_START = f"{_MIN_TRAIN_YEAR:04d}-01-01"
CALIBRATION_END = f"{_MAX_OOS_YEAR:04d}-12-31"
# 校准题是「一道题」：校正方法固定 Bonferroni + K=执行次数（K 翻倍不改变本意）
CALIBRATION_CORRECTION_METHOD = "bonferroni"
# 校准成本与撮合：走 broker 正式路径的四分量（R7/R8，T2-fix-5：禁止比例成本近似）


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
    if cfg.block_length is None:
        raise MissingBacktestConfigError("回测配置缺值: block_length（KQ-2）")
    if cfg.n_bootstrap is None:
        raise MissingBacktestConfigError("回测配置缺值: n_bootstrap（KQ-2）")
    horizon = max(cfg.windows)
    # Q4 成本键必须在扫描前可用：零事件也不得绕过「缺键即拒绝」
    CostCalculator.from_config(cfg)
    codes = _calibration_codes(loader, CALIBRATION_END)
    prices = load_price_series(
        codes, CALIBRATION_START, CALIBRATION_END, AdjustMode.HFQ, loader=loader
    )
    condition = ConditionSpec(
        condition_id="ma60_breakdown",
        kind="ma60_breakdown",
        params={"window": MA_WINDOW},
    )
    excess: list[float] = []
    for code in codes:
        bars = prices.get(code, ())
        bar_dates = [bar.trade_date for bar in bars]
        for index in range(1, len(bars)):
            snapshot = PointInTimeSnapshot(
                as_of=bars[index].trade_date, price=tuple(bars[: index + 1])
            )
            signal = evaluate_condition(snapshot, condition)
            if signal is None:
                continue
            # 撮合走正式路径（t+1 / 封板顺延 / 停牌跳过 / 流动性上限），成本取四分量
            order = Order(
                code=code,
                signal_date=signal.event_date,
                side=OrderSide.SELL,
                requested_amount=0.0,
                requested_qty=LOT_SIZE,
            )
            fill = execute_orders([order], {code: bars}, cfg=cfg)[0]
            if fill.fill_date is None or not fill.filled_amount or fill.filled_amount <= 0:
                continue
            fill_index = bar_dates.index(fill.fill_date)
            exit_index = fill_index + horizon
            if exit_index >= len(bars):
                continue
            hold_return = bars[exit_index].close / bars[fill_index].close - 1.0
            cost_rate = fill.cost.total / fill.filled_amount
            # 规则：事件后离场（空仓）→ 组合收益 0；相对买入持有的超额 = -成本 - hold
            excess.append(-cost_rate - hold_return)

    k_value = _next_calibration_k(registry)
    params = {
        "horizon_days": horizon,
        "K": k_value,
        "correction_method": CALIBRATION_CORRECTION_METHOD,
        "short_history_policy": "ma20_substitute",
        "codes": len(codes),
        "events": len(excess),
        "calibration_window": [CALIBRATION_START, CALIBRATION_END],
        "cost_model": "broker_four_components",
        "match_engine": "execute_orders",
    }
    if excess:
        ci, _effective_n = block_bootstrap(
            excess,
            block_length=int(cfg.block_length),
            n_bootstrap=int(cfg.n_bootstrap),
            seed=0,
        )
        p_value = p_value_from_t(t_statistic(excess))
        corrected_p = multiple_testing_correction(
            [p_value], k_value, CALIBRATION_CORRECTION_METHOD, cfg=cfg
        )[0]
        mean_excess = sum(excess) / len(excess)
        # KQ-5（「显著」判据）未答复：本波只用「方向为负 + 置信区间不含 0」这一确定判据
        passed = mean_excess < 0.0 and ci[1] < 0.0
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
    notes.append("KQ-1 未答复：次新股沿用现行 MA60/MA20 替代口径并标注")
    notes.append(
        "成本 = broker 四分量（佣金/印花税/滑点/过户费，R7）；撮合走 execute_orders"
        "（T+1/封板顺延/停牌跳过/流动性上限，R8）——不使用比例成本近似"
    )
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
            reason=None if passed else notes[0],
        )
    )
    return result


def _calibration_codes(loader: Any, as_of: str) -> tuple[str, ...]:
    method = getattr(loader, "load_universe_codes", None)
    if method is None:
        raise BacktestError(
            "校准题无法取样本：loader 缺 load_universe_codes（R18 要求跑全 A，不静默降级）"
        )
    codes = tuple(str(code) for code in method(as_of))
    if not codes:
        # 全 A 名单为空 = 数据不可得（不是「无信号」）
        raise BacktestDataGapError("校准题样本为空：全 A 名单不可得（R18/T3-repair）")
    return codes


def _next_calibration_k(registry: Any) -> int:
    """K = 本次校准的累计执行次数（执行行可数，避免「结论不对就重跑」不留痕）。"""
    executions = [
        row
        for row in registry.rows()
        if isinstance(row, RunRecord)
        and row.hypothesis_id == CALIBRATION_SCOPE
        and row.status in (RunStatus.PASSED, RunStatus.FAILED)
    ]
    return len(executions) + 1


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


def calibration_payload(result: CalibrationResult) -> dict[str, Any]:
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
