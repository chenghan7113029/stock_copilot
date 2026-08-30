"""双轨分析 Facade：价值面 + 技术面编排。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from common.exceptions import UnsupportedMarketError
from data_provider.base import is_a_share
from service.dual_track.config import DualTrackConfig
from service.dual_track.models.report import DualTrackReport, ValueRating
from service.dual_track.signal_fusion import SignalFusion
from service.sentiment.analyzer import SentimentAnalyzer
from service.sentiment.models.sentiment_result import SentimentAnalysisResult, SentimentStatus
from service.tech.analyzer import TechAnalyzer
from service.tech.models.tech_result import TechAnalysisResult
from service.report.explainers import format_mos_percent_points
from service.value.analyzer import ValueAnalyzer
from service.value.models.analysis_result import ValueAnalysisResult


def build_analysis_summary(
    code: str,
    value_result: ValueAnalysisResult | None,
    tech_result: TechAnalysisResult | None,
    combined_signal: str,
    value_rating: ValueRating | None,
    sentiment_result: SentimentAnalysisResult | None = None,
) -> str:
    parts: list[str] = [f"股票代码: {code}"]
    if value_result is not None and value_result.name:
        parts.append(f"名称: {value_result.name}")

    if value_result is not None:
        if value_result.fair_value_range is not None:
            r = value_result.fair_value_range
            parts.append(
                f"价值面: 公允价区间 [{r.low:.2f}, {r.base:.2f}, {r.high:.2f}]"
            )
        if value_result.margin_of_safety is not None:
            parts.append(
                f"安全边际: {format_mos_percent_points(value_result.margin_of_safety)}"
            )

    if tech_result is not None:
        parts.append(
            f"技术面: {tech_result.trend_status.value}, 评分 {tech_result.signal_score}"
        )

    if sentiment_result is None:
        parts.append("情绪面数据缺失，本次报告仅基于价值+技术双维")
    else:
        status = sentiment_result.market_sentiment_status
        score = sentiment_result.market_sentiment_score
        if (
            status == SentimentStatus.EXTREME_GREED
            and tech_result is not None
            and tech_result.trend_status.value == "强势多头"
        ):
            parts.append("情绪面极度贪婪叠加技术面强势，注意钝化与回调风险，不建议仅因情绪指标追高")
        elif (
            status == SentimentStatus.EXTREME_FEAR
            and value_result is not None
            and value_result.assessment == "低估"
        ):
            parts.append("市场极度恐慌但价值面显示低估，符合逆向逻辑，但仍需技术面企稳信号确认")
        else:
            label = status.value if status is not None else "数据不足"
            score_text = f"{score:.1f}" if score is not None else "N/A"
            assessment = value_result.assessment if value_result is not None else "缺失"
            trend = tech_result.trend_status.value if tech_result is not None else "缺失"
            parts.append(
                f"情绪面: {label}（指数 {score_text}），须结合价值面「{assessment}」"
                f"与技术面「{trend}」综合判断，不单独作为买卖依据"
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
        sentiment_analyzer: SentimentAnalyzer | None = None,
    ) -> None:
        self._value_analyzer = value_analyzer
        self._tech_analyzer = tech_analyzer
        self._config = config or DualTrackConfig()
        self._signal_fusion = signal_fusion or SignalFusion(self._config)
        self._sentiment_analyzer = sentiment_analyzer

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DualTrackAnalyzer":
        return cls(
            value_analyzer=ValueAnalyzer.from_config(config),
            tech_analyzer=TechAnalyzer.from_config(config),
            config=DualTrackConfig(),
            sentiment_analyzer=SentimentAnalyzer.from_config(config),
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
        sentiment_result: SentimentAnalysisResult | None = None

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

        if self._sentiment_analyzer is not None:
            try:
                sentiment_result = self._sentiment_analyzer.analyze(code)
                warnings.extend(sentiment_result.warnings)
            except Exception as exc:
                warnings.append(f"情绪面分析失败: {exc}")

        combined_signal, value_rating = self._signal_fusion.fuse(
            value_result, tech_result
        )

        analysis_summary = build_analysis_summary(
            code,
            value_result,
            tech_result,
            combined_signal.value,
            value_rating,
            sentiment_result,
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
            sentiment_result=sentiment_result,
            combined_signal=combined_signal,
            value_rating=value_rating,
            analysis_summary=analysis_summary,
            warnings=warnings,
            data_timestamp=data_timestamp,
        )

    def analyze_offline(
        self,
        raw_code: str,
        *,
        as_of: date | str | None = None,
    ) -> DualTrackReport:
        """离线双轨分析：不发起任何网络请求。

        ``as_of`` 仅影响技术面 K 线窗口（与 migration baseline 一致）；
        value/sentiment 离线读快照，不依赖墙钟 ``date.today()``。
        """
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code = raw_code.strip()
        warnings: list[str] = []
        value_result: ValueAnalysisResult | None = None
        tech_result: TechAnalysisResult | None = None
        sentiment_result: SentimentAnalysisResult | None = None

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
            tech_result = self._tech_analyzer.analyze(code, offline=True, as_of=as_of)
            warnings.extend(tech_result.warnings)
        except UnsupportedMarketError:
            raise
        except Exception as exc:
            warnings.append(f"技术面分析失败: {exc}")

        if self._sentiment_analyzer is not None:
            try:
                sentiment_result = self._sentiment_analyzer.analyze_offline(code)
                if sentiment_result is None:
                    warnings.append("情绪面无本地快照，请先运行 sync market")
                else:
                    warnings.extend(sentiment_result.warnings)
            except Exception as exc:
                warnings.append(f"情绪面分析失败: {exc}")

        combined_signal, value_rating = self._signal_fusion.fuse(
            value_result, tech_result
        )

        analysis_summary = build_analysis_summary(
            code,
            value_result,
            tech_result,
            combined_signal.value,
            value_rating,
            sentiment_result,
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
            sentiment_result=sentiment_result,
            combined_signal=combined_signal,
            value_rating=value_rating,
            analysis_summary=analysis_summary,
            warnings=warnings,
            data_timestamp=data_timestamp,
        )
