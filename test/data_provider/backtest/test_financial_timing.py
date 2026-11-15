"""T2.6 财务公告日对齐（R11：ann_date 优先，缺失走保守回退并标注）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError
from data_provider.backtest.financial_timing import (
    FinancialTimingAdapter,
    annotate_visible_from,
    conservative_visible_from,
)


def test_ann_date_wins():
    rows = annotate_visible_from(
        [
            {
                "code": "000001",
                "report_period": "20231231",
                "ann_date": "2024-04-25",
                "end_date": "2023-12-31",
            }
        ]
    )
    assert rows[0]["visible_from"] == "2024-04-25"
    assert rows[0]["ann_date_fallback"] is False


def test_missing_ann_date_falls_back_to_legal_deadline():
    rows = annotate_visible_from(
        [{"code": "000001", "report_period": "20231231", "ann_date": None}]
    )
    assert rows[0]["visible_from"] == "2024-04-30"
    assert rows[0]["ann_date_fallback"] is True


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("20230331", "2023-04-30"),
        ("20230630", "2023-08-31"),
        ("20230930", "2023-10-31"),
        ("20231231", "2024-04-30"),
    ],
)
def test_conservative_cutoffs(period, expected):
    assert conservative_visible_from(period) == expected


def test_unknown_report_period_reports_gap():
    with pytest.raises(BacktestDataGapError):
        conservative_visible_from("20230228")


def test_no_source_reports_gap():
    with pytest.raises(BacktestDataGapError):
        FinancialTimingAdapter().load_rows(["000001"], "2024-01-01")


def test_adapter_groups_and_annotates():
    adapter = FinancialTimingAdapter(
        fetch=lambda **kwargs: [
            {"code": "000001", "report_period": "20231231", "ann_date": "2024-04-25"}
        ]
    )
    grouped = adapter.load_rows(["000001"], "2024-05-01")
    assert grouped["000001"][0]["visible_from"] == "2024-04-25"
