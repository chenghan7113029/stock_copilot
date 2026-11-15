"""T2.17 已知答案校准门禁（R18 + QA-F9 二分 + QA-F11 写盘点 + T2-fix-4 契约）。"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from common.exceptions import CalibrationFailedError
from service.backtest.calibration import (
    CALIBRATION_END,
    CALIBRATION_FILE,
    CALIBRATION_START,
    assert_calibrated,
    run_calibration,
)
from service.backtest.models import RunStatus, Verdict


def weekday_dates(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def rows_for(code: str, closes: list[float]) -> tuple[dict, ...]:
    dates = weekday_dates(CALIBRATION_START, len(closes))
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


class CalibrationLoader:
    def __init__(self, closes: list[float], codes: int = 5):
        self.closes = closes
        self.codes = tuple(f"{index:06d}" for index in range(1, codes + 1))
        self.universe_calls: list[str] = []

    def load_universe_codes(self, as_of):
        self.universe_calls.append(as_of)
        return self.codes

    def load_price_rows(self, codes, start, end, adjust):
        return {code: rows_for(code, self.closes) for code in codes}


# 61 根打底（MA60 + 事件日）+ 60 天事件后
BREAKDOWN_THEN_RALLY = [10.0] * 60 + [9.0] + [9.0 + 0.05 * step for step in range(1, 61)]
BREAKDOWN_THEN_DROP = [10.0] * 60 + [9.0] + [9.0 - 0.03 * step for step in range(1, 61)]


def test_calibration_fixture_window_is_spec_range():
    assert CALIBRATION_START == "2015-01-01"
    assert CALIBRATION_END == "2026-12-31"


def test_calibration_pass_marks_platform_trusted(cfg, registry):
    loader = CalibrationLoader(BREAKDOWN_THEN_RALLY)
    result = run_calibration(cfg=cfg, loader=loader, registry=registry)
    assert result.passed is True
    assert result.verdict is Verdict.INVALID  # 结论：规则无效（跑输持有），台子可信
    assert result.direction == "显著跑输"
    assert result.K == 1
    assert result.corrected_p is not None
    assert result.ci is not None and result.ci[1] < 0
    assert loader.universe_calls
    payload = json.loads((registry.results_dir / CALIBRATION_FILE).read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["run_id"]
    assert payload["params"]["horizon_days"] == 60  # = max(cfg.windows)
    assert payload["params"]["short_history_policy"] == "ma20_substitute"
    statuses = [
        row.status for row in registry.rows() if getattr(row, "row_type", "") == "run"
    ]
    assert statuses == [RunStatus.PASSED]
    assert_calibrated(registry)  # 不抛异常


def test_calibration_failure_blocks_output(cfg, registry):
    loader = CalibrationLoader(BREAKDOWN_THEN_DROP)
    result = run_calibration(cfg=cfg, loader=loader, registry=registry)
    assert result.passed is False
    assert result.verdict is not Verdict.VALID
    assert result.direction == "未复现"
    payload = json.loads((registry.results_dir / CALIBRATION_FILE).read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload["reason"]
    statuses = [
        row.status for row in registry.rows() if getattr(row, "row_type", "") == "run"
    ]
    assert statuses == [RunStatus.FAILED]
    with pytest.raises(CalibrationFailedError) as exc:
        assert_calibrated(registry)
    assert exc.value.reason  # type: ignore[attr-defined]
    assert exc.value.verdict is Verdict.INCONCLUSIVE  # type: ignore[attr-defined]


def test_calibration_k_accumulates_per_execution(cfg, registry):
    loader = CalibrationLoader(BREAKDOWN_THEN_RALLY)
    first = run_calibration(cfg=cfg, loader=loader, registry=registry)
    second = run_calibration(cfg=cfg, loader=loader, registry=registry)
    assert (first.K, second.K) == (1, 2)


def test_assert_calibrated_without_record_raises(registry):
    with pytest.raises(CalibrationFailedError):
        assert_calibrated(registry)


def test_failure_wording_never_blames_strategy(cfg, registry):
    result = run_calibration(
        cfg=cfg, loader=CalibrationLoader(BREAKDOWN_THEN_DROP, codes=2), registry=registry
    )
    text = " ".join([result.direction, *result.notes, json.dumps(dict(result.params), ensure_ascii=False)])
    for forbidden in ("MA60 无效", "止损无效", "该规则无效"):
        assert forbidden not in text
    assert "台子不可信" in text
    assert "KQ-1" in text  # 口径未定的显式标注
