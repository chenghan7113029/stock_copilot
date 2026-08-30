"""CLI report persona-stress 命令测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apps.cli import run_report_persona_stress
from apps.formatters import format_persona_stress_report
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.guard.persona_stress_narrator import PersonaStressOutcome, pending_persona_stress
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


def test_format_persona_stress_json_and_disclaimer():
    text = format_persona_stress_report(
        code="600519",
        evidence={
            "bull_evidence": [{"index": 1, "text": "低估"}],
            "bear_evidence": [{"index": 1, "text": "风险"}],
        },
        persona_stress=pending_persona_stress(),
        confrontation_id=9,
        as_json=True,
    )
    assert '"confrontation_id": 9' in text
    assert "value_quality" in text
    assert "思维透镜" in text or "不构成买卖建议" in text


def test_format_persona_stress_text_pending():
    text = format_persona_stress_report(
        code="600519",
        evidence={"bull_evidence": [], "bear_evidence": []},
        persona_stress=pending_persona_stress(),
        as_json=False,
    )
    assert "Persona 压力测试" in text
    assert "待 `--narrate`" in text
    assert "不构成买卖建议" in text


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_persona_stress_level0_creates_record(
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
    mock_bucketer_cls.return_value.bucket.return_value = buckets
    saved = MagicMock()
    saved.id = 11
    mock_confront_repo_cls.return_value.save.return_value = saved

    with patch("apps.cli.PersonaStressNarrator") as mock_narrator_cls:
        mock_narrator_cls.return_value.build_evidence.return_value = {
            "code": "600519",
            "bull_evidence": [{"index": 1, "text": "多方"}],
            "bear_evidence": [{"index": 1, "text": "空方"}],
        }
        run_report_persona_stress("600519")

    captured = capsys.readouterr()
    assert "Persona 压力测试" in captured.out
    save_kw = mock_confront_repo_cls.return_value.save.call_args.kwargs
    assert save_kw["persona_stress"]["personas"][0]["status"] == "pending"
    session.commit.assert_called()


@patch("apps.cli.PersonaStressNarrator")
@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.LLMNarrateCacheRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_persona_stress_updates_existing_confrontation(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_cache_cls,
    mock_confront_repo_cls,
    mock_narrator_cls,
    capsys,
):
    mock_cfg.return_value = {}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)

    existing = MagicMock()
    existing.id = 12
    existing.code = "600519"
    existing.evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "多方"}],
        "bear_evidence": [{"index": 1, "text": "空方"}],
    }
    mock_confront_repo_cls.return_value.get.return_value = existing
    updated = MagicMock()
    updated.id = 12
    mock_confront_repo_cls.return_value.update_persona_stress.return_value = updated

    payload = {
        "personas": [
            {
                "id": "value_quality",
                "status": "ok",
                "output": {
                    "lens_summary": "质量优先",
                    "emphasized_refs": [{"side": "bull", "index": 1}],
                    "blind_spots": [],
                    "questions_for_self": [],
                    "disclaimer": "persona 为思维透镜，不构成买卖建议。",
                    "confidence": 0.7,
                },
                "error": None,
            },
            {"id": "trend_momentum", "status": "failed", "output": None, "error": "fail"},
            {
                "id": "risk_governor",
                "status": "ok",
                "output": {
                    "lens_summary": "控风险",
                    "emphasized_refs": [{"side": "bear", "index": 1}],
                    "blind_spots": [],
                    "questions_for_self": [],
                    "disclaimer": "persona 为思维透镜，不构成买卖建议。",
                    "confidence": 0.6,
                },
                "error": None,
            },
        ],
        "disclaimer": "persona 为思维透镜，不构成买卖建议。",
    }
    mock_narrator_cls.return_value.stress.return_value = PersonaStressOutcome(
        payload=payload,
        evidence_payload=existing.evidence,
    )

    run_report_persona_stress(
        "600519", narrate=True, confrontation_id=12, as_json=True
    )
    mock_confront_repo_cls.return_value.save.assert_not_called()
    mock_confront_repo_cls.return_value.update_persona_stress.assert_called_once()
    captured = capsys.readouterr()
    assert "思维透镜" in captured.out or "不构成买卖建议" in captured.out
    assert "trend_momentum" in captured.out
