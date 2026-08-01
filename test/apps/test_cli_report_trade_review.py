"""CLI trade-review 报告单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_trade_review
from service.trade_review.models.trade_review_result import TradeReviewResult


def _result() -> TradeReviewResult:
    return TradeReviewResult(
        win_rate=0.5,
        avg_return=0.0,
        total_trades=2,
        open_positions=0,
        badcase_list=[],
        checklist_data_available=False,
        warnings=["⚠ 当前无关联 Checklist 记录，无法判定 Badcase"],
    )


@patch("apps.cli.TradeReviewAnalyzer")
@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_report_trade_review_uses_all_records_and_formats_result(
    mock_cfg, mock_engine, mock_session_factory, mock_repo, mock_analyzer, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    mock_repo.return_value.find_all.return_value = [MagicMock()]
    mock_analyzer.return_value.analyze.return_value = _result()

    run_report_trade_review()

    mock_repo.return_value.find_all.assert_called_once()
    assert "FIFO 胜率" in capsys.readouterr().out


@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_report_trade_review_rejects_when_no_records(
    mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    mock_repo.return_value.find_all.return_value = []

    with pytest.raises(SystemExit):
        run_report_trade_review()

    assert "未找到交易记录" in capsys.readouterr().err


@patch("apps.cli.run_report_trade_review")
def test_report_trade_review_command_routes_optional_code(mock_report):
    main(["report", "trade-review", "--code", "600519", "--json"])

    mock_report.assert_called_once_with("600519", as_json=True, output=None, config=None)
