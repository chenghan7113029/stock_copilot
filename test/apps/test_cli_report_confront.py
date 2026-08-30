"""CLI report confront 命令测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apps.cli import run_report_confront
from apps.formatters import format_confront_report
from common.llm.models import NarrateResult
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.guard.confrontation_narrator import ConfrontationNarrateOutcome
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult


def _dual_report() -> DualTrackReport:
    value = ValueAnalysisResult(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype="value_growth",
        method_keys_used=[],
        fair_value_range=None,
        margin_of_safety=25.0,
        price_percentile=None,
        assessment="低估",
        confidence="High",
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    tech = TechAnalysisResult(
        code="600519",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=80,
        buy_signal=BuySignal.STRONG_BUY,
        signal_reasons=["MA5 上穿 MA20"],
        risk_factors=["RSI 偏高"],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    return DualTrackReport(
        code="600519",
        value_result=value,
        tech_result=tech,
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=ValueRating.UNDERVALUED,
        analysis_summary="股票代码: 600519 | 综合信号: 强烈买入",
    )


def test_format_confront_report_json_includes_ids():
    text = format_confront_report(
        code="600519",
        evidence={
            "bull_evidence": [{"index": 1, "text": "低估"}],
            "bear_evidence": [{"index": 1, "text": "风险"}],
        },
        narrate_status="skipped",
        confrontation_id=7,
        as_json=True,
    )
    assert '"confrontation_id": 7' in text
    assert '"index": 1' in text


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_confront_level0_persists_skipped(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    mock_confront_repo_cls,
    capsys,
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["多方"]
    buckets.bear_evidence = ["空方"]
    buckets.numbered.return_value = {
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [{"index": 1, "text": "空方"}],
    }
    mock_bucketer_cls.return_value.bucket.return_value = buckets
    saved = MagicMock()
    saved.id = 42
    mock_confront_repo_cls.return_value.save.return_value = saved

    run_report_confront("600519")
    captured = capsys.readouterr()
    assert "红蓝对抗报告" in captured.out
    assert "42" in captured.out or "confrontation_id" in captured.out.lower() or "42" in captured.out
    assert mock_confront_repo_cls.return_value.save.call_args.kwargs["narrate_status"] == "skipped"
    session.commit.assert_called()


@patch("apps.cli.ConfrontationNarrator")
@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.LLMNarrateCacheRepo")
@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_confront_narrate_without_llm_exits_nonzero(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    mock_cache_cls,
    mock_confront_repo_cls,
    mock_narrator_cls,
    capsys,
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["多方"]
    buckets.bear_evidence = ["空方"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets

    narrator = mock_narrator_cls.return_value
    narrator.build_evidence.return_value = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [{"index": 1, "text": "空方"}],
    }
    narrator.narrate.return_value = ConfrontationNarrateOutcome(
        result=NarrateResult(ok=False, error="LLM 未配置"),
        narrative=None,
        evidence_payload=narrator.build_evidence.return_value,
    )
    saved = MagicMock()
    saved.id = 3
    mock_confront_repo_cls.return_value.save.return_value = saved

    try:
        run_report_confront("600519", narrate=True)
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code == 1
    assert raised
    assert mock_confront_repo_cls.return_value.save.call_args.kwargs["narrate_status"] == "failed"
    captured = capsys.readouterr()
    assert "叙事失败" in captured.out or "LLM 未配置" in captured.out
