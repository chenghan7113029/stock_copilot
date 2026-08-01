"""CLI report summary 命令测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_summary
from apps.formatters import format_summary_report
from common.llm.models import NarrateResult
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult


def _dual_report(*, with_data: bool = True) -> DualTrackReport:
    if not with_data:
        tech = TechAnalysisResult(
            code="600519",
            warnings=["无缓存数据"],
            risk_factors=["无缓存数据，请先运行 sync"],
        )
        return DualTrackReport(
            code="600519",
            value_result=None,
            tech_result=tech,
            warnings=["价值面无本地快照"],
        )
    return DualTrackReport(
        code="600519",
        value_result=ValueAnalysisResult(
            code="600519",
            name="贵州茅台",
            current_price=1500.0,
            prototype="value_growth",
            method_keys_used=[],
            fair_value_range=None,
            margin_of_safety=0.25,
            price_percentile=None,
            assessment="低估",
            confidence="High",
            data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
        ),
        tech_result=TechAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            signal_score=70,
            buy_signal=BuySignal.BUY,
            signal_reasons=["多头"],
            risk_factors=[],
        ),
        combined_signal=CombinedSignal.BUY,
        value_rating=ValueRating.UNDERVALUED,
        analysis_summary="股票代码: 600519 | 综合信号: 买入",
    )


@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_summary_offline(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["b1", "b2"]
    buckets.bear_evidence = ["e1"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets

    run_report_summary("600519")
    captured = capsys.readouterr()
    assert "综合摘要" in captured.out
    assert "确定性摘要" in captured.out
    assert "多方 2 条" in captured.out
    assert "LLM 综合叙事" not in captured.out


@patch("apps.cli.narrate_comprehensive_report")
@patch("apps.cli.LLMNarrateCacheRepo")
@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_summary_narrate_success(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    mock_cache_cls,
    mock_narrate,
    capsys,
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["b1"]
    buckets.bear_evidence = ["e1"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets
    mock_narrate.return_value = NarrateResult(
        ok=True,
        data={
            "summary": "价值低估且技术偏多",
            "key_points": ["安全边际充足"],
            "risks": ["注意回调"],
            "confidence": 0.85,
        },
        confidence=0.85,
    )

    run_report_summary("600519", narrate=True)
    captured = capsys.readouterr()
    assert "LLM 综合叙事" in captured.out
    assert "价值低估且技术偏多" in captured.out
    mock_narrate.assert_called_once()
    session.commit.assert_called()


@patch("apps.cli.narrate_comprehensive_report")
@patch("apps.cli.LLMNarrateCacheRepo")
@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_summary_narrate_degrades(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    mock_cache_cls,
    mock_narrate,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["b1"]
    buckets.bear_evidence = ["e1"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets
    mock_narrate.return_value = NarrateResult(ok=False, error="LLM 未配置")

    run_report_summary("600519", narrate=True)
    captured = capsys.readouterr()
    assert "确定性摘要" in captured.out
    assert "LLM 叙事生成失败" in captured.out
    assert "LLM 未配置" in captured.out


@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_summary_no_cache(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report(with_data=False)

    with pytest.raises(SystemExit) as exc:
        run_report_summary("600519")
    assert exc.value.code == 1
    assert "未找到 600519 的本地数据" in capsys.readouterr().err


@patch("apps.cli.run_report_summary")
def test_cli_report_summary_invocation(mock_run):
    main(["report", "summary", "600519", "--narrate", "--json"])
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs.get("narrate") is True
    assert kwargs.get("as_json") is True


def test_format_summary_report_degrade_and_success():
    det = {
        "code": "600519",
        "name": "贵州茅台",
        "analysis_summary": "摘要行",
        "combined_signal": "买入",
        "value_rating": "低估",
        "bull_evidence_count": 2,
        "bear_evidence_count": 1,
    }
    text = format_summary_report(det, narrative_error="LLM 未配置")
    assert "LLM 叙事生成失败" in text
    assert "确定性摘要" in text
    assert "=== 综合摘要 600519 贵州茅台 ===" in text
    assert "名称: 贵州茅台" in text

    ok = format_summary_report(
        det,
        narrative={
            "summary": "叙事正文",
            "key_points": ["要点1"],
            "risks": ["风险1"],
            "confidence": 0.9,
        },
    )
    assert "叙事正文" in ok
    assert "要点1" in ok


def test_format_summary_report_without_name():
    det = {
        "code": "600519",
        "combined_signal": "观望",
        "value_rating": "高估",
        "bull_evidence_count": 0,
        "bear_evidence_count": 0,
    }
    text = format_summary_report(det)
    assert "=== 综合摘要 600519 ===" in text
    assert "名称:" not in text


def test_report_summary_includes_stock_name(capsys):
    from unittest.mock import MagicMock, patch

    with (
        patch("apps.cli.load_app_config", return_value={}),
        patch("apps.cli.make_session_factory") as mock_sf,
        patch("apps.cli.create_db_engine"),
        patch("apps.cli.StockSnapshotRepo"),
        patch("apps.cli.ValueAnalyzer"),
        patch("apps.cli.TechAnalyzer"),
        patch("apps.cli.DualTrackAnalyzer") as mock_dual_cls,
        patch("apps.cli.EvidenceBucketer") as mock_bucketer_cls,
    ):
        mock_sf.return_value = MagicMock(return_value=MagicMock())
        mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
        buckets = MagicMock()
        buckets.bull_evidence = ["b1"]
        buckets.bear_evidence = ["e1"]
        mock_bucketer_cls.return_value.bucket.return_value = buckets

        run_report_summary("600519")

    out = capsys.readouterr().out
    assert "=== 综合摘要 600519 贵州茅台 ===" in out
    assert "名称: 贵州茅台" in out
