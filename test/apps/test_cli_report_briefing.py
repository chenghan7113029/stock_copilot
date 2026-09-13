"""CLI report briefing 命令测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import build_parser, run_report_briefing
from service.report.models.briefing_view import BriefingView, SectionStatus


def test_parser_briefing_default_narrate_on():
    args = build_parser().parse_args(["report", "briefing", "600519"])
    assert args.report_type == "briefing"
    assert args.no_narrate is False


def test_parser_briefing_no_narrate_flag():
    args = build_parser().parse_args(["report", "briefing", "600519", "--no-narrate", "-o", "out.html"])
    assert args.no_narrate is True
    assert args.output == "out.html"


@patch("apps.cli.BriefingComposer")
@patch("apps.cli.HtmlBriefingRenderer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.ensure_sqlite_schema")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_briefing_writes_html(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_schema,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_renderer_cls,
    mock_composer_cls,
    tmp_path: Path,
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    view = BriefingView(
        code="600519",
        name="贵州茅台",
        section_statuses={
            "narrative": SectionStatus(status="ok"),
            "persona": SectionStatus(status="ok"),
        },
    )
    mock_composer_cls.return_value.build.return_value = view
    mock_renderer_cls.return_value.render.return_value = "<html><body>ok</body></html>"

    out = tmp_path / "600519_briefing.html"
    run_report_briefing("600519", narrate=True, output=str(out))

    mock_composer_cls.return_value.build.assert_called_once_with("600519", narrate=True)
    assert out.read_text(encoding="utf-8") == "<html><body>ok</body></html>"


@patch("apps.cli.BriefingComposer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.ensure_sqlite_schema")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_briefing_missing_data_exits_nonzero(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_schema,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_composer_cls,
):
    from service.report.briefing_composer import LocalDataMissingError

    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_composer_cls.return_value.build.side_effect = LocalDataMissingError("600519")

    with pytest.raises(SystemExit) as exc:
        run_report_briefing("600519", narrate=False)
    assert exc.value.code == 1


@patch("apps.cli.BriefingComposer")
@patch("apps.cli.HtmlBriefingRenderer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.ensure_sqlite_schema")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_briefing_narrate_failed_still_zero(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_schema,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_renderer_cls,
    mock_composer_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    view = BriefingView(
        code="600519",
        section_statuses={
            "narrative": SectionStatus(
                status="failed", hint="互驳叙事失败：LLM down"
            ),
            "persona": SectionStatus(status="ok"),
        },
    )
    mock_composer_cls.return_value.build.return_value = view
    mock_renderer_cls.return_value.render.return_value = "<html/>"

    run_report_briefing("600519", narrate=True)
    err = capsys.readouterr().err
    assert "LLM down" in err
