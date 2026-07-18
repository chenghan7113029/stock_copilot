"""双轨分析 Facade：价值面 + 技术面编排。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from common.exceptions import UnsupportedMarketError
from data_provider.base import is_a_share
from service.dual_track.config import DualTrackConfig
from service.dual_track.models.report import DualTrackReport, ValueRating
from service.dual_track.signal_fusion import SignalFusion
from service.tech.analyzer import TechAnalyzer
from service.tech.models.tech_result import TechAnalysisResult
from service.value.analyzer import ValueAnalyzer
from service.value.models.analysis_result import ValueAnalysisResult


def build_analysis_summary(
    code: str,
    value_result: ValueAnalysisResult | None,
    tech_result: TechAnalysisResult | None,
    combined_signal: str,
    value_rating: ValueRating | None,
) -> str:
    parts: list[str] = [f"股票代码: {code}"]

    if value_result is not None:
        if value_result.fair_value_range is not None:
            r = value_result.fair_value_range
            parts.append(
                f"价值面: 公允价区间 [{r.low:.2f}, {r.base:.2f}, {r.high:.2f}]"
            )
        if value_result.margin_of_safety is not None:
            parts.append(f"安全边际: {value_result.margin_of_safety:.1%}")

    if tech_result is not None:
        parts.append(
            f"技术面: {tech_result.trend_status.value}, 评分 {tech_result.signal_score}"
        )

    parts.append(f"综合信号: {combined_signal}")
    if value_rating is not None:
        parts.append(f"价值评级: {value_rating.value}")

    return " | ".join(parts)


class DualTrackAnalyzer:
    """双轨分析单一入口。"""

    def __init__(
        self,
        value_analyzer: ValueAnalyzer,
        tech_analyzer: TechAnalyzer,
        config: DualTrackConfig | None = None,
        signal_fusion: SignalFusion | None = None,
    ) -> None:
        self._value_analyzer = value_analyzer
        self._tech_analyzer = tech_analyzer
        self._config = config or DualTrackConfig()
        self._signal_fusion = signal_fusion or SignalFusion(self._config)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DualTrackAnalyzer":
        return cls(
            value_analyzer=ValueAnalyzer.from_config(config),
            tech_analyzer=TechAnalyzer.from_config(config),
            config=DualTrackConfig(),
        )

    def analyze(self, raw_code: str) -> DualTrackReport:
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code = raw_code.strip()
        warnings: list[str] = []
        value_result: ValueAnalysisResult | None = None
        tech_result: TechAnalysisResult | None = None

        try:
            value_result = self._value_analyzer.analyze(code)
            warnings.extend(value_result.warnings)
        except UnsupportedMarketError:
            raise
        except Exception as exc:
            warnings.append(f"价值面分析失败: {exc}")

        try:
            tech_result = self._tech_analyzer.analyze(code)
            warnings.extend(tech_result.warnings)
        except UnsupportedMarketError:
            raise
        except Exception as exc:
            warnings.append(f"技术面分析失败: {exc}")

        combined_signal, value_rating = self._signal_fusion.fuse(
            value_result, tech_result
        )

        analysis_summary = build_analysis_summary(
            code,
            value_result,
            tech_result,
            combined_signal.value,
            value_rating,
        )

        data_timestamp = datetime.now(timezone.utc)
        if value_result and value_result.data_timestamp:
            data_timestamp = value_result.data_timestamp
        elif tech_result and tech_result.data_timestamp:
            data_timestamp = tech_result.data_timestamp

        return DualTrackReport(
            code=code,
            value_result=value_result,
            tech_result=tech_result,
            combined_signal=combined_signal,
            value_rating=value_rating,
            analysis_summary=analysis_summary,
            warnings=warnings,
            data_timestamp=data_timestamp,
        )

    def analyze_offline(self, raw_code: str) -> DualTrackReport:
        """离线双轨分析：不发起任何网络请求。"""
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code = raw_code.strip()
        warnings: list[str] = []
        value_result: ValueAnalysisResult | None = None
        tech_result: TechAnalysisResult | None = None

        try:
            value_result = self._value_analyzer.analyze_offline(code)
            if value_result is None:
                warnings.append("价值面无本地快照，请先运行 sync")
            else:
                warnings.extend(value_result.warnings)
        except UnsupportedMarketError:
            raise
        except Exception as exc:
            warnings.append(f"价值面分析失败: {exc}")

        try:
            tech_result = self._tech_analyzer.analyze(code, offline=True)
            warnings.extend(tech_result.warnings)
        except UnsupportedMarketError:
            raise
        except Exception as exc:
            warnings.append(f"技术面分析失败: {exc}")

        combined_signal, value_rating = self._signal_fusion.fuse(
            value_result, tech_result
        )

        analysis_summary = build_analysis_summary(
            code,
            value_result,
            tech_result,
            combined_signal.value,
            value_rating,
        )

        data_timestamp = datetime.now(timezone.utc)
        if value_result and value_result.data_timestamp:
            data_timestamp = value_result.data_timestamp
        elif tech_result and tech_result.data_timestamp:
            data_timestamp = tech_result.data_timestamp

        return DualTrackReport(
            code=code,
            value_result=value_result,
            tech_result=tech_result,
            combined_signal=combined_signal,
            value_rating=value_rating,
            analysis_summary=analysis_summary,
            warnings=warnings,
            data_timestamp=data_timestamp,
        )
