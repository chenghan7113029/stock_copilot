"""CLI 报告格式化：分析结果 → Markdown 文本或 JSON。"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from service.guard.models.fresh_entry_view import FreshEntryView
from service.portfolio.models.portfolio_result import PortfolioAnalysisResult
from service.report.explainers import (
    applicability_to_zh,
    assessment_to_zh,
    format_mos_percent_points,
    render_tech_explanations,
    render_value_explanations,
)
from service.report.models.dashboard_view import DashboardView
from service.sentiment.models.sentiment_result import SentimentAnalysisResult
from service.tech.models.tech_result import TechAnalysisResult
from service.trade_review.models.trade_review_result import TradeReviewResult
from service.value.anchor import percentile_band
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


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def format_tech_report(result: TechAnalysisResult, as_json: bool = False) -> str:
    if as_json:
        return _dump_json(result)

    lines: list[str] = [
        f"# 技术面分析报告 {result.code}",
        "",
        f"[离线模式] K线末行: {_kline_last_date(result)} | quote_mode: {result.quote_mode}",
        "",
        f"- **综合评分:** {result.signal_score if result.signal_score is not None else 'N/A'}",
        f"- **信号:** {result.buy_signal.value}",
        f"- **趋势:** {result.trend_status.value} ({result.ma_alignment})",
    ]

    if result.weekly_trend_status is not None:
        lines.append(
            f"- **周线:** {result.weekly_trend_status.value} ({result.weekly_ma_alignment})"
        )

    lines.extend(
        [
            "",
            "## 均线",
            "",
            f"MA5={_fmt_num(result.ma5)} MA10={_fmt_num(result.ma10)} "
            f"MA20={_fmt_num(result.ma20)} MA60={_fmt_num(result.ma60)}",
            f"现价: {_fmt_num(result.current_price)}",
            "",
            "## 指标",
            "",
            f"- MACD: {result.macd_status.value} | {result.macd_signal}",
            f"- RSI(6/12/24): {_fmt_num(result.rsi_6)}/{_fmt_num(result.rsi_12)}/{_fmt_num(result.rsi_24)} "
            f"({result.rsi_status.value})",
            f"- KDJ: K={_fmt_num(result.kdj_k)} D={_fmt_num(result.kdj_d)} J={_fmt_num(result.kdj_j)} "
            f"({result.kdj_status.value})",
            f"- 量能: {result.volume_status.value} (5日量比 {_fmt_num(result.volume_ratio_5d)})",
            f"- Bias: MA5={_fmt_num(result.bias_ma5)}% MA10={_fmt_num(result.bias_ma10)}% "
            f"MA20={_fmt_num(result.bias_ma20)}%",
            "",
            "--- 布林带 ---",
            (
                f"中轨={_fmt_num(result.boll_mid)} 上轨={_fmt_num(result.boll_upper)} "
                f"下轨={_fmt_num(result.boll_lower)} | 带宽={result.boll_bandwidth:.2%} "
                f"(百分位 {_fmt_num(result.boll_percentile, 0)}%) | {result.boll_status.value}"
            ),
        ]
    )

    if result.support_levels or result.resistance_levels:
        lines.extend(
            [
                "",
                "## 支撑/压力",
                "",
                f"- 支撑: {', '.join(_fmt_num(x) for x in result.support_levels) or 'N/A'}",
                f"- 压力: {', '.join(_fmt_num(x) for x in result.resistance_levels) or 'N/A'}",
            ]
        )

    if result.winner_ratio is not None:
        chip_status = result.chip_status.value if result.chip_status is not None else "N/A"
        lines.extend(
            [
                "",
                "## 筹码分布",
                "",
                f"获利比例 {result.winner_ratio:.1f}% | 套牢比例 {_fmt_num(result.trap_ratio, 1)}% | "
                f"平均成本 {_fmt_num(result.avg_cost)} | 集中度(90%/70%) "
                f"{_fmt_num(result.concentration_90, 1)}/{_fmt_num(result.concentration_70, 1)} | {chip_status}",
            ]
        )

    if result.candlestick_patterns:
        lines.extend(["", "--- K 线形态 ---", ""])
        for signal in result.candlestick_patterns:
            lines.append(
                f"{signal.trade_date} {signal.pattern.value}（{signal.direction}）：{signal.description}"
            )

    if result.signal_reasons:
        lines.extend(["", "## 信号理由", "", *_bullet_lines(result.signal_reasons)])

    if result.risk_factors:
        lines.extend(["", "## 风险", "", *_bullet_lines(result.risk_factors)])

    if result.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(result.warnings)])

    lines.extend(render_tech_explanations(result))
    return "\n".join(lines)


def _method_semantic_hint(key: str, mr: Any) -> str:
    """DCF/EPV 方法行的语义提示（EPV=地板价，DCF=含增长假设）。"""
    details = getattr(mr, "details", None) or {}
    if key == "scenario_dcf":
        position = details.get("price_position")
        if position:
            return f"(浅情景三档；落位={position})"
        return "(浅情景三档)"
    if key in {"cyclical_pe", "cyclical_fcf"}:
        label = details.get("cycle_position_label") or details.get("cycle_position")
        if label:
            return f"(周期调整；位置={label})"
        return "(周期调整)"
    if key == "defense_orders":
        years = details.get("order_execution_years")
        if years is not None:
            return f"(订单驱动；消化≈{years}年)"
        return "(订单驱动)"
    if key == "insurance_ev":
        pev = details.get("p_ev_actual")
        if pev is not None:
            return f"(EV/NBV；P/EV={pev:.2f}x)"
        return "(EV/NBV)"
    if key == "peg":
        peg = details.get("peg_ratio") or details.get("peg")
        if peg is not None:
            return f"(成长 PEG={peg:.2f})"
        return "(成长 PEG)"
    if key == "garp":
        return "(成长 GARP)"
    if key == "rule_of_40":
        score = details.get("rule_of_40_score") or details.get("score")
        if score is not None:
            return f"(Rule of 40={score:.1f})"
        return "(Rule of 40)"
    if key == "dcf":
        g1 = details.get("growth_1_5")
        if g1 is not None:
            return f"(含增长假设：g₁={g1:.1f}% 5年)"
        return "(含增长假设)"
    if key == "epv":
        return "(零增长地板价)"
    return ""


def _append_scenario_section(lines: list[str], result: ValueAnalysisResult) -> None:
    scenario = (result.method_results or {}).get("scenario_dcf")
    if scenario is None:
        return
    details = getattr(scenario, "details", None) or {}
    if details.get("output_type") != "scenario":
        return
    scenarios = details.get("scenarios") or {}
    if not scenarios:
        return

    lines.extend(["", "## 浅情景 DCF（悲观 / 基准 / 乐观）", ""])
    for key in ("bear", "base", "bull"):
        row = scenarios.get(key) or {}
        label = row.get("label") or key
        fv = row.get("fair_value")
        g1 = row.get("growth_rate_1_5")
        g1_text = f"{g1:.1f}%" if isinstance(g1, (int, float)) else "N/A"
        lines.append(
            f"- **{label}**: 公允价 {_fmt_num(fv if isinstance(fv, (int, float)) else None)}"
            f"（1-5年增速 {g1_text}）"
        )
    if scenario.assessment:
        lines.append(f"- **现价落位:** {scenario.assessment}")
    lines.append("- 说明: 主结论看三档相对位置，勿把基准情景当成唯一公允价")
    cash_source = details.get("cash_source")
    if cash_source and cash_source != "fcf":
        lines.append(f"- 现金流底座: `{cash_source}`（制造扩张期可能非报告 FCF）")


def _append_cyclical_section(lines: list[str], result: ValueAnalysisResult) -> None:
    methods = result.method_results or {}
    primary = None
    for key in ("cyclical_fcf", "cyclical_pe"):
        mr = methods.get(key)
        details = getattr(mr, "details", None) or {}
        if mr is not None and details.get("output_type") == "cyclical":
            primary = mr
            break
    if primary is None:
        return
    details = primary.details or {}
    lines.extend(["", "## 周期调整估值", ""])
    label = details.get("cycle_position_label") or details.get("cycle_position") or "未知"
    lines.append(f"- **周期位置:** {label}")
    fcf = methods.get("cyclical_fcf")
    if fcf is not None and (fcf.details or {}).get("output_type") == "cyclical":
        fd = fcf.details or {}
        lines.append(
            f"- **Cyclical FCF:** 公允价 {_fmt_num(fcf.fair_value)}"
            f"（FCF Yield {fd.get('fcf_yield', 'N/A')}% / 公允 {fd.get('fair_fcf_yield', 'N/A')}%）"
        )
    pe = methods.get("cyclical_pe")
    if pe is not None and (pe.details or {}).get("output_type") == "cyclical":
        pd = pe.details or {}
        lines.append(
            f"- **Cyclical PE:** 公允价 {_fmt_num(pe.fair_value)}"
            f"（均值化 EPS {_fmt_num(pd.get('cyclical_adjusted_eps'), 3)} × {pd.get('fair_pe', 'N/A')}x）"
        )
    if primary.assessment:
        lines.append(f"- **综合落位:** {primary.assessment}")
    lines.append("- 说明: 无可靠周期位置时不会毕业；勿把景气高峰的低 PE/高 FCF Yield 当便宜")


def _append_defense_section(lines: list[str], result: ValueAnalysisResult) -> None:
    defense = (result.method_results or {}).get("defense_orders")
    if defense is None:
        return
    details = getattr(defense, "details", None) or {}
    if details.get("output_type") != "defense_orders":
        return

    lines.extend(["", "## 军工订单驱动估值", ""])
    backlog = details.get("order_backlog")
    years = details.get("order_execution_years")
    margin = details.get("order_margin")
    if isinstance(backlog, (int, float)):
        lines.append(f"- **在手订单:** {backlog / 1e8:.2f} 亿元")
    if years is not None:
        lines.append(f"- **预计消化:** {years} 年")
    if margin is not None:
        lines.append(f"- **订单利润率:** {margin}%（税前）")
    lines.append(f"- **订单折现公允价:** {_fmt_num(defense.fair_value)}")
    if defense.assessment:
        lines.append(f"- **评估:** {defense.assessment}")
    lines.append("- 说明: 订单多为配置/手工输入；缺输入时保持诚实降级，勿用通用 DCF 替代")


def _append_insurance_section(lines: list[str], result: ValueAnalysisResult) -> None:
    insurance = (result.method_results or {}).get("insurance_ev")
    if insurance is None:
        return
    details = getattr(insurance, "details", None) or {}
    if details.get("output_type") != "insurance_ev":
        return

    lines.extend(["", "## 保险 EV/NBV 估值", ""])
    ev = details.get("embedded_value")
    if isinstance(ev, (int, float)):
        lines.append(f"- **内含价值 EV:** {ev / 1e8:.2f} 亿元")
    ev_ps = details.get("ev_per_share")
    if ev_ps is not None:
        lines.append(f"- **每股 EV:** {_fmt_num(ev_ps)}")
    pev = details.get("p_ev_actual")
    pev_fair = details.get("p_ev_fair")
    if pev is not None:
        lines.append(f"- **当前 P/EV:** {pev:.2f}x（公允假设 {pev_fair}x）")
    nbv = details.get("nbv")
    if isinstance(nbv, (int, float)) and nbv > 0:
        lines.append(f"- **一年新业务价值 NBV:** {nbv / 1e8:.2f} 亿元")
    lines.append(f"- **EV 对照公允价:** {_fmt_num(insurance.fair_value)}")
    if insurance.assessment:
        lines.append(f"- **评估:** {insurance.assessment}")
    lines.append("- 说明: EV/NBV 依赖年报或配置手工输入；缺 EV 时保持诚实降级")


def _append_growth_tech_section(lines: list[str], result: ValueAnalysisResult) -> None:
    if result.prototype != "growth_tech":
        return
    methods = result.method_results or {}
    if not any(k in methods for k in ("peg", "garp", "rule_of_40")):
        return

    lines.extend(["", "## 成长科技方法（PEG / GARP / Rule of 40）", ""])
    peg = methods.get("peg")
    if peg is not None and peg.error is None and peg.applicability != "Not Applicable":
        pd = peg.details or {}
        lines.append(
            f"- **PEG:** {_fmt_num(pd.get('peg_ratio'))}"
            f"（PE {_fmt_num(pd.get('pe_ratio'), 1)} / 增速 {_fmt_num(pd.get('growth_rate'), 1)}%）"
            f" → 公允价 {_fmt_num(peg.fair_value)}"
        )
    garp = methods.get("garp")
    if garp is not None and garp.error is None and garp.applicability != "Not Applicable":
        lines.append(f"- **GARP:** 公允价 {_fmt_num(garp.fair_value)} | {garp.assessment}")
    rule = methods.get("rule_of_40")
    if rule is not None and rule.error is None and rule.applicability != "Not Applicable":
        rd = rule.details or {}
        lines.append(
            f"- **Rule of 40:** 得分 {_fmt_num(rd.get('rule_of_40_score') or rd.get('score'), 1)}"
            f"（增速 {_fmt_num(rd.get('growth'), 1)}% + FCF 利润率 {_fmt_num(rd.get('fcf_margin'), 1)}%）"
        )
    lines.append("- 说明: 成长科技路由显式使用 PEG 族方法，避免被当成普通 value_growth")


def format_value_report(
    result: ValueAnalysisResult,
    as_json: bool = False,
    *,
    show_anchor_price: bool = False,
    anchor_high: tuple[float, int] | None = None,
) -> str:
    if as_json:
        return _dump_json(result)

    ts = "N/A"
    if result.data_timestamp:
        ts = result.data_timestamp.strftime("%Y-%m-%d %H:%M")

    lines: list[str] = [
        f"# 价值面分析报告 {result.code}",
        "",
        f"[离线模式] 价值快照: {ts}",
        "",
    ]
    if not result.methodology_applicable:
        honesty_warnings = [
            w for w in result.warnings if "不能作为买卖依据" in w or "不应用于买卖决策" in w
        ]
        if honesty_warnings:
            lines.extend(
                [
                    "> **诚实降级（方法暂不适用）**",
                    ">",
                    f"> {honesty_warnings[0]}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "> **诚实降级（方法暂不适用）**",
                    ">",
                    "> 专用估值方法暂缺，当前数字仅供对照，不能作为买卖依据",
                    "",
                ]
            )

    lines.extend(
        [
            f"- **名称:** {result.name or 'N/A'}",
            f"- **原型:** {result.prototype}",
            f"- **现价:** {_fmt_num(result.current_price)}",
        ]
    )
    if result.value_trap_alert:
        lines.extend(
            [
                "",
                "> **价值陷阱高危警示**",
                ">",
                f"> {result.value_trap_alert}",
            ]
        )
    lines.extend(
        [
            f"- **评估:** {result.assessment}",
            f"- **置信度:** {result.confidence}",
        ]
    )

    contrast_note = "（对照用）" if not result.methodology_applicable else ""

    if result.fair_value_range:
        r = result.fair_value_range
        lines.extend(
            [
                "",
                "## 估值",
                "",
                f"- 公允价区间{contrast_note}: {_fmt_num(r.low)} ~ {_fmt_num(r.base)} ~ {_fmt_num(r.high)}",
            ]
        )

    if result.margin_of_safety is not None:
        lines.append(
            f"- 安全边际{contrast_note}: {format_mos_percent_points(result.margin_of_safety)}"
        )

    if result.price_percentile is not None:
        band = percentile_band(result.price_percentile)
        lines.append(f"- 当前价格处于{band}（分位 {result.price_percentile:.0f}%）")

    if show_anchor_price and anchor_high is not None:
        high, window_days = anchor_high
        lines.extend(
            [
                f"- 历史最高价: {high:.2f}（基于本地缓存 {window_days} 条交易日数据）",
                "- ⚠ 历史最高价仅供参考，不建议作为决策心理锚点",
            ]
        )

    _append_scenario_section(lines, result)
    _append_cyclical_section(lines, result)
    _append_defense_section(lines, result)
    _append_insurance_section(lines, result)
    _append_growth_tech_section(lines, result)

    if result.method_results:
        lines.extend(["", "## 估值方法", ""])
        for key, mr in result.method_results.items():
            fv = _fmt_num(mr.fair_value) if mr.fair_value else "N/A"
            hint = _method_semantic_hint(key, mr)
            assess = assessment_to_zh(mr.assessment)
            appl = applicability_to_zh(mr.applicability)
            line = f"- `{key}`: 公允价={fv} | {assess} ({appl})"
            if hint:
                line = f"{line} {hint}"
            lines.append(line)

    if result.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(result.warnings)])

    lines.extend(render_value_explanations(result))
    return "\n".join(lines)


def _numbered_evidence(items: list[str]) -> list[dict[str, int | str]]:
    from service.dual_track.evidence_bucketer import number_evidence_list

    return number_evidence_list(items)


def format_dual_report(
    code: str,
    bull_evidence: list[str],
    bear_evidence: list[str],
    *,
    analysis_summary: str = "",
    as_json: bool = False,
    sentiment_result: SentimentAnalysisResult | None = None,
    value_result: ValueAnalysisResult | None = None,
    tech_result: TechAnalysisResult | None = None,
) -> str:
    """红蓝对抗 Level 0：证据分桶输出；JSON 含稳定 1-based index。"""
    payload = {
        "code": code,
        "analysis_summary": analysis_summary,
        "bull_evidence": _numbered_evidence(bull_evidence),
        "bear_evidence": _numbered_evidence(bear_evidence),
        "sentiment_result": _to_json_serializable(sentiment_result),
    }
    if as_json:
        # 讲解仅默认出现在文本模式，避免撑破 Skill 消费体积
        return _dump_json(payload)

    lines: list[str] = [
        f"# 红蓝对抗证据分桶 {code}",
        "",
        "[离线模式] Level 0 — 确定性证据分桶"
        "（产品主路径：`report confront --narrate`；Skill 为 fallback）",
        "",
    ]
    if analysis_summary:
        lines.extend([f"**摘要:** {analysis_summary}", ""])
    if sentiment_result is not None:
        status = (
            sentiment_result.market_sentiment_status.value
            if sentiment_result.market_sentiment_status is not None
            else "数据不足"
        )
        score = _fmt_num(sentiment_result.market_sentiment_score, 1)
        lines.extend([f"**市场情绪:** {status}（指数 {score}）", ""])

    lines.extend([f"## 多方证据 ({len(bull_evidence)})", ""])
    if bull_evidence:
        lines.extend(f"{i}. {item}" for i, item in enumerate(bull_evidence, 1))
    else:
        lines.append("- （空）")

    lines.extend(["", f"## 空方证据 ({len(bear_evidence)})", ""])
    if bear_evidence:
        lines.extend(f"{i}. {item}" for i, item in enumerate(bear_evidence, 1))
    else:
        lines.append("- （空）")

    if value_result is not None:
        lines.extend(["", "## 价值面讲解（与 report value 同源）"])
        lines.extend(render_value_explanations(value_result))
    if tech_result is not None:
        lines.extend(["", "## 技术面讲解（与 report tech 同源）"])
        lines.extend(render_tech_explanations(tech_result))

    return "\n".join(lines)


def format_confront_report(
    *,
    code: str,
    evidence: dict[str, Any],
    narrate_status: str,
    narrative: dict[str, Any] | None = None,
    confrontation_id: int | None = None,
    narrate_error: str | None = None,
    from_cache: bool = False,
    low_confidence_warning: bool = False,
    as_json: bool = False,
) -> str:
    """红蓝对抗 Level 0/1 报告（产品主路径）。"""
    payload = {
        "code": code,
        "confrontation_id": confrontation_id,
        "narrate_status": narrate_status,
        "evidence": evidence,
        "narrative": narrative,
        "narrate_error": narrate_error,
        "from_cache": from_cache,
        "low_confidence_warning": low_confidence_warning,
        "disclaimer": (
            "叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实。不构成买卖建议。"
        ),
    }
    if as_json:
        return _dump_json(payload)

    bull = evidence.get("bull_evidence") or []
    bear = evidence.get("bear_evidence") or []
    lines: list[str] = [
        f"# 红蓝对抗报告 {code}",
        "",
        f"**narrate_status:** {narrate_status}",
    ]
    if confrontation_id is not None:
        lines.append(f"**confrontation_id:** {confrontation_id}")
    if from_cache:
        lines.append("**来源:** LLM 缓存")
    if low_confidence_warning:
        lines.append("**警告:** 叙事置信度偏低，请人工核对证据")
    lines.append("")

    summary = evidence.get("analysis_summary") or ""
    if summary:
        lines.extend([f"**摘要:** {summary}", ""])

    lines.extend([f"## 多方证据 ({len(bull)})", ""])
    if bull:
        for item in bull:
            if isinstance(item, dict):
                lines.append(f"{item.get('index', '?')}. {item.get('text', '')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- （空）")

    lines.extend(["", f"## 空方证据 ({len(bear)})", ""])
    if bear:
        for item in bear:
            if isinstance(item, dict):
                lines.append(f"{item.get('index', '?')}. {item.get('text', '')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- （空）")

    if narrative:
        lines.extend(["", "## 多方论述", "", narrative.get("bull_thesis") or "（空）"])
        lines.extend(["", "## 空方论述", "", narrative.get("bear_thesis") or "（空）"])
        bull_rebs = narrative.get("bull_rebuttals") or []
        lines.extend(["", "## 多方反驳空方", ""])
        if bull_rebs:
            for reb in bull_rebs:
                idx = reb.get("target_index", "?")
                lines.append(f"- 针对空方证据 [{idx}]：{reb.get('text', '')}")
        else:
            lines.append("- （空）")
        bear_rebs = narrative.get("bear_rebuttals") or []
        lines.extend(["", "## 空方反驳多方", ""])
        if bear_rebs:
            for reb in bear_rebs:
                idx = reb.get("target_index", "?")
                lines.append(f"- 针对多方证据 [{idx}]：{reb.get('text', '')}")
        else:
            lines.append("- （空）")
        conf = narrative.get("confidence")
        if conf is not None:
            lines.extend(["", f"**置信度:** {conf}"])
        disc = narrative.get("disclaimer") or payload["disclaimer"]
        lines.extend(["", f"> {disc}"])
    elif narrate_status == "failed":
        lines.extend(
            [
                "",
                "## LLM 互驳叙事",
                "",
                f"叙事失败：{narrate_error or '未知错误'}。请仅使用上方 Level 0 证据。",
            ]
        )
    elif narrate_status == "skipped":
        lines.extend(
            [
                "",
                "## LLM 互驳叙事",
                "",
                "未请求 `--narrate`。产品主路径可运行：`report confront <code> --narrate`。",
            ]
        )

    return "\n".join(lines)


def format_persona_stress_report(
    *,
    code: str,
    evidence: dict[str, Any],
    persona_stress: dict[str, Any],
    confrontation_id: int | None = None,
    as_json: bool = False,
) -> str:
    """Persona 压力测试报告（Level 0 占位 / Level 1 narrate）。"""
    disclaimer = persona_stress.get("disclaimer") or (
        "persona 为思维透镜，不构成买卖建议。"
        "三种 lens 冲突时，应回到 declare 明确立场。"
    )
    payload = {
        "code": code,
        "confrontation_id": confrontation_id,
        "evidence": evidence,
        "persona_stress": persona_stress,
        "disclaimer": disclaimer,
    }
    if as_json:
        return _dump_json(payload)

    labels = {
        "value_quality": "价值质量",
        "trend_momentum": "趋势动量",
        "risk_governor": "风控官",
    }
    bull = evidence.get("bull_evidence") or []
    bear = evidence.get("bear_evidence") or []
    lines: list[str] = [
        f"# Persona 压力测试 {code}",
        "",
    ]
    if confrontation_id is not None:
        lines.append(f"**confrontation_id:** {confrontation_id}")
        lines.append("")

    summary = evidence.get("analysis_summary") or ""
    if summary:
        lines.extend([f"**摘要:** {summary}", ""])

    lines.extend([f"## 多方证据 ({len(bull)})", ""])
    if bull:
        for item in bull:
            if isinstance(item, dict):
                lines.append(f"{item.get('index', '?')}. {item.get('text', '')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- （空）")

    lines.extend(["", f"## 空方证据 ({len(bear)})", ""])
    if bear:
        for item in bear:
            if isinstance(item, dict):
                lines.append(f"{item.get('index', '?')}. {item.get('text', '')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- （空）")

    personas = persona_stress.get("personas") or []
    lines.extend(["", "## Persona 结果", ""])
    if not personas:
        lines.append("- （无）")
    for entry in personas:
        pid = entry.get("id", "?")
        label = labels.get(str(pid), str(pid))
        status = entry.get("status", "?")
        lines.extend([f"### {label} (`{pid}`) — {status}", ""])
        if status == "pending":
            lines.append("待 `--narrate` 生成 lens 解读。")
        elif status == "failed":
            lines.append(f"失败：{entry.get('error') or '未知错误'}")
        else:
            output = entry.get("output") or {}
            lines.append(output.get("lens_summary") or "（空）")
            refs = output.get("emphasized_refs") or []
            if refs:
                lines.extend(["", "**强调证据:**"])
                for ref in refs:
                    lines.append(f"- [{ref.get('side')}:{ref.get('index')}]")
            blinds = output.get("blind_spots") or []
            if blinds:
                lines.extend(["", "**盲点:**"])
                for b in blinds:
                    lines.append(f"- {b}")
            questions = output.get("questions_for_self") or []
            if questions:
                lines.extend(["", "**自省问题:**"])
                for q in questions:
                    lines.append(f"- {q}")
        lines.append("")

    lines.extend([f"> {disclaimer}"])
    return "\n".join(lines)


def format_sentiment_report(result: SentimentAnalysisResult, as_json: bool = False) -> str:
    disclaimer = (
        f"情绪面结论不得单独作为买卖依据，请结合 `report dual {result.code}` "
        "查看价值+技术+情绪联合解读"
    )
    if as_json:
        payload = _to_json_serializable(result)
        payload["disclaimer"] = disclaimer
        return _dump_json(payload)

    score = _fmt_num(result.market_sentiment_score, 1)
    ratio = f"{result.limit_updown_ratio:.1%}" if result.limit_updown_ratio is not None else "N/A"
    status = result.market_sentiment_status.value if result.market_sentiment_status is not None else "数据不足"
    lines = [
        f"# 情绪面分析报告 {result.code}",
        "",
        "[严格离线] 读取最近一次市场级情绪快照",
        "",
        f"- **市场情绪:** {status}",
        f"- **恐慌贪婪代理指数:** {score}",
        f"- **涨跌停家数比:** {ratio}",
    ]
    if result.reasons:
        lines.extend(["", "## 依据", "", *_bullet_lines(result.reasons)])
    if result.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(result.warnings)])
    lines.extend(["", f"> ⚠ {disclaimer}"])
    return "\n".join(lines)


def format_dashboard_report(view: DashboardView, as_json: bool = False) -> str:
    """多维看板汇总输出（Markdown / JSON）。"""
    if as_json:
        return _dump_json(view)

    lines: list[str] = [
        f"# 多维看板 {view.code}",
        "",
        "[离线模式] 本命令为汇总视图，单维度深入分析请使用 report tech/value/dual",
        "",
        "## 价值面",
        "",
        view.value_section or "（空）",
        "",
        "## 技术面",
        "",
        view.tech_section or "（空）",
        "",
        "## 情绪面",
        "",
        view.sentiment_section or "（空）",
        "",
        "## Checklist",
        "",
        view.checklist_section or "（空）",
        "",
        "## 综合摘要",
        "",
        view.combined_summary or "（空）",
    ]
    if view.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(view.warnings)])
    return "\n".join(lines)


def format_entry_check_report(view: FreshEntryView, as_json: bool = False) -> str:
    """格式化无仓位视角入场检查，避免输出持仓成本与盈亏百分比。"""
    if as_json:
        return _dump_json(view)

    position_hint = "已录入持仓（已隐藏相关信息）" if view.has_position else "未录入持仓"
    return "\n".join(
        [
            f"# 无仓位视角入场检查 {view.code}",
            "",
            "[严格离线] 本报告不展示持仓成本或盈亏百分比",
            "",
            f"- **现价:** {_fmt_num(view.current_price)}",
            f"- **持仓状态:** {position_hint}",
            "",
            "## 三维分析摘要",
            "",
            view.value_summary,
            view.tech_summary,
            "",
            "## 自我提问",
            "",
            view.framing_question,
            "",
            f"**提示:** {view.reminder_text}",
            "",
            "若你的答案是否定的，请重新评估当前仓位是否需要减仓或止损。",
        ]
    )


def format_confrontation_history(
    code: str,
    records: list[Any],
    *,
    as_json: bool = False,
) -> str:
    """列出某票 confrontation 历史（含 declare 状态）。"""
    rows = []
    for record in records:
        evidence = getattr(record, "evidence", None) or {}
        bull = evidence.get("bull_evidence") or []
        bear = evidence.get("bear_evidence") or []
        decl = getattr(record, "declaration", None) or {}
        rows.append(
            {
                "id": record.id,
                "code": record.code,
                "narrate_status": record.narrate_status,
                "declare_status": record.declare_status,
                "declared_at": (
                    record.declared_at.isoformat() if record.declared_at else None
                ),
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "bull_count": len(bull) if isinstance(bull, list) else 0,
                "bear_count": len(bear) if isinstance(bear, list) else 0,
                "declare_stance": decl.get("stance") if isinstance(decl, dict) else None,
            }
        )
    if as_json:
        return _dump_json({"code": code, "records": rows})
    if not rows:
        return f"暂无 {code} 的 confrontation 记录"
    lines = [f"# Confrontation 历史 — {code}", ""]
    for row in rows:
        stance = row["declare_stance"] or "-"
        lines.append(
            f"- **#{row['id']}** | narrate={row['narrate_status']} | "
            f"declare={row['declare_status'] or 'none'} | stance={stance} | "
            f"evidence bull={row['bull_count']} bear={row['bear_count']} | "
            f"created={row['created_at']}"
        )
    return "\n".join(lines)


def format_trade_review_report(result: TradeReviewResult, as_json: bool = False) -> str:
    """格式化严格离线的 FIFO 交易复盘报告。"""
    if as_json:
        return _dump_json(result)

    win_rate = "N/A" if result.win_rate is None else f"{result.win_rate:.1%}"
    avg_return = "N/A" if result.avg_return is None else f"{result.avg_return:.2%}"
    lines = [
        "# 交易复盘报告",
        "",
        "[严格离线] FIFO 配对的已实现收益统计",
        "",
        f"- **FIFO 胜率:** {win_rate}",
        f"- **平均已实现收益率:** {avg_return}",
        f"- **已平仓配对数:** {result.total_trades}",
        f"- **当前未平仓数量:** {result.open_positions}",
    ]
    if result.checklist_data_available:
        lines.extend(["", f"## Badcase ({len(result.badcase_list)})", ""])
        if result.badcase_list:
            lines.extend(
                (
                    f"- `{item.code}` | Checklist #{item.checklist_id} | "
                    f"收益率 {item.return_rate:.2%} | 数量 {item.quantity}"
                    + (
                        f" | declare={item.declare_stance}"
                        if item.declare_stance
                        else ""
                    )
                )
                for item in result.badcase_list
            )
        else:
            lines.append("- （无）")
        if result.badcase_summary:
            lines.extend(["", "## 描述性统计", "", *_bullet_lines(list(result.badcase_summary))])
    if result.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(result.warnings)])
    return "\n".join(lines)


def format_portfolio_report(result: PortfolioAnalysisResult, as_json: bool = False) -> str:
    """格式化严格离线组合集中度与行业暴露度报告。"""
    if as_json:
        return _dump_json(result)

    lines = [
        "# 持仓组合报告",
        "",
        "[严格离线] 基于 TradeRecord 与本地价值快照的市值粗估",
        "",
        f"- **组合总市值:** {_fmt_num(result.total_value)}",
        "",
        "## 单票持仓占比",
        "",
    ]
    if result.positions:
        lines.extend(
            f"- `{position.code}` | 数量 {position.quantity} | 市值 {_fmt_num(position.market_value)} | "
            f"占比 {position.weight:.1%} | 行业 {position.industry or 'N/A'}"
            for position in result.positions
        )
    else:
        lines.append("- （无）")

    lines.extend(["", "## 集中度", ""])
    if result.top_n_concentration:
        for n, concentration in sorted(result.top_n_concentration.items()):
            lines.append(f"- 前 {n} 大持仓占比: {concentration:.1%}")
    else:
        lines.append("- N/A")

    lines.extend(["", "## 行业暴露度（粗估）", ""])
    if result.industry_exposure:
        lines.extend(
            f"- {industry}: {exposure:.1%}"
            for industry, exposure in sorted(
                result.industry_exposure.items(), key=lambda item: item[1], reverse=True
            )
        )
    else:
        lines.append("- N/A")

    if result.warnings:
        lines.extend(["", "## 警告", "", *_bullet_lines(result.warnings)])
    return "\n".join(lines)


def format_summary_report(
    deterministic: dict[str, Any],
    *,
    narrative: dict[str, Any] | None = None,
    narrative_error: str | None = None,
    as_json: bool = False,
) -> str:
    """综合摘要输出：确定性部分 + 可选 LLM 叙事（失败时降级提示）。"""
    payload: dict[str, Any] = {
        **deterministic,
        "narrative": narrative,
        "narrative_error": narrative_error,
    }
    if as_json:
        return _dump_json(payload)

    code = deterministic.get("code", "")
    name = (deterministic.get("name") or "").strip()
    title = f"# 综合摘要 {code} {name}" if name else f"# 综合摘要 {code}"
    lines: list[str] = [
        title,
        "",
        "[离线模式] 确定性摘要"
        + (" + LLM 叙事" if narrative else "")
        + ("（叙事失败已降级）" if narrative_error else ""),
        "",
        "## 确定性摘要",
        "",
    ]
    if name:
        lines.append(f"- **名称:** {name}")
    lines.extend(
        [
            f"- **综合信号:** {deterministic.get('combined_signal') or 'N/A'}",
            f"- **价值评级:** {deterministic.get('value_rating') or 'N/A'}",
            f"- **红蓝证据:** 多方 {deterministic.get('bull_evidence_count', 0)} 条 / "
            f"空方 {deterministic.get('bear_evidence_count', 0)} 条",
        ]
    )
    summary = deterministic.get("analysis_summary") or ""
    if summary:
        lines.extend(["", summary])

    if narrative_error:
        lines.extend(
            [
                "",
                f"> **warn** LLM 叙事生成失败：{narrative_error}",
                ">",
                "> 以下为确定性摘要（未附加 LLM 叙事）。",
            ]
        )
    elif narrative:
        lines.extend(["", "## LLM 综合叙事", "", narrative.get("summary") or "（空）"])
        key_points = narrative.get("key_points") or []
        if key_points:
            lines.extend(["", "**关键要点:**", "", *_bullet_lines(list(key_points))])
        risks = narrative.get("risks") or []
        if risks:
            lines.extend(["", "**风险提示:**", "", *_bullet_lines(list(risks))])
        conf = narrative.get("confidence")
        if conf is not None:
            lines.append(f"- **置信度:** {conf}")

    return "\n".join(lines)


def format_checklist_records(code: str, records: list[Any], as_json: bool = False) -> str:
    """格式化某只股票的 Checklist 历史记录。"""
    payload = [
        {
            "code": record.code,
            "action": record.action,
            "passed": record.passed,
            "created_at": record.created_at,
            "value_reasons": record.value_reasons,
            "tech_alignment": record.tech_alignment,
            "sentiment_position": record.sentiment_position,
            "stop_loss_price": record.stop_loss_price,
            "take_profit_price": record.take_profit_price,
            "rejection_reasons": record.rejection_reasons,
        }
        for record in records
    ]
    if as_json:
        return _dump_json(payload)

    lines = [f"# Checklist 历史记录 {code}"]
    for index, record in enumerate(payload, 1):
        status = "合规" if record["passed"] else "不合规"
        created_at = _to_json_serializable(record["created_at"]) or "N/A"
        lines.extend(
            [
                "",
                f"## #{index} {status} | {created_at}",
                "",
                f"- **动作:** {record['action'] or '未指定'}",
                f"- **价值理由:** {'；'.join(record['value_reasons']) or '（未填写）'}",
                f"- **技术面配合:** {record['tech_alignment'] or '（未填写）'}",
                f"- **情绪位置:** {record['sentiment_position'] or '（未填写）'}",
                f"- **止损/止盈:** {_fmt_num(record['stop_loss_price'])} / {_fmt_num(record['take_profit_price'])}",
            ]
        )
        if record["rejection_reasons"]:
            lines.append(f"- **拒绝原因:** {'；'.join(record['rejection_reasons'])}")
    return "\n".join(lines)


def _kline_last_date(result: TechAnalysisResult) -> str:
    if result.kline_last_date:
        return result.kline_last_date
    if result.data_timestamp:
        return result.data_timestamp.strftime("%Y-%m-%d")
    return "N/A"
