"""T2.17 已知答案校准门禁（R18 + QA-F9 失败表达二分 + QA-F11 写盘点）。"""

from __future__ import annotations

import json

import pytest

from common.exceptions import CalibrationFailedError
from service.backtest.calibration import (
    CALIBRATION_FILE,
    assert_calibrated,
    run_calibration,
)
from service.backtest.models import BacktestConfig, RunStatus, Verdict


def weekday_dates(start: str, count: int) -> list[str]:
    from datetime import date, timedelta

    current = date.fromisoformat(start)
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def make_rows(code: str, closes: list[float]) -> tuple[dict, ...]:
    dates = weekday_dates("2020-01-01", len(closes))
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
        self.codes = [f"{index:06d}" for index in range(1, codes + 1)]

    def load_price_rows(self, codes, start, end, adjust):
        return {code: make_rows(code, self.closes) for code in codes}

    def load_universe_codes(self, as_of):
        return tuple(self.codes)


BREAKDOWN_THEN_RALLY = [10.0] * 60 + [9.0, 11.0, 12.0]
BREAKDOWN_THEN_DROP = [10.0] * 60 + [9.0, 8.0, 7.0]


def calibration_cfg(tmp_path, config_factory, codes):
    return BacktestConfig.from_config(
        config_factory(**{"calibration.codes": codes}), base_dir=tmp_path
    )


def test_calibration_pass_marks_platform_trusted(tmp_path, config_factory, registry):
    codes = ["000001", "000002", "000003", "000004", "000005"]
    cfg = calibration_cfg(tmp_path, config_factory, codes)
    result = run_calibration(cfg=cfg, loader=CalibrationLoader(BREAKDOWN_THEN_RALLY), registry=registry)
    assert result.passed is True
    assert result.verdict is Verdict.INVALID  # 结论：规则无效（跑输持有），台子可信
    assert result.direction == "显著跑输"
    assert result.K == 1
    assert result.corrected_p is not None and result.corrected_p < 0.05
    assert result.ci is not None and result.ci[1] < 0
    payload = json.loads((registry.results_dir / CALIBRATION_FILE).read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["run_id"]
    assert [row.status for row in registry.rows() if getattr(row, "row_type", "") == "run"] == [
        RunStatus.PASSED
    ]
    assert_calibrated(registry)  # 不抛异常


def test_calibration_failure_blocks_output(tmp_path, config_factory, registry):
    codes = ["000001", "000002", "000003", "000004", "000005"]
    cfg = calibration_cfg(tmp_path, config_factory, codes)
    result = run_calibration(cfg=cfg, loader=CalibrationLoader(BREAKDOWN_THEN_DROP), registry=registry)
    assert result.passed is False
    assert result.verdict is not Verdict.VALID
    assert result.direction == "未复现"
    payload = json.loads((registry.results_dir / CALIBRATION_FILE).read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload["reason"]
    assert [row.status for row in registry.rows() if getattr(row, "row_type", "") == "run"] == [
        RunStatus.FAILED
    ]
    with pytest.raises(CalibrationFailedError) as exc:
        assert_calibrated(registry)
    assert exc.value.reason  # type: ignore[attr-defined]
    assert exc.value.verdict is Verdict.INCONCLUSIVE  # type: ignore[attr-defined]
    assert exc.value.corrected_p is not None  # type: ignore[attr-defined]


def test_assert_calibrated_without_record_raises(tmp_path, registry):
    with pytest.raises(CalibrationFailedError):
        assert_calibrated(registry)


def test_failure_wording_never_blames_strategy(tmp_path, config_factory, registry):
    cfg = calibration_cfg(tmp_path, config_factory, ["000001", "000002"])
    result = run_calibration(cfg=cfg, loader=CalibrationLoader(BREAKDOWN_THEN_DROP), registry=registry)
    text = " ".join(
        [
            result.direction,
            *result.notes,
            json.dumps(dict(result.params), ensure_ascii=False),
        ]
    )
    for forbidden in ("MA60 无效", "止损无效", "该规则无效"):
        assert forbidden not in text
    assert "台子不可信" in text
