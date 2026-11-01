"""CLI report toplist 命令测试。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_toplist
from apps.formatters import format_top_list_report
from service.toplist.models.top_list_result import (
    ActiveLevel,
    InstParticipation,
    NetAmountLevel,
    TopListResult,
)


def _result() -> TopListResult:
    return TopListResult(
        code="600519",
        appearance_count=3,
        active_level=ActiveLevel.ACTIVE,
        latest_trade_date="2026-10-30",
        latest_net_amount=6.8e7,
        latest_net_amount_level=NetAmountLevel.LARGE_NET_BUY,
        latest_event_count=1,
        latest_reasons=["日涨幅偏离值达到7%的前5只证券"],
        inst_net_buy=1.4e7,
        inst_participation=InstParticipation.INST_BUY,
        reason_categories=["涨幅偏离"],
        coverage_trade_days=20,
        coverage_start="2026-10-09",
        coverage_end="2026-10-30",
        reasons=["近 90 日上榜 3 个交易日（活跃）"],
        data_timestamp=datetime(2026, 11, 1),
    )


def test_format_top_list_report_includes_disclaimer() -> None:
    text = format_top_list_report(_result())
    assert "龙虎榜/席位报告" in text
    assert "龙虎榜为观察维度，不构成买卖建议" in text
    assert "机构席位净买" in text
    assert "涨幅偏离" in text


def test_format_top_list_report_json_contains_fields() -> None:
    payload = json.loads(format_top_list_report(_result(), as_json=True))
    assert payload["code"] == "600519"
    assert payload["appearance_count"] == 3
    assert payload["active_level"] == "活跃"
    assert payload["latest_trade_date"] == "2026-10-30"
    assert payload["latest_net_amount"] == 6.8e7
    assert payload["inst_net_buy"] == 1.4e7
    assert payload["reason_categories"] == ["涨幅偏离"]
    assert "warnings" in payload
    assert "disclaimer" in payload


@patch("apps.cli._top_list_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_toplist_success(mock_cfg, mock_sf, mock_engine, mock_analyzer, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = _result()

    run_report_toplist("600519")

    out = capsys.readouterr().out
    assert "龙虎榜/席位报告" in out
    assert "龙虎榜为观察维度，不构成买卖建议" in out


@patch("apps.cli._top_list_analyzer")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_toplist_without_cache_exits(
    mock_cfg, mock_sf, mock_engine, mock_analyzer, capsys
) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = None

    with pytest.raises(SystemExit) as exc:
        run_report_toplist("600519")

    assert exc.value.code == 1
    assert "未找到 600519 的龙虎榜数据，请先运行 sync" in capsys.readouterr().err


@patch("apps.cli.run_report_toplist")
def test_cli_report_toplist_invocation(mock_run) -> None:
    main(["report", "toplist", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)
