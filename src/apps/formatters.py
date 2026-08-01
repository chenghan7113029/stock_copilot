"""CLI 报告格式化：TechAnalysisResult / ValueAnalysisResult → text 或 JSON。"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from service.guard.models.fresh_entry_view import FreshEntryView
from service.portfolio.models.portfolio_result import PortfolioAnalysisResult
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

    if result.winner_ratio is not None:
        chip_status = result.chip_status.value if result.chip_status is not None else "N/A"
        lines.extend(
            [
                "",
                "--- 筹码分布 ---",
                f"获利比例 {result.winner_ratio:.1f}% | 套牢比例 {_fmt_num(result.trap_ratio, 1)}% | "
                f"平均成本 {_fmt_num(result.avg_cost)} | 集中度(90%/70%) "
                f"{_fmt_num(result.concentration_90, 1)}/{_fmt_num(result.concentration_70, 1)} | {chip_status}",
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
        f"=== 价值面分析报告 {result.code} ===",
        f"[离线模式] 价值快照: {ts}",
        "",
        f"名称: {result.name or 'N/A'}",
        f"原型: {result.prototype}",
        f"现价: {_fmt_num(result.current_price)}",
    ]
    if result.value_trap_alert:
        lines.extend(["", "⚠⚠⚠ 价值陷阱高危警示 ⚠⚠⚠", result.value_trap_alert, "⚠⚠⚠"])
    lines.extend(
        [
            f"评估: {result.assessment}",
            f"置信度: {result.confidence}",
        ]
    )

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
        band = percentile_band(result.price_percentile)
        lines.append(f"当前价格处于{band}（分位 {result.price_percentile:.0f}%）")

    if show_anchor_price and anchor_high is not None:
        high, window_days = anchor_high
        lines.extend(
            [
                f"历史最高价: {high:.2f}（基于本地缓存 {window_days} 条交易日数据）",
                "⚠ 历史最高价仅供参考，不建议作为决策心理锚点",
            ]
        )

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


def format_dual_report(
    code: str,
    bull_evidence: list[str],
    bear_evidence: list[str],
    *,
    analysis_summary: str = "",
    as_json: bool = False,
    sentiment_result: SentimentAnalysisResult | None = None,
) -> str:
    """红蓝对抗 Level 0：证据分桶输出（供 Skill 消费）。"""
    payload = {
        "code": code,
        "analysis_summary": analysis_summary,
        "bull_evidence": list(bull_evidence),
        "bear_evidence": list(bear_evidence),
        "sentiment_result": _to_json_serializable(sentiment_result),
    }
    if as_json:
        return _dump_json(payload)

    lines: list[str] = [
        f"=== 红蓝对抗证据分桶 {code} ===",
        "[离线模式] Level 0 — 确定性证据分桶（互驳叙事请用 red-blue-confrontation Skill）",
        "",
    ]
    if analysis_summary:
        lines.extend([f"摘要: {analysis_summary}", ""])
    if sentiment_result is not None:
        status = (
            sentiment_result.market_sentiment_status.value
            if sentiment_result.market_sentiment_status is not None
            else "数据不足"
        )
        score = _fmt_num(sentiment_result.market_sentiment_score, 1)
        lines.extend([f"市场情绪: {status}（指数 {score}）", ""])

    lines.append(f"--- 多方证据 ({len(bull_evidence)}) ---")
    if bull_evidence:
        lines.extend(f"  [{i}] {item}" for i, item in enumerate(bull_evidence, 1))
    else:
        lines.append("  （空）")

    lines.extend(["", f"--- 空方证据 ({len(bear_evidence)}) ---"])
    if bear_evidence:
        lines.extend(f"  [{i}] {item}" for i, item in enumerate(bear_evidence, 1))
    else:
        lines.append("  （空）")

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
        f"=== 情绪面分析报告 {result.code} ===",
        "[严格离线] 读取最近一次市场级情绪快照",
        "",
        f"市场情绪: {status}",
        f"恐慌贪婪代理指数: {score}",
        f"涨跌停家数比: {ratio}",
    ]
    if result.reasons:
        lines.extend(["", "--- 依据 ---", *result.reasons])
    if result.warnings:
        lines.extend(["", "--- 警告 ---", *result.warnings])
    lines.extend(["", f"⚠ {disclaimer}"])
    return "\n".join(lines)


def format_dashboard_report(view: DashboardView, as_json: bool = False) -> str:
    """多维看板汇总输出（text / JSON）。"""
    if as_json:
        return _dump_json(view)

    lines: list[str] = [
        f"=== 多维看板 {view.code} ===",
        "[离线模式] 本命令为汇总视图，单维度深入分析请使用 report tech/value/dual",
        "",
        "--- 价值面 ---",
        view.value_section or "（空）",
        "",
        "--- 技术面 ---",
        view.tech_section or "（空）",
        "",
        "--- 情绪面 ---",
        view.sentiment_section or "（空）",
        "",
        "--- Checklist ---",
        view.checklist_section or "（空）",
        "",
        "--- 综合摘要 ---",
        view.combined_summary or "（空）",
    ]
    if view.warnings:
        lines.extend(["", "--- 警告 ---", *view.warnings])
    return "\n".join(lines)


def format_entry_check_report(view: FreshEntryView, as_json: bool = False) -> str:
    """格式化无仓位视角入场检查，避免输出持仓成本与盈亏百分比。"""
    if as_json:
        return _dump_json(view)

    position_hint = "已录入持仓（已隐藏相关信息）" if view.has_position else "未录入持仓"
    return "\n".join(
        [
            f"=== 无仓位视角入场检查 {view.code} ===",
            "[严格离线] 本报告不展示持仓成本或盈亏百分比",
            "",
            f"现价: {_fmt_num(view.current_price)}",
            f"持仓状态: {position_hint}",
            "",
            "--- 三维分析摘要 ---",
            view.value_summary,
            view.tech_summary,
            "",
            "--- 自我提问 ---",
            view.framing_question,
            "",
            f"提示: {view.reminder_text}",
            "若你的答案是否定的，请重新评估当前仓位是否需要减仓或止损。",
        ]
    )


def format_trade_review_report(result: TradeReviewResult, as_json: bool = False) -> str:
    """格式化严格离线的 FIFO 交易复盘报告。"""
    if as_json:
        return _dump_json(result)

    win_rate = "N/A" if result.win_rate is None else f"{result.win_rate:.1%}"
    avg_return = "N/A" if result.avg_return is None else f"{result.avg_return:.2%}"
    lines = [
        "=== 交易复盘报告 ===",
        "[严格离线] FIFO 配对的已实现收益统计",
        "",
        f"FIFO 胜率: {win_rate}",
        f"平均已实现收益率: {avg_return}",
        f"已平仓配对数: {result.total_trades}",
        f"当前未平仓数量: {result.open_positions}",
    ]
    if result.checklist_data_available:
        lines.extend(["", f"--- Badcase ({len(result.badcase_list)}) ---"])
        if result.badcase_list:
            lines.extend(
                f"  {item.code} | Checklist #{item.checklist_id} | "
                f"收益率 {item.return_rate:.2%} | 数量 {item.quantity}"
                for item in result.badcase_list
            )
        else:
            lines.append("  （无）")
        if result.badcase_summary:
            lines.extend(["", "--- 描述性统计 ---", *result.badcase_summary])
    if result.warnings:
        lines.extend(["", "--- 警告 ---", *result.warnings])
    return "\n".join(lines)


def format_portfolio_report(result: PortfolioAnalysisResult, as_json: bool = False) -> str:
    """格式化严格离线组合集中度与行业暴露度报告。"""
    if as_json:
        return _dump_json(result)

    lines = [
        "=== 持仓组合报告 ===",
        "[严格离线] 基于 TradeRecord 与本地价值快照的市值粗估",
        "",
        f"组合总市值: {_fmt_num(result.total_value)}",
        "",
        "--- 单票持仓占比 ---",
    ]
    if result.positions:
        lines.extend(
            f"  {position.code} | 数量 {position.quantity} | 市值 {_fmt_num(position.market_value)} | "
            f"占比 {position.weight:.1%} | 行业 {position.industry or 'N/A'}"
            for position in result.positions
        )
    else:
        lines.append("  （无）")

    lines.extend(["", "--- 集中度 ---"])
    if result.top_n_concentration:
        for n, concentration in sorted(result.top_n_concentration.items()):
            lines.append(f"前 {n} 大持仓占比: {concentration:.1%}")
    else:
        lines.append("  N/A")

    lines.extend(["", "--- 行业暴露度（粗估） ---"])
    if result.industry_exposure:
        lines.extend(
            f"  {industry}: {exposure:.1%}"
            for industry, exposure in sorted(
                result.industry_exposure.items(), key=lambda item: item[1], reverse=True
            )
        )
    else:
        lines.append("  N/A")

    if result.warnings:
        lines.extend(["", "--- 警告 ---", *result.warnings])
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
    title = f"=== 综合摘要 {code} {name} ===" if name else f"=== 综合摘要 {code} ==="
    lines: list[str] = [
        title,
        "[离线模式] 确定性摘要"
        + (" + LLM 叙事" if narrative else "")
        + ("（叙事失败已降级）" if narrative_error else ""),
        "",
        "--- 确定性摘要 ---",
    ]
    if name:
        lines.append(f"名称: {name}")
    lines.extend(
        [
            f"综合信号: {deterministic.get('combined_signal') or 'N/A'}",
            f"价值评级: {deterministic.get('value_rating') or 'N/A'}",
            f"红蓝证据: 多方 {deterministic.get('bull_evidence_count', 0)} 条 / "
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
                f"[warn] LLM 叙事生成失败：{narrative_error}",
                "以下为确定性摘要（未附加 LLM 叙事）。",
            ]
        )
    elif narrative:
        lines.extend(["", "--- LLM 综合叙事 ---", narrative.get("summary") or "（空）"])
        key_points = narrative.get("key_points") or []
        if key_points:
            lines.extend(["", "关键要点:"])
            lines.extend(f"  - {p}" for p in key_points)
        risks = narrative.get("risks") or []
        if risks:
            lines.extend(["", "风险提示:"])
            lines.extend(f"  - {r}" for r in risks)
        conf = narrative.get("confidence")
        if conf is not None:
            lines.append(f"置信度: {conf}")

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

    lines = [f"=== Checklist 历史记录 {code} ==="]
    for index, record in enumerate(payload, 1):
        status = "合规" if record["passed"] else "不合规"
        created_at = _to_json_serializable(record["created_at"]) or "N/A"
        lines.extend(
            [
                "",
                f"--- #{index} {status} | {created_at} ---",
                f"动作: {record['action'] or '未指定'}",
                f"价值理由: {'；'.join(record['value_reasons']) or '（未填写）'}",
                f"技术面配合: {record['tech_alignment'] or '（未填写）'}",
                f"情绪位置: {record['sentiment_position'] or '（未填写）'}",
                f"止损/止盈: {_fmt_num(record['stop_loss_price'])} / {_fmt_num(record['take_profit_price'])}",
            ]
        )
        if record["rejection_reasons"]:
            lines.append(f"拒绝原因: {'；'.join(record['rejection_reasons'])}")
    return "\n".join(lines)


def _kline_last_date(result: TechAnalysisResult) -> str:
    if result.kline_last_date:
        return result.kline_last_date
    if result.data_timestamp:
        return result.data_timestamp.strftime("%Y-%m-%d")
    return "N/A"
