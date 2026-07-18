"""从 DualTrackReport 确定性分桶多空证据（零 LLM）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from service.dual_track.models.report import DualTrackReport, ValueRating
from service.tech.models.tech_result import TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationResult

_BULL_KEYWORDS = ("低估", "undervalued", "attractive", "cheap", "优秀", "healthy", "excellent")
_BEAR_KEYWORDS = (
    "高估",
    "overvalued",
    "expensive",
    "weak",
    "poor",
    "fraud",
    "distress",
    "bankruptcy",
)
_WARNING_BEAR_KEYWORDS = ("风险", "不可信", "limited", "缺失", "不足")

# 方法论局限文案：不含个股具体数值断言
_PROTOTYPE_VULNERABILITIES: dict[str, list[str]] = {
    "value_growth": [
        "[假设脆弱性] DCF/成长估值依赖增长率与折现率假设，假设偏离会导致公允价区间大幅偏移",
        "[假设脆弱性] 成长股估值对远期现金流敏感，短期业绩波动可能削弱模型可信度",
    ],
    "high_dividend": [
        "[假设脆弱性] 股息折现模型依赖分红可持续性假设，分红政策变化会削弱 DDM 结论",
        "[假设脆弱性] 高股息策略对利率环境敏感，利率上行可能压缩估值吸引力",
    ],
    "bank": [
        "[假设脆弱性] 银行股通常排除 DCF，依赖 PB/ROE、净息差等银行专用指标，指标口径变化会影响结论",
        "[假设脆弱性] 银行估值受信贷周期与资产质量影响，周期拐点处历史倍数可能失效",
    ],
    "unknown": [
        "[假设脆弱性] 原型未识别时使用通用方法集，方法适用性不确定，结论置信度偏低",
        "[假设脆弱性] 通用估值假设可能与行业特征不匹配，需额外核对关键输入字段完整性",
    ],
}

_TREND_VULNERABILITY = (
    "[假设脆弱性] 技术面单边强势/弱势状态可能钝化，趋势反转时均线与动量信号会滞后"
)

_MIN_EVIDENCE = 2


@dataclass(frozen=True)
class EvidenceBuckets:
    bull_evidence: list[str]
    bear_evidence: list[str]


class EvidenceBucketer:
    """按既有确定性字段分桶，不重新计算、不调用 LLM。"""

    def bucket(self, report: DualTrackReport) -> EvidenceBuckets:
        bull: list[str] = []
        bear: list[str] = []

        if report.value_rating == ValueRating.UNDERVALUED:
            bull.append(f"[价值评级] {ValueRating.UNDERVALUED.value}")
        elif report.value_rating == ValueRating.OVERVALUED:
            bear.append(f"[价值评级] {ValueRating.OVERVALUED.value}")

        if report.value_result is not None:
            self._bucket_value(report.value_result, bull, bear)

        if report.tech_result is not None:
            for reason in report.tech_result.signal_reasons:
                text = reason.strip()
                if text:
                    bull.append(f"[技术信号] {text}")
            for risk in report.tech_result.risk_factors:
                text = risk.strip()
                if text and "无缓存" not in text:
                    bear.append(f"[技术风险] {text}")

        prototype = (
            report.value_result.prototype if report.value_result is not None else "unknown"
        )
        self._apply_fallback(bull, bear, prototype, report)

        return EvidenceBuckets(bull_evidence=bull, bear_evidence=bear)

    def _bucket_value(
        self,
        value_result: ValueAnalysisResult,
        bull: list[str],
        bear: list[str],
    ) -> None:
        for key, result in value_result.method_results.items():
            self._bucket_method(key, result, bull, bear)

        for warning in value_result.warnings:
            text = warning.strip()
            if not text:
                continue
            lower = text.lower()
            if any(k in lower or k in text for k in _WARNING_BEAR_KEYWORDS):
                bear.append(f"[价值警告] {text}")

    def _bucket_method(
        self,
        key: str,
        result: ValuationResult,
        bull: list[str],
        bear: list[str],
    ) -> None:
        details = result.details or {}
        if key == "value_trap" or "overall_risk" in details:
            risk = str(details.get("overall_risk", "")).strip()
            if risk in {"Medium", "High"}:
                bear.append(
                    f"[价值陷阱] {result.method or key}: overall_risk={risk}"
                    + (f", {result.assessment}" if result.assessment else "")
                )
                return
            if risk == "Low":
                bull.append(f"[价值陷阱] {result.method or key}: overall_risk=Low（风险可控）")
                return

        assessment = (result.assessment or "").strip()
        if not assessment:
            return

        lower = assessment.lower()
        label = f"[估值-{result.method or key}] {assessment}"
        if any(k in lower or k in assessment for k in _BULL_KEYWORDS):
            bull.append(label)
        elif any(k in lower or k in assessment for k in _BEAR_KEYWORDS):
            bear.append(label)

    def _apply_fallback(
        self,
        bull: list[str],
        bear: list[str],
        prototype: str,
        report: DualTrackReport,
    ) -> None:
        vulns = list(_PROTOTYPE_VULNERABILITIES.get(prototype, _PROTOTYPE_VULNERABILITIES["unknown"]))

        if report.tech_result is not None and report.tech_result.trend_status in {
            TrendStatus.STRONG_BULL,
            TrendStatus.STRONG_BEAR,
        }:
            vulns.append(_TREND_VULNERABILITY)

        if len(bull) < _MIN_EVIDENCE:
            # 多方证据不足：追加空方假设脆弱性，给多方「攻击对方假设」的材料
            for item in vulns:
                if item not in bull:
                    bull.append(item)
                if len(bull) >= _MIN_EVIDENCE:
                    break

        if len(bear) < _MIN_EVIDENCE:
            for item in vulns:
                if item not in bear:
                    bear.append(item)
                if len(bear) >= _MIN_EVIDENCE:
                    break


def strip_numeric_assertions(text: str) -> bool:
    """启发式：兜底文案不应含针对个股的具体数字断言（单测辅助）。"""
    return not bool(re.search(r"\d+(\.\d+)?%?", text))
