"""T2.1 契约 dataclass / 枚举 / 异常族（design §4.1）。"""

from __future__ import annotations

import pytest

from common.exceptions import (
    BacktestDataGapError,
    BacktestError,
    CalibrationFailedError,
    FutureDataError,
    GateSkipError,
    InvalidAdjustModeError,
    MissingBacktestConfigError,
    RegistryCorruptedError,
    RegistryImmutableError,
)
from service.backtest.models import (
    AdjustMode,
    ConditionSpec,
    CostBreakdown,
    ExperimentRecord,
    Fill,
    FinancialRecord,
    Order,
    OrderAttempt,
    OrderSide,
    OrderStatus,
    PointInTimeSnapshot,
    RunRecord,
    RunStatus,
    Segment,
    Verdict,
    segment_of,
)


def test_snapshot_rejects_future_price_bar(make_bar):
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(as_of="2020-01-06", price=(make_bar(trade_date="2020-01-07"),))


def test_snapshot_rejects_future_financial():
    record = FinancialRecord(
        code="000001",
        report_period="20191231",
        ann_date="2020-02-28",
        end_date="2019-12-31",
        visible_from="2020-02-28",
    )
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(as_of="2020-01-06", financials=(record,))


def test_snapshot_accepts_past_rows(make_bar):
    snapshot = PointInTimeSnapshot(as_of="2020-01-06", price=(make_bar(trade_date="2020-01-06"),))
    assert snapshot.as_of == "2020-01-06"


def test_fill_attempts_express_seal_then_fill(make_bar):
    order = Order(code="000001", signal_date="2020-01-03", side=OrderSide.BUY, requested_amount=100_000)
    fill = Fill(
        order=order,
        attempts=(
            OrderAttempt("2020-01-06", OrderStatus.FAILED_LIMIT_SEAL, "一字涨停封板"),
            OrderAttempt("2020-01-07", OrderStatus.FILLED, None),
        ),
        cost=CostBreakdown(),
        fill_date="2020-01-07",
        fill_price=11.0,
        filled_amount=100_000.0,
        delay_days=1,
        notes=("连续封板 1 日",),
    )
    assert fill.attempts[0].status is OrderStatus.FAILED_LIMIT_SEAL
    assert fill.attempts[-1].status is OrderStatus.FILLED
    assert fill.delay_days == 1


def test_experiment_record_allows_missing_k():
    record = ExperimentRecord(
        experiment_id="hid-0001",
        hypothesis_id="hid",
        params={"ma": 60},
        segment=Segment.VALIDATION,
        K=None,
        verdict=Verdict.INCONCLUSIVE,
        metrics={},
        prereg_commit="abc123",
        data_version="v1",
        adjust_mode=AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-01T00:00:00"},
    )
    assert record.K is None
    assert record.verdict is Verdict.INCONCLUSIVE
    assert record.row_type == "result"


def test_run_record_has_data_version_field():
    record = RunRecord(
        run_id="hid-0001",
        status=RunStatus.FAILED,
        at="2026-01-01T00:00:00",
        hypothesis_id="hid",
        data_version="v1",
    )
    assert record.data_version == "v1"
    assert record.row_type == "run"


def test_exception_family_is_binary():
    assert issubclass(InvalidAdjustModeError, BacktestError)
    assert issubclass(BacktestDataGapError, BacktestError)
    assert not issubclass(InvalidAdjustModeError, BacktestDataGapError)
    for exception in (
        MissingBacktestConfigError,
        FutureDataError,
        RegistryCorruptedError,
        RegistryImmutableError,
        CalibrationFailedError,
        GateSkipError,
    ):
        assert issubclass(exception, BacktestError)


def test_adjust_mode_has_no_qfq():
    assert [mode.value for mode in AdjustMode] == ["hfq", "segmented_hfq"]


def test_segment_of_three_ranges():
    assert segment_of("2016-01-04") is Segment.TRAIN
    assert segment_of("2022-06-01") is Segment.VALIDATION
    assert segment_of("2025-01-02") is Segment.OUT_OF_SAMPLE
    with pytest.raises(BacktestError):
        segment_of("2010-01-04")


def test_condition_spec_is_frozen_and_serializable():
    spec = ConditionSpec(condition_id="ma60", kind="ma_breakdown", params={"window": 60})
    assert spec.params["window"] == 60
    with pytest.raises(Exception):
        spec.kind = "other"  # type: ignore[misc]
