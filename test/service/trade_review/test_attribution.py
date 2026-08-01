"""FIFO 复盘归因单元测试。"""

from datetime import datetime

from dao.models import ChecklistRecord, TradeRecord
from service.trade_review.attribution import TradeReviewAnalyzer


def _trade(
    action: str,
    quantity: int,
    price: float,
    date: str,
    *,
    checklist_id: int | None = None,
) -> TradeRecord:
    return TradeRecord(
        code="600519",
        action=action,
        quantity=quantity,
        price=price,
        trade_date=datetime.fromisoformat(date),
        checklist_id=checklist_id,
    )


def _checklist(record_id: int, passed: bool) -> ChecklistRecord:
    return ChecklistRecord(
        id=record_id,
        code="600519",
        action="buy",
        value_reasons_json="[]",
        rejection_reasons_json="[]",
        passed=passed,
    )


def test_analyze_calculates_fifo_win_rate_for_closed_pairs():
    result = TradeReviewAnalyzer().analyze(
        [
            _trade("BUY", 100, 100.0, "2026-08-01"),
            _trade("SELL", 100, 110.0, "2026-08-02"),
            _trade("BUY", 100, 100.0, "2026-08-03"),
            _trade("SELL", 100, 90.0, "2026-08-04"),
        ]
    )

    assert result.total_trades == 2
    assert result.win_rate == 0.5
    assert result.avg_return == 0.0


def test_analyze_splits_partial_closes_and_excludes_open_quantity():
    result = TradeReviewAnalyzer().analyze(
        [
            _trade("BUY", 100, 100.0, "2026-08-01"),
            _trade("SELL", 50, 110.0, "2026-08-02"),
            _trade("SELL", 50, 90.0, "2026-08-03"),
            _trade("BUY", 20, 100.0, "2026-08-04"),
        ]
    )

    assert result.total_trades == 2
    assert result.win_rate == 0.5
    assert result.open_positions == 20


def test_analyze_marks_only_passed_checklist_losses_below_threshold_as_badcase():
    result = TradeReviewAnalyzer().analyze(
        [
            _trade("BUY", 100, 100.0, "2026-08-01", checklist_id=1),
            _trade("SELL", 100, 85.0, "2026-08-02"),
            _trade("BUY", 100, 100.0, "2026-08-03", checklist_id=2),
            _trade("SELL", 100, 85.0, "2026-08-04"),
        ],
        checklists=[_checklist(1, True), _checklist(2, False)],
    )

    assert result.checklist_data_available is True
    assert len(result.badcase_list) == 1
    assert result.badcase_list[0].checklist_id == 1


def test_analyze_degrades_when_no_checklist_can_be_resolved():
    result = TradeReviewAnalyzer().analyze(
        [
            _trade("BUY", 100, 100.0, "2026-08-01", checklist_id=99),
            _trade("SELL", 100, 85.0, "2026-08-02"),
        ]
    )

    assert result.checklist_data_available is False
    assert result.badcase_list == []
    assert any("无法判定 Badcase" in warning for warning in result.warnings)
