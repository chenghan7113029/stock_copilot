"""BriefingComposer：组装 BriefingView，只编排不重算。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from common.exceptions import StockCopilotError
from dao.checklist_repo import ChecklistRepo
from dao.confrontation_repo import (
    DECLARE_OK,
    NARRATE_FAILED,
    NARRATE_OK,
    NARRATE_SKIPPED,
    ConfrontationRepo,
)
from dao.kline_repo import KlineRepo
from dao.llm_narrate_cache_repo import LLMNarrateCacheRepo
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.evidence_bucketer import EvidenceBucketer
from service.guard.confrontation_narrator import ConfrontationNarrator
from service.guard.persona_stress_narrator import PersonaStressNarrator
from service.report.models.briefing_view import BriefingView, SectionStatus
from service.tech.models.tech_result import TechAnalysisResult

_PRICE_SERIES_DAYS = 10


class LocalDataMissingError(StockCopilotError):
    """价值面与技术面均无本地数据。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"未找到 {code} 的本地数据，请先运行 sync")


def _tech_has_no_cache(tech: TechAnalysisResult | None) -> bool:
    if tech is None:
        return True
    return any("无K线缓存" in w for w in tech.warnings) or any(
        "无K线缓存" in r for r in tech.risk_factors
    )


def _enum_val(obj: Any) -> str:
    if obj is None:
        return ""
    return getattr(obj, "value", str(obj))


