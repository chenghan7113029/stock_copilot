"""BriefingComposer 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.guard.confrontation_narrator import ConfrontationNarrateOutcome
from service.guard.persona_stress_narrator import PersonaStressOutcome
from service.report.briefing_composer import BriefingComposer, LocalDataMissingError
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationRange, ValuationResult
from common.llm.models import NarrateResult


def _value(**kwargs) -> ValueAnalysisResult:
    base = dict(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        prototype="value_growth",
        method_keys_used=["dcf"],
        fair_value_range=ValuationRange(low=1800, base=2000, high=2200),
        margin_of_safety=25.0,
        price_percentile=0.3,
        assessment="低估",
        confidence="High",
        method_results={
            "dcf": ValuationResult(
                method="dcf",
                fair_value=2000,
                current_price=1500,
                premium_discount=-0.25,
                assessment="Undervalued",
            )
        },
        warnings=[],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    base.update(kwargs)
    return ValueAnalysisResult(**base)


def _tech(**kwargs) -> TechAnalysisResult:
    base = dict(
        code="600519",
        trend_status=TrendStatus.STRONG_BULL,
        signal_score=80,
        buy_signal=BuySignal.STRONG_BUY,
        signal_reasons=["MA5 上穿 MA20"],
        risk_factors=["RSI 偏高"],
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    base.update(kwargs)
    return TechAnalysisResult(**base)


def _report(value=None, tech=None) -> DualTrackReport:
    return DualTrackReport(
        code="600519",
        value_result=value,
        tech_result=tech,
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=ValueRating.UNDERVALUED,
        analysis_summary="股票代码: 600519",
        data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


def _composer(dual_report: DualTrackReport, *, narrate_ok: bool = True):
    dual = MagicMock()
    dual.analyze_offline.return_value = dual_report
    session = MagicMock()
    confront = MagicMock()
    confront.build_evidence.return_value = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "低估"}],
        "bear_evidence": [{"index": 1, "text": "风险"}],
    }
    if narrate_ok:
        confront.narrate.return_value = ConfrontationNarrateOutcome(
            result=NarrateResult(ok=True, data={"bull_thesis": "多"}, error=None),
            narrative={
                "bull_thesis": "多方",
                "bear_thesis": "空方",
                "bull_rebuttals": [],
                "bear_rebuttals": [],
                "disclaimer": "免责",
            },
            evidence_payload={},
        )
    else:
        confront.narrate.return_value = ConfrontationNarrateOutcome(
            result=NarrateResult(ok=False, data=None, error="LLM down"),
            narrative=None,
            evidence_payload={},
        )

    persona = MagicMock()
    persona.stress.return_value = PersonaStressOutcome(
        payload={
            "personas": [
                {
                    "id": "value_quality",
                    "status": "ok",
                    "output": {"lens_summary": "质量尚可"},
                }
            ],
            "disclaimer": "透镜免责",
        },
        evidence_payload={},
    )

    composer = BriefingComposer(
        dual,
        session=session,
        config={},
        confront_narrator=confront,
        persona_narrator=persona,
    )
    return composer, session, confront, persona


def test_composer_offline_pack_when_dual_ready(monkeypatch):
    composer, session, confront, persona = _composer(_report(_value(), _tech()))
    saved = MagicMock()
    saved.id = 42
    saved.declare_status = "skipped"
    saved.declaration = None

    checklist_repo = MagicMock()
    checklist_repo.list_by_code.return_value = []
    confront_repo = MagicMock()
    confront_repo.save.return_value = saved
    confront_repo.get.return_value = saved
    confront_repo.list_by_code.return_value = []

    monkeypatch.setattr(
        "service.report.briefing_composer.ChecklistRepo",
        lambda _s: checklist_repo,
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.ConfrontationRepo",
        lambda _s: confront_repo,
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.LLMNarrateCacheRepo",
        lambda _s: MagicMock(),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.EvidenceBucketer",
        lambda: MagicMock(bucket=MagicMock(return_value=MagicMock())),
    )

    view = composer.build("600519", narrate=True)
    assert view.code == "600519"
    assert view.name == "贵州茅台"
    assert view.section_statuses["value"].status == "ok"
    assert view.section_statuses["tech"].status == "ok"
    assert view.section_statuses["narrative"].status == "ok"
    assert view.section_statuses["checklist"].status == "missing"
    assert "checklist submit" in view.section_statuses["checklist"].hint
    assert view.section_statuses["declare"].status == "missing"
    assert "confront declare" in view.section_statuses["declare"].hint
    assert view.confrontation_id == 42
    assert view.fair_base == 2000.0
    assert view.value_method_rows[0]["key"] == "dcf"
    confront.narrate.assert_called_once()
    persona.stress.assert_called_once()
    session.commit.assert_called()


def test_composer_raises_when_both_value_and_tech_missing():
    tech = _tech(warnings=["无K线缓存"], risk_factors=["无K线缓存"])
    composer, *_ = _composer(_report(None, tech))
    with pytest.raises(LocalDataMissingError):
        composer.build("600519", narrate=False)


def test_composer_narrate_failure_still_returns_view(monkeypatch):
    composer, session, confront, persona = _composer(
        _report(_value(), _tech()), narrate_ok=False
    )
    saved = MagicMock()
    saved.id = 7
    saved.declare_status = "skipped"
    saved.declaration = None

    monkeypatch.setattr(
        "service.report.briefing_composer.ChecklistRepo",
        lambda _s: MagicMock(list_by_code=MagicMock(return_value=[])),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.ConfrontationRepo",
        lambda _s: MagicMock(
            save=MagicMock(return_value=saved),
            get=MagicMock(return_value=saved),
            list_by_code=MagicMock(return_value=[]),
        ),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.LLMNarrateCacheRepo",
        lambda _s: MagicMock(),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.EvidenceBucketer",
        lambda: MagicMock(bucket=MagicMock(return_value=MagicMock())),
    )

    view = composer.build("600519", narrate=True)
    assert view.section_statuses["narrative"].status == "failed"
    assert "LLM down" in view.section_statuses["narrative"].hint
    assert "report confront" in view.section_statuses["narrative"].hint
    assert view.section_statuses["core"].status == "ok"
    assert view.confrontation_id == 7


def test_composer_no_narrate_sets_missing_hints(monkeypatch):
    composer, session, confront, persona = _composer(_report(_value(), _tech()))
    saved = MagicMock()
    saved.id = 3
    saved.declare_status = "skipped"
    saved.declaration = None
    monkeypatch.setattr(
        "service.report.briefing_composer.ChecklistRepo",
        lambda _s: MagicMock(list_by_code=MagicMock(return_value=[])),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.ConfrontationRepo",
        lambda _s: MagicMock(
            save=MagicMock(return_value=saved),
            get=MagicMock(return_value=saved),
            list_by_code=MagicMock(return_value=[]),
        ),
    )
    monkeypatch.setattr(
        "service.report.briefing_composer.EvidenceBucketer",
        lambda: MagicMock(bucket=MagicMock(return_value=MagicMock())),
    )

    view = composer.build("600519", narrate=False)
    assert view.section_statuses["narrative"].status == "missing"
    assert "--no-narrate" in view.section_statuses["narrative"].hint
    assert view.section_statuses["persona"].status == "missing"
    confront.narrate.assert_not_called()
    persona.stress.assert_not_called()
