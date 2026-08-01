"""CLI entry-check 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_entry_check
from service.guard.fresh_entry_check import LocalDataMissingError
from service.guard.models.fresh_entry_view import FreshEntryView


def _view() -> FreshEntryView:
    return FreshEntryView(
        code="600519",
        current_price=1500.0,
        value_summary="价值面：合理",
        tech_summary="技术面：多头趋势",
        framing_question="若你今天没有 600519 的仓位，以现价 1500.00 买入，你还会买吗？",
        has_position=True,
        reminder_text="以上评估已隐藏你的实际买入依据，请基于当前信息独立判断。",
    )


@patch("apps.cli.FreshEntryCheck")
@patch("apps.cli.TechAnalyzer.from_config")
@patch("apps.cli.ValueAnalyzer.from_config")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_run_entry_check_outputs_hidden_cost_report(
    mock_cfg, mock_engine, mock_session_factory, mock_value, mock_tech, mock_check, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    mock_check.return_value.build.return_value = _view()

    run_entry_check("600519")

    text = capsys.readouterr().out
    assert "若你今天没有" in text
    assert "成本价" not in text
    assert "1500.00" in text


@patch("apps.cli.FreshEntryCheck")
@patch("apps.cli.TechAnalyzer.from_config")
@patch("apps.cli.ValueAnalyzer.from_config")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_run_entry_check_reports_missing_local_data(
    mock_cfg, mock_engine, mock_session_factory, mock_value, mock_tech, mock_check, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    mock_check.return_value.build.side_effect = LocalDataMissingError("未找到 600519 的本地数据，请先运行 sync")

    with pytest.raises(SystemExit, match="1"):
        run_entry_check("600519")

    assert "[error] 未找到 600519 的本地数据，请先运行 sync" in capsys.readouterr().err


@patch("apps.cli.run_entry_check")
def test_entry_check_command_routes_arguments(mock_check):
    main(["entry-check", "600519", "--json", "--output", "report.json", "--quiet"])

    mock_check.assert_called_once()
    args, kwargs = mock_check.call_args
    assert args == ("600519",)
    assert kwargs["as_json"] is True
    assert kwargs["output"] == "report.json"
