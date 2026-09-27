"""CLI report events 命令测试。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_events
from apps.formatters import format_event_report
from service.event.models.event_result import EventResult


def _result() -> EventResult:
    return EventResult(
        code="600519",
        holder_net_sell_90d=70000.0,
        repurchase_active=False,
        upcoming_unlock_30d=None,
        pledge_ratio=52.0,
        block_trade_discount=None,
        northbound_net_inflow_5d=30.0,
        reasons=["质押比例 52%"],
        data_timestamp=datetime(2026, 8, 1),
    )


def test_format_event_report_includes_disclaimer() -> None:
    text = format_event_report(_result())
    assert "治理/事件面报告" in text
    assert "事件面数据为观察维度，不构成买卖建议" in text


def test_format_event_report_json_contains_fields() -> None:
    payload = json.loads(format_event_report(_result(), as_json=True))
    assert payload["holder_net_sell_90d"] == 70000.0
    assert payload["pledge_ratio"] == 52.0
    assert "disclaimer" in payload


@patch("apps.cli._event_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_events_success(mock_cfg, mock_sf, mock_engine, mock_analyzer, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = _result()

    run_report_events("600519")

    out = capsys.readouterr().out
    assert "治理/事件面报告" in out
    assert "事件面数据为观察维度，不构成买卖建议" in out


@patch("apps.cli._event_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_events_without_cache_exits(mock_cfg, mock_sf, mock_engine, mock_analyzer, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = None

    with pytest.raises(SystemExit) as exc:
        run_report_events("600519")

    assert exc.value.code == 1
    assert "未找到 600519 的治理事件数据，请先运行 sync" in capsys.readouterr().err


@patch("apps.cli.run_report_events")
def test_cli_report_events_invocation(mock_run) -> None:
    main(["report", "events", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)
