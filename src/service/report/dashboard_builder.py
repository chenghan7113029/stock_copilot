"""单票多维看板聚合：只读复用 DualTrackAnalyzer + EvidenceBucketer。"""

from __future__ import annotations

from typing import Any

from common.exceptions import StockCopilotError
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.evidence_bucketer import EvidenceBucketer
from service.dual_track.models.report import DualTrackReport
from service.report.models.dashboard_view import DashboardView
from service.tech.analyzer import TechAnalyzer
from service.tech.models.tech_result import TechAnalysisResult
from service.value.analyzer import ValueAnalyzer
from service.value.models.analysis_result import ValueAnalysisResult

_SENTIMENT_PLACEHOLDER = "情绪面待建（见 PO-06）"
_CHECKLIST_PLACEHOLDER = "Checklist 待建（见 PO-04）"
_NO_VALUE_HINT = "无本地快照，请先运行 sync"
_NO_TECH_HINT = "无本地快照，请先运行 sync"


class LocalDataMissingError(StockCopilotError):
    """价值面与技术面均无本地数据时抛出。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"未找到 {code} 的本地数据，请先运行 sync")


def _tech_has_no_cache(tech: TechAnalysisResult | None) -> bool:
    if tech is None:
        return True
    return any("无缓存" in w for w in tech.warnings) or any(
        "无缓存" in r for r in tech.risk_factors
    )


def _format_value_section(value: ValueAnalysisResult | None) -> str:
    if value is None:
        return _NO_VALUE_HINT
    lines = [
        f"名称: {value.name or 'N/A'}",
        f"原型: {value.prototype}",
        f"现价: {value.current_price if value.current_price is not None else 'N/A'}",
        f"评估: {value.assessment}",
        f"置信度: {value.confidence}",
    ]
    if value.fair_value_range is not None:
        r = value.fair_value_range
        lines.append(f"公允价区间: {r.low:.2f} ~ {r.base:.2f} ~ {r.high:.2f}")
    if value.margin_of_safety is not None:
        lines.append(f"安全边际: {value.margin_of_safety:.1%}")
    return "\n".join(lines)


def _format_tech_section(tech: TechAnalysisResult | None) -> str:
    if _tech_has_no_cache(tech):
        return _NO_TECH_HINT
    assert tech is not None
    lines = [
        f"趋势: {tech.trend_status.value}",
        f"信号: {tech.buy_signal.value}",
        f"评分: {tech.signal_score}",
        f"现价: {tech.current_price}",
    ]
    if tech.signal_reasons:
        lines.append("信号理由: " + "；".join(tech.signal_reasons[:3]))
    if tech.risk_factors:
        # 过滤无缓存类提示（已作为整体缺失处理）
        risks = [r for r in tech.risk_factors if "无缓存" not in r][:3]
        if risks:
            lines.append("风险: " + "；".join(risks))
    return "\n".join(lines)


def _format_combined_summary(
    report: DualTrackReport,
    bull_count: int,
    bear_count: int,
) -> str:
    parts: list[str] = []
    if report.analysis_summary:
        parts.append(report.analysis_summary)
    else:
        if report.combined_signal is not None:
            parts.append(f"综合信号: {report.combined_signal.value}")
        if report.value_rating is not None:
            parts.append(f"价值评级: {report.value_rating.value}")
    parts.append(
        f"红蓝证据: 多方 {bull_count} 条 / 空方 {bear_count} 条"
        "（详见 report dual 或 red-blue-confrontation Skill）"
    )
    return " | ".join(parts)


class DashboardBuilder:
    """看板聚合 Facade：只做展示态编排，不重新计算数值。"""

    def __init__(
        self,
        value_analyzer: ValueAnalyzer,
        tech_analyzer: TechAnalyzer,
        config: dict[str, Any] | None = None,
        *,
        dual_analyzer: DualTrackAnalyzer | None = None,
        bucketer: EvidenceBucketer | None = None,
    ) -> None:
        self._config = config or {}
        self._dual = dual_analyzer or DualTrackAnalyzer(value_analyzer, tech_analyzer)
        self._bucketer = bucketer or EvidenceBucketer()

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        value_analyzer: ValueAnalyzer | None = None,
        tech_analyzer: TechAnalyzer | None = None,
    ) -> "DashboardBuilder":
        value = value_analyzer or ValueAnalyzer.from_config(config)
        tech = tech_analyzer or TechAnalyzer.from_config(config)
        return cls(value, tech, config=config)

    def build(self, code: str) -> DashboardView:
        report = self._dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = _tech_has_no_cache(report.tech_result)
        if no_value and no_tech:
            raise LocalDataMissingError(code)

        buckets = self._bucketer.bucket(report)

        return DashboardView(
            code=code,
            value_section=_format_value_section(report.value_result),
            tech_section=_format_tech_section(report.tech_result),
            sentiment_section=_SENTIMENT_PLACEHOLDER,
            checklist_section=_CHECKLIST_PLACEHOLDER,
            combined_summary=_format_combined_summary(
                report,
                len(buckets.bull_evidence),
                len(buckets.bear_evidence),
            ),
            warnings=list(report.warnings),
        )
