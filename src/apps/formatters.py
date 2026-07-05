"""CLI 报告格式化：TechAnalysisResult / ValueAnalysisResult → text 或 JSON。"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from service.tech.models.tech_result import TechAnalysisResult
from service.value.models.analysis_result import ValueAnalysisResult


def _fmt_num(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}"


def _to_json_serializable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_serializable(v) for v in obj]
    if dataclasses.is_dataclass(obj):
        return {
            f.name: _to_json_serializable(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
        }
    return obj


def _dump_json(obj: Any) -> str:
    return json.dumps(_to_json_serializable(obj), ensure_ascii=False, indent=2)


def format_tech_report(result: TechAnalysisResult, as_json: bool = False) -> str:
    if as_json:
        return _dump_json(result)

    lines: list[str] = [
        f"=== 技术面分析报告 {result.code} ===",
        f"[离线模式] K线末行: {_kline_last_date(result)} | quote_mode: {result.quote_mode}",
        "",
        f"综合评分: {result.signal_score if result.signal_score is not None else 'N/A'}",
        f"信号: {result.buy_signal.value}",
        f"趋势: {result.trend_status.value} ({result.ma_alignment})",
    ]

    if result.weekly_trend_status is not None:
        lines.append(f"周线: {result.weekly_trend_status.value} ({result.weekly_ma_alignment})")

    lines.extend(
        [
            "",
            "--- 均线 ---",
            f"MA5={_fmt_num(result.ma5)} MA10={_fmt_num(result.ma10)} "
            f"MA20={_fmt_num(result.ma20)} MA60={_fmt_num(result.ma60)}",
            f"现价: {_fmt_num(result.current_price)}",
            "",
            "--- 指标 ---",
            f"MACD: {result.macd_status.value} | {result.macd_signal}",
            f"RSI(6/12/24): {_fmt_num(result.rsi_6)}/{_fmt_num(result.rsi_12)}/{_fmt_num(result.rsi_24)} "
            f"({result.rsi_status.value})",
            f"KDJ: K={_fmt_num(result.kdj_k)} D={_fmt_num(result.kdj_d)} J={_fmt_num(result.kdj_j)} "
            f"({result.kdj_status.value})",
            f"量能: {result.volume_status.value} (5日量比 {_fmt_num(result.volume_ratio_5d)})",
            f"Bias: MA5={_fmt_num(result.bias_ma5)}% MA10={_fmt_num(result.bias_ma10)}% "
            f"MA20={_fmt_num(result.bias_ma20)}%",
        ]
    )

    if result.support_levels or result.resistance_levels:
        lines.extend(
            [
                "",
                "--- 支撑/压力 ---",
                f"支撑: {', '.join(_fmt_num(x) for x in result.support_levels) or 'N/A'}",
                f"压力: {', '.join(_fmt_num(x) for x in result.resistance_levels) or 'N/A'}",
            ]
        )

    if result.signal_reasons:
        lines.extend(["", "--- 信号理由 ---", *result.signal_reasons])

    if result.risk_factors:
        lines.extend(["", "--- 风险 ---", *result.risk_factors])

    if result.warnings:
        lines.extend(["", "--- 警告 ---", *result.warnings])

    return "\n".join(lines)


def _method_semantic_hint(key: str, mr: Any) -> str:
    """DCF/EPV 方法行的语义提示（EPV=地板价，DCF=含增长假设）。"""
    details = getattr(mr, "details", None) or {}
    if key == "dcf":
        g1 = details.get("growth_1_5")
        if g1 is not None:
            return f"(含增长假设：g₁={g1:.1f}% 5年)"
        return "(含增长假设)"
    if key == "epv":
        return "(零增长地板价)"
    return ""


def format_value_report(result: ValueAnalysisResult, as_json: bool = False) -> str:
    if as_json:
        return _dump_json(result)

    ts = "N/A"
    if result.data_timestamp:
        ts = result.data_timestamp.strftime("%Y-%m-%d %H:%M")

    lines: list[str] = [
        f"=== 价值面分析报告 {result.code} ===",
        f"[离线模式] 价值快照: {ts}",
        "",
        f"名称: {result.name or 'N/A'}",
        f"原型: {result.prototype}",
        f"现价: {_fmt_num(result.current_price)}",
        f"评估: {result.assessment}",
        f"置信度: {result.confidence}",
    ]

    if result.fair_value_range:
        r = result.fair_value_range
        lines.extend(
            [
                "",
                "--- 估值 ---",
                f"公允价区间: {_fmt_num(r.low)} ~ {_fmt_num(r.base)} ~ {_fmt_num(r.high)}",
            ]
        )

    if result.margin_of_safety is not None:
        lines.append(f"安全边际: {result.margin_of_safety:.1f}%")

    if result.price_percentile is not None:
        lines.append(f"价格分位: {result.price_percentile:.1f}%")

    if result.method_results:
        lines.extend(["", "--- 估值方法 ---"])
        for key, mr in result.method_results.items():
            fv = _fmt_num(mr.fair_value) if mr.fair_value else "N/A"
            hint = _method_semantic_hint(key, mr)
            line = f"  {key}: 公允价={fv} | {mr.assessment} ({mr.applicability})"
            if hint:
                line = f"{line} {hint}"
            lines.append(line)

    if result.warnings:
        lines.extend(["", "--- 警告 ---", *result.warnings])

    return "\n".join(lines)


def _kline_last_date(result: TechAnalysisResult) -> str:
    if result.kline_last_date:
        return result.kline_last_date
    if result.data_timestamp:
        return result.data_timestamp.strftime("%Y-%m-%d")
    return "N/A"
