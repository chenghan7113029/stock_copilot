"""CLI report fundflow 命令测试。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_fundflow
from apps.formatters import format_fund_flow_report
from service.fundflow.models.fund_flow_result import FundFlowResult, LeverageDirection


def _result() -> FundFlowResult:
    return FundFlowResult(
        code="600519",
        margin_balance_change_pct=10.0,
        short_balance_change_pct=1.0,
        main_net_inflow_5d=800.0,
        leverage_direction=LeverageDirection.ADD_LEVERAGE,
        reasons=["两融余额近 5 个交易日变化 +10.0%"],
        data_timestamp=datetime(2026, 8, 1),
    )


def test_format_fund_flow_report_includes_disclaimer() -> None:
    text = format_fund_flow_report(_result())
    assert "个股资金面报告" in text
    assert "资金面数据为观察维度，不构成买卖建议" in text


def test_format_fund_flow_report_json_contains_fields() -> None:
    payload = json.loads(format_fund_flow_report(_result(), as_json=True))
    assert payload["margin_balance_change_pct"] == 10.0
    assert payload["main_net_inflow_5d"] == 800.0
    assert "disclaimer" in payload


@patch("apps.cli._fund_flow_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_fundflow_success(mock_cfg, mock_sf, mock_engine, mock_ff, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_ff.return_value.analyze_offline.return_value = _result()

    run_report_fundflow("600519")

    out = capsys.readouterr().out
    assert "个股资金面报告" in out
    assert "资金面数据为观察维度，不构成买卖建议" in out


@patch("apps.cli._fund_flow_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_fundflow_without_cache_exits(mock_cfg, mock_sf, mock_engine, mock_ff, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_ff.return_value.analyze_offline.return_value = None

    with pytest.raises(SystemExit) as exc:
        run_report_fundflow("600519")

    assert exc.value.code == 1
    assert "未找到 600519 的资金面数据，请先运行 sync" in capsys.readouterr().err


@patch("apps.cli.run_report_fundflow")
def test_cli_report_fundflow_invocation(mock_run) -> None:
    main(["report", "fundflow", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)
