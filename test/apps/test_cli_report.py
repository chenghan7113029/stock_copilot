"""CLI report 命令测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_tech, run_report_value
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult


@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.load_app_config")
def test_report_tech_success(mock_cfg, mock_analyzer_cls):
    mock_cfg.return_value = {"tech": {"kline_days": 90}}
    result = TechAnalysisResult(
        code="600519",
        buy_signal=BuySignal.HOLD,
        signal_score=70,
        trend_status=TrendStatus.BULL,
        kline_last_date="2025-06-28",
        quote_mode="eod",
    )
    mock_analyzer_cls.from_config.return_value.analyze.return_value = result

    run_report_tech("600519")
    mock_analyzer_cls.from_config.return_value.analyze.assert_called_once_with(
        "600519", offline=True
    )


@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.load_app_config")
def test_report_tech_no_cache(mock_cfg, mock_analyzer_cls, capsys):
    mock_cfg.return_value = {}
    result = TechAnalysisResult(code="600519", warnings=["无缓存数据"])
    result.risk_factors.append("无缓存数据，请先运行 sync")
    mock_analyzer_cls.from_config.return_value.analyze.return_value = result

    with pytest.raises(SystemExit) as exc:
        run_report_tech("600519")
    assert exc.value.code == 1


@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.load_app_config")
def test_report_tech_json(mock_cfg, mock_analyzer_cls, capsys):
    mock_cfg.return_value = {}
    mock_analyzer_cls.from_config.return_value.analyze.return_value = TechAnalysisResult(
        code="600519", signal_score=60, kline_last_date="2025-06-28"
    )
    run_report_tech("600519", as_json=True)
    captured = capsys.readouterr()
    assert '"code": "600519"' in captured.out


@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_value_success(
    mock_cfg, mock_sf, mock_engine, mock_repo_cls, mock_analyzer_cls
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_analyzer_cls.from_config.return_value.analyze_offline.return_value = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1800.0,
        prototype="quality_growth",
        method_keys_used=[],
        fair_value_range=None,
        margin_of_safety=None,
        price_percentile=None,
        assessment="合理",
        confidence="Medium",
        data_timestamp=datetime(2025, 6, 28, 9, 15),
    )

    run_report_value("600519")
    mock_analyzer_cls.from_config.return_value.analyze_offline.assert_called_once_with("600519")


@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_value_no_cache(mock_cfg, mock_sf, mock_engine, mock_repo_cls, mock_analyzer_cls):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer_cls.from_config.return_value.analyze_offline.return_value = None

    with pytest.raises(SystemExit) as exc:
        run_report_value("600519")
    assert exc.value.code == 1


@patch("apps.cli.run_report_tech")
def test_cli_report_tech_invocation(mock_run):
    main(["report", "tech", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)


@patch("apps.cli.run_report_value")
def test_cli_report_value_passes_anchor_price_opt_in_flag(mock_run):
    main(["report", "value", "600519", "--show-anchor-price"])

    mock_run.assert_called_once_with(
        "600519",
        as_json=False,
        output=None,
        config=None,
        show_anchor_price=True,
    )


@patch("apps.cli.run_report_value")
def test_cli_report_value_hides_anchor_price_by_default(mock_run):
    main(["report", "value", "600519"])

    mock_run.assert_called_once_with(
        "600519",
        as_json=False,
        output=None,
        config=None,
        show_anchor_price=False,
    )