class BriefingComposer:
    """周末深度复盘 Pack：复用双轨/对抗/Persona/Checklist，不重算数值。"""

    def __init__(
        self,
        dual: DualTrackAnalyzer,
        *,
        session: Any,
        config: dict[str, Any] | None = None,
        confront_narrator: ConfrontationNarrator | None = None,
        persona_narrator: PersonaStressNarrator | None = None,
    ) -> None:
        self._dual = dual
        self._session = session
        self._config = config or {}
        self._confront = confront_narrator or ConfrontationNarrator()
        self._persona = persona_narrator or PersonaStressNarrator()
        self._bucketer = EvidenceBucketer()

    def build(self, code: str, *, narrate: bool = True) -> BriefingView:
        report = self._dual.analyze_offline(code)
        no_value = report.value_result is None
        no_tech = _tech_has_no_cache(report.tech_result)
        if no_value and no_tech:
            raise LocalDataMissingError(code)

        buckets = self._bucketer.bucket(report)
        evidence = self._confront.build_evidence(
            buckets, code=code, analysis_summary=report.analysis_summary or ""
        )
        bull = list(evidence.get("bull_evidence") or [])
        bear = list(evidence.get("bear_evidence") or [])

        view = BriefingView(code=code)
        view.section_statuses["core"] = SectionStatus(status="ok")
        self._fill_hero(view, report, bull_count=len(bull), bear_count=len(bear))
        self._fill_value(view, report)
        self._fill_tech(view, report)
        self._fill_sentiment(view, report)
        self._fill_price_context(view, code)
        view.bull_evidence = bull
        view.bear_evidence = bear
        view.section_statuses["evidence"] = SectionStatus(status="ok")

        confrontation_id: int | None = None
        if narrate:
            confrontation_id = self._run_narrate(view, evidence, buckets, report, code)
        else:
            view.section_statuses["narrative"] = SectionStatus(
                status="missing",
                hint="未启用 LLM 叙事（使用了 --no-narrate）。需要互驳时可去掉该参数或运行："
                f"report confront {code} --narrate",
            )
            view.section_statuses["persona"] = SectionStatus(
                status="missing",
                hint="未启用 Persona 压力测试（--no-narrate）。可运行："
                f"report persona-stress {code} --narrate",
            )
            # 仍落库 Level 0 evidence，便于后续 declare
            repo = ConfrontationRepo(self._session)
            record = repo.save(
                code=code,
                evidence=evidence,
                narrate_status=NARRATE_SKIPPED,
                narrative=None,
            )
            self._session.commit()
            confrontation_id = record.id

        view.confrontation_id = confrontation_id
        self._fill_decision_trace(view, code, confrontation_id)
        return view

    def _fill_hero(
        self,
        view: BriefingView,
        report: Any,
        *,
        bull_count: int,
        bear_count: int,
    ) -> None:
        value = report.value_result
        view.name = (value.name if value and value.name else "") or ""
        view.combined_signal = _enum_val(report.combined_signal)
        view.value_rating = _enum_val(report.value_rating)
        ts = report.data_timestamp or datetime.now(timezone.utc)
        view.data_timestamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        view.conflict_summary = (
            f"综合信号「{view.combined_signal or '未知'}」，"
            f"价值评级「{view.value_rating or '未知'}」；"
            f"红蓝证据多方 {bull_count} / 空方 {bear_count}"
        )
        if report.analysis_summary:
            view.warnings.append(report.analysis_summary)

    def _fill_value(self, view: BriefingView, report: Any) -> None:
        value = report.value_result
        if value is None:
            view.section_statuses["value"] = SectionStatus(
                status="missing",
                hint="价值面无本地快照，请先运行 sync",
            )
            return
        view.section_statuses["value"] = SectionStatus(status="ok")
        view.current_price = value.current_price
        view.value_assessment = value.assessment or ""
        view.value_prototype = value.prototype or ""
        view.value_confidence = str(value.confidence or "")
        view.margin_of_safety = value.margin_of_safety
        if value.fair_value_range is not None:
            r = value.fair_value_range
            view.fair_low = float(r.low)
            view.fair_base = float(r.base)
            view.fair_high = float(r.high)
        view.value_warnings = list(value.warnings or [])
        rows: list[dict[str, Any]] = []
        for key, item in (value.method_results or {}).items():
            rows.append(
                {
                    "key": key,
                    "method": getattr(item, "method", key),
                    "fair_value": getattr(item, "fair_value", None),
                    "label": getattr(item, "assessment", "") or "",
                    "applicable": getattr(item, "applicability", None),
                }
            )
        view.value_method_rows = rows[:24]

    def _fill_tech(self, view: BriefingView, report: Any) -> None:
        tech = report.tech_result
        if _tech_has_no_cache(tech):
            view.section_statuses["tech"] = SectionStatus(
                status="missing",
                hint="技术面无 K 线缓存，请先运行 sync",
            )
            return
        assert tech is not None
        view.section_statuses["tech"] = SectionStatus(status="ok")
        view.tech_score = int(tech.signal_score) if tech.signal_score is not None else None
        view.tech_trend = _enum_val(tech.trend_status)
        view.tech_signal = _enum_val(tech.buy_signal)
        view.tech_price = tech.current_price
        view.tech_reasons = list(tech.signal_reasons or [])[:12]
        view.tech_risks = [r for r in (tech.risk_factors or []) if "无K线缓存" not in r][:12]
        view.boll_mid = getattr(tech, "boll_mid", None) or None
        view.boll_upper = getattr(tech, "boll_upper", None) or None
        view.boll_lower = getattr(tech, "boll_lower", None) or None
        view.boll_bandwidth = getattr(tech, "boll_bandwidth", None) or None
        view.boll_percentile = getattr(tech, "boll_percentile", None)
        view.boll_status = _enum_val(getattr(tech, "boll_status", None))
        patterns = []
        for p in getattr(tech, "candlestick_patterns", None) or []:
            patterns.append(
                {
                    "pattern": _enum_val(getattr(p, "pattern", None)),
                    "direction": getattr(p, "direction", ""),
                    "trade_date": getattr(p, "trade_date", ""),
                    "description": getattr(p, "description", ""),
                }
            )
        view.candlestick_patterns = patterns

    def _fill_price_context(self, view: BriefingView, code: str) -> None:
        rows = KlineRepo(self._session).list_by_code(code)
        series: list[dict[str, Any]] = []
        for row in rows:
            close = row.get("close")
            if close is None:
                continue
            try:
                close_f = float(close)
            except (TypeError, ValueError):
                continue
            date = str(row.get("trade_date") or row.get("date") or "")
            series.append({"date": date, "close": close_f})
        if not series:
            view.section_statuses["price_context"] = SectionStatus(
                status="missing",
                hint="无本地 K 线收盘序列，价格情境不可用。请先运行 sync",
            )
            return
        recent = series[-_PRICE_SERIES_DAYS:]
        view.price_series = recent
        closes = [p["close"] for p in recent]
        view.price_high = max(closes)
        view.price_low = min(closes)
        if view.current_price is None and recent:
            view.current_price = recent[-1]["close"]
        if len(recent) < _PRICE_SERIES_DAYS:
            view.section_statuses["price_context"] = SectionStatus(
                status="ok",
                hint=f"K 线不足 {_PRICE_SERIES_DAYS} 个交易日（当前 {len(recent)}），已按可得数据绘制。可 sync 补齐",
            )
        else:
            view.section_statuses["price_context"] = SectionStatus(status="ok")

    def _fill_sentiment(self, view: BriefingView, report: Any) -> None:
        sent = report.sentiment_result
        if sent is None or sent.market_sentiment_score is None:
            view.section_statuses["sentiment"] = SectionStatus(
                status="missing",
                hint="情绪面数据缺失，请先运行 sync market",
            )
            view.sentiment_note = "情绪面数据缺失"
            return
        view.section_statuses["sentiment"] = SectionStatus(status="ok")
        view.sentiment_score = float(sent.market_sentiment_score)
        view.sentiment_status = _enum_val(sent.market_sentiment_status)
        view.sentiment_note = "；".join(sent.reasons[:3]) if sent.reasons else ""

    def _run_narrate(
        self,
        view: BriefingView,
        evidence: dict[str, Any],
        buckets: Any,
        report: Any,
        code: str,
    ) -> int | None:
        cache = LLMNarrateCacheRepo(self._session)
        narrate_status = NARRATE_SKIPPED
        narrative: dict[str, Any] | None = None
        try:
            outcome = self._confront.narrate(
                buckets,
                code=code,
                analysis_summary=report.analysis_summary or "",
                config=self._config,
                cache=cache,
            )
            if outcome.result.ok and outcome.narrative is not None:
                narrate_status = NARRATE_OK
                narrative = outcome.narrative
                view.narrative = narrative
                view.section_statuses["narrative"] = SectionStatus(status="ok")
            else:
                narrate_status = NARRATE_FAILED
                err = outcome.result.error or "LLM 互驳叙事失败"
                view.section_statuses["narrative"] = SectionStatus(
                    status="failed",
                    hint=f"互驳叙事失败：{err}。可检查 llm: / LLM_API_KEY 后重试："
                    f"report confront {code} --narrate",
                )
        except Exception as exc:  # noqa: BLE001
            narrate_status = NARRATE_FAILED
            view.section_statuses["narrative"] = SectionStatus(
                status="failed",
                hint=f"互驳叙事失败：{exc}。可重试：report confront {code} --narrate",
            )

        persona_payload: dict[str, Any] | None = None
        try:
            stress = self._persona.stress(
                evidence, config=self._config, cache=cache
            )
            persona_payload = stress.payload
            view.persona_stress = persona_payload
            personas = persona_payload.get("personas") or []
            failed = [p for p in personas if p.get("status") == "failed"]
            if not personas:
                view.section_statuses["persona"] = SectionStatus(
                    status="failed",
                    hint=f"Persona 压力测试失败：无结果。可重试：report persona-stress {code} --narrate",
                )
            elif len(failed) == len(personas):
                view.section_statuses["persona"] = SectionStatus(
                    status="failed",
                    hint="Persona 压力测试全部失败。请检查 LLM 配置后运行："
                    f"report persona-stress {code} --narrate",
                )
            elif failed:
                view.section_statuses["persona"] = SectionStatus(
                    status="ok",
                    hint=f"部分 Persona 失败（{len(failed)}/{len(personas)}），请对照证据阅读。",
                )
            else:
                view.section_statuses["persona"] = SectionStatus(status="ok")
        except Exception as exc:  # noqa: BLE001
            view.section_statuses["persona"] = SectionStatus(
                status="failed",
                hint=f"Persona 压力测试失败：{exc}。可重试："
                f"report persona-stress {code} --narrate",
            )

        repo = ConfrontationRepo(self._session)
        record = repo.save(
            code=code,
            evidence=evidence,
            narrate_status=narrate_status,
            narrative=narrative,
            persona_stress=persona_payload,
        )
        self._session.commit()
        return record.id

    def _fill_decision_trace(
        self, view: BriefingView, code: str, confrontation_id: int | None
    ) -> None:
        checklists = ChecklistRepo(self._session).list_by_code(code)
        if not checklists:
            view.section_statuses["checklist"] = SectionStatus(
                status="missing",
                hint=f"尚未提交 Checklist。可运行：checklist submit {code}",
            )
            view.checklist_summary = ""
        else:
            latest = checklists[0]
            passed = getattr(latest, "passed", None)
            action = getattr(latest, "action", "") or ""
            view.checklist_summary = (
                f"最近 Checklist：action={action} passed={passed} "
                f"id={getattr(latest, 'id', '?')}"
            )
            view.section_statuses["checklist"] = SectionStatus(status="ok")

        declare_found = False
        declare_text = ""
        if confrontation_id is not None:
            record = ConfrontationRepo(self._session).get(confrontation_id)
            if (
                record is not None
                and record.declare_status == DECLARE_OK
                and record.declaration
            ):
                declare_found = True
                stance = record.declaration.get("stance", "")
                declare_text = f"confrontation_id={confrontation_id} stance={stance}"
        if not declare_found:
            # 回退：该票历史是否有 declare
            for rec in ConfrontationRepo(self._session).list_by_code(code):
                if rec.declare_status == DECLARE_OK and rec.declaration:
                    declare_found = True
                    declare_text = (
                        f"历史 declare：confrontation_id={rec.id} "
                        f"stance={rec.declaration.get('stance', '')}"
                    )
                    break
        if declare_found:
            view.declare_summary = declare_text
            view.section_statuses["declare"] = SectionStatus(status="ok")
        else:
            cid = confrontation_id if confrontation_id is not None else "<id>"
            view.section_statuses["declare"] = SectionStatus(
                status="missing",
                hint=f"尚未 declare。可读完证据后运行：confront declare {cid}",
            )
            view.declare_summary = ""
