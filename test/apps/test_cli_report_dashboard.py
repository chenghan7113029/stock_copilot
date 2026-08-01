"""CLI report dashboard 命令测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_dashboard
from apps.formatters import format_dashboard_report
from service.report.dashboard_builder import LocalDataMissingError
from service.report.models.dashboard_view import DashboardView


def _view() -> DashboardView:
    return DashboardView(
        code="600519",
        value_section="评估: 低估",
        tech_section="趋势: 强势多头",
        sentiment_section="情绪面待建（见 PO-06）",
        checklist_section="Checklist 待建（见 PO-04）",
        combined_summary="红蓝证据: 多方 5 条 / 空方 3 条",
    )


@patch("apps.cli.DashboardBuilder")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dashboard_success(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_builder_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_builder_cls.return_value.build.return_value = _view()

    run_report_dashboard("600519")
    captured = capsys.readouterr()
    assert "多维看板" in captured.out
    assert "价值面" in captured.out
    assert "PO-06" in captured.out
    assert "PO-04" in captured.out
    mock_builder_cls.return_value.build.assert_called_once_with("600519")


@patch("apps.cli.DashboardBuilder")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dashboard_json(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_builder_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_builder_cls.return_value.build.return_value = _view()

    run_report_dashboard("600519", as_json=True)
    captured = capsys.readouterr()
    assert '"value_section"' in captured.out
    assert '"tech_section"' in captured.out
    assert '"sentiment_section"' in captured.out
    assert '"checklist_section"' in captured.out
    assert '"combined_summary"' in captured.out


@patch("apps.cli.DashboardBuilder")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dashboard_output_file(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_builder_cls,
    tmp_path: Path,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_builder_cls.return_value.build.return_value = _view()

    out = tmp_path / "dash.json"
    run_report_dashboard("600519", as_json=True, output=str(out))
    assert out.exists()
    assert "value_section" in out.read_text(encoding="utf-8")


@patch("apps.cli.DashboardBuilder")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dashboard_no_cache(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_builder_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_builder_cls.return_value.build.side_effect = LocalDataMissingError("600519")

    with pytest.raises(SystemExit) as exc:
        run_report_dashboard("600519")
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "未找到 600519 的本地数据" in captured.err


@patch("apps.cli.run_report_dashboard")
def test_cli_report_dashboard_invocation(mock_run):
    main(["report", "dashboard", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)


def test_format_dashboard_report_text_and_json():
    text = format_dashboard_report(_view())
    assert "--- 价值面 ---" in text
    assert "--- 技术面 ---" in text
    assert "--- 情绪面 ---" in text
    assert "--- Checklist ---" in text
    assert "--- 综合摘要 ---" in text
    js = format_dashboard_report(_view(), as_json=True)
    assert '"code": "600519"' in js
    assert '"combined_summary"' in js
