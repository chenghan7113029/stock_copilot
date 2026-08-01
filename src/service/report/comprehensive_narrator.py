"""LLM 综合报告：ContextPack + narrate() 封装。"""

from __future__ import annotations

from typing import Any

from common.llm.client import LLMClient
from common.llm.models import NarrateResult
from common.llm.narrator import NarrateCache, narrate
from service.dual_track.models.report import DualTrackReport
from service.report.context_pack import build_dual_track_evidence

COMPREHENSIVE_REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "key_points", "risks", "confidence"],
    "properties": {
        "summary": {
            "type": "string",
            "description": "一段综合叙述，概括价值面与技术面要点",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "关键要点列表",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "风险提示列表",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "模型对本次叙述的置信度",
        },
    },
}

COMPREHENSIVE_REPORT_INSTRUCTION = (
    "请基于给定 evidence 生成一份股票综合分析叙事报告。"
    "输出必须包含：summary（综合叙述）、key_points（关键要点数组）、"
    "risks（风险提示数组）、confidence（0-1）。"
    "只能基于给定 evidence 中的数值与结论组织叙述，"
    "不得引入 evidence 之外的任何新数字、新百分比、新结论；"
    "若 evidence 不足以支撑某个论断，应明确说明信息不足，而非猜测。"
    "不得使用 evidence 中未出现的具体价格、比率或评分数字。"
)


def narrate_comprehensive_report(
    report: DualTrackReport,
    *,
    config: dict[str, Any] | None = None,
    client: LLMClient | None = None,
    cache: NarrateCache | None = None,
    force_refresh: bool = False,
) -> NarrateResult:
    """将 DualTrackReport 打包为 evidence 并调用 narrate()。"""
    evidence = build_dual_track_evidence(report)
    return narrate(
        evidence,
        COMPREHENSIVE_REPORT_SCHEMA,
        COMPREHENSIVE_REPORT_INSTRUCTION,
        config=config,
        client=client,
        cache=cache,
        force_refresh=force_refresh,
    )
