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
    EventObservation,
    ExperimentRecord,
    Fill,
    FinancialRecord,
    Order,
    OrderAttempt,
    OrderSide,
    OrderStatus,
    PointInTimeSnapshot,
    PriceBar,
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


def test_event_observation_contract_fields():
    """T2-fix-4：事件收益载体字段固定（code/event_date/condition_id/benchmark_kind/excess_returns）。"""
    fields = set(EventObservation.__dataclass_fields__)
    assert fields == {
        "code",
        "event_date",
        "condition_id",
        "benchmark_kind",
        "excess_returns",
    }
    item = EventObservation(
        code="000001",
        event_date="2020-01-06",
        condition_id="ma60_breakdown",
        benchmark_kind="buy_and_hold",
        excess_returns=(-0.01, 0.02),
    )
    assert item.excess_returns == (-0.01, 0.02)


def test_condition_spec_contract_fields():
    fields = set(ConditionSpec.__dataclass_fields__)
    assert fields == {"condition_id", "kind", "params"}


def test_config_spec_dataclasses_exist():
    from service.backtest.models import (
        BacktestConfig,
        CommissionSpec,
        GateCriteria,
        LiquidityCapSpec,
        SlippageTierSpec,
        StampTaxSpec,
        TransferFeeSpec,
    )

    assert set(CommissionSpec.__dataclass_fields__) == {"rate", "min"}
    assert set(StampTaxSpec.__dataclass_fields__) == {"side", "rate"}
    assert set(TransferFeeSpec.__dataclass_fields__) == {"rate", "included"}
    assert set(SlippageTierSpec.__dataclass_fields__) == {"amount_lower", "amount_upper", "bps"}
    assert set(LiquidityCapSpec.__dataclass_fields__) == {"adv_tier", "max_participation"}
    assert set(GateCriteria.__dataclass_fields__) == {
        "backtest_pass",
        "shadow",
        "direction_agree",
        "small_position",
    }
    assert "segments" in BacktestConfig.__dataclass_fields__
    assert "gate_criteria" in BacktestConfig.__dataclass_fields__


def test_price_bar_has_avg_amount():
    fields = set(PriceBar.__dataclass_fields__)
    assert "avg_amount" in fields
    bar = PriceBar(
        code="000001",
        trade_date="2020-01-06",
        open=10.0,
        high=10.0,
        low=10.0,
        close=10.0,
        amount=1_000_000.0,
        avg_amount=500_000.0,
    )
    assert bar.avg_amount == 500_000.0


def test_attribution_result_verdict_and_optional_fields():
    from service.backtest.models import AttributionResult

    fields = AttributionResult.__dataclass_fields__
    assert set(fields) == {
        "verdict",
        "beta",
        "size",
        "value",
        "momentum",
        "exposures",
        "contributions",
        "unexplained",
    }
    result = AttributionResult(
        verdict=Verdict.INCONCLUSIVE,
        beta=None,
        size=0.1,
        value=0.2,
        momentum=0.3,
        exposures={"size": 0.1},
        contributions={"size": 0.0},
        unexplained=None,
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.beta is None and result.unexplained is None


def test_event_study_result_has_verdict_field():
    from service.backtest.models import EventStudyResult

    fields = set(EventStudyResult.__dataclass_fields__)
    assert "verdict" in fields
    result = EventStudyResult(
        verdict=Verdict.INCONCLUSIVE,
        windows={},
        n_events=0,
        inference_method="block_bootstrap",
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.windows == {}


def test_auto_shrink_token_lands_and_unknown_token_rejected(tmp_path, config_factory):
    from common.exceptions import MissingBacktestConfigError
    from service.backtest.models import AUTO_SHRINK, BacktestConfig

    cfg = BacktestConfig.from_config(
        config_factory(**{"shrink": "auto_by_sample_size"}), base_dir=tmp_path
    )
    assert cfg.shrink == AUTO_SHRINK
    with pytest.raises(MissingBacktestConfigError):
        BacktestConfig.from_config(config_factory(**{"shrink": "fixed_0.5"}), base_dir=tmp_path)
