"""stock_copilot CLI：sync / report / watchlist / feishu。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from apps.formatters import (
    format_checklist_records,
    format_confront_report,
    format_confrontation_history,
    format_dashboard_report,
    format_dual_report,
    format_entry_check_report,
    format_persona_stress_report,
    format_portfolio_report,
    format_sentiment_report,
    format_summary_report,
    format_tech_report,
    format_trade_review_report,
    format_value_report,
)
from common.cli_progress import CliProgress, cli_progress_enabled
from common.config_loader import is_data_source_enabled, load_app_config, resolve_feishu_config
from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from common.watchlist import (
    add_to_watchlist,
    load_watchlist,
    remove_from_watchlist,
    watchlist_codes,
    watchlist_path,
)
from common.win_console import setup_utf8_console
from dao.checklist_repo import ChecklistRepo
from dao.chip_distribution_repo import ChipDistributionRepo
from dao.confrontation_repo import (
    DECLARE_OK,
    NARRATE_FAILED,
    NARRATE_OK,
    NARRATE_SKIPPED,
    ConfrontationRepo,
)
from dao.engine import Base, create_db_engine, ensure_sqlite_schema, make_session_factory
from dao.kline_repo import KlineRepo
from dao.llm_narrate_cache_repo import LLMNarrateCacheRepo
from dao.market_sentiment_repo import MarketSentimentRepo
from dao.models import (  # noqa: F401 — register ORM models
    ChecklistRecord,
    ChipDistribution,
    ConfrontationRecord,
    Kline,
    MarketSentimentSnapshot,
    PositionRecord,
    PrototypeOverrideRecord,
    TradeRecord,
)
from dao.position_repo import PositionRepo
from dao.prototype_override_repo import PrototypeOverrideRepo
from dao.stock_snapshot_repo import StockSnapshotRepo
from dao.trade_record_repo import TradeRecordRepo
from data_provider.base import is_a_share
from data_provider.chip_distribution_provider import ChipDistributionProvider
from data_provider.kline_provider import KlineProvider
from data_provider.provider import StockDataProvider
from data_provider.sentiment.provider import MarketSentimentProvider
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.evidence_bucketer import EvidenceBucketer
from service.feishu.pipeline import reports_root, run_feishu_push
from service.feishu.publisher import FeishuPublisherError
from service.guard.checklist_validator import ChecklistValidator
from service.guard.confrontation_declaration_validator import ConfrontationDeclarationValidator
from service.guard.confrontation_narrator import ConfrontationNarrator
from service.guard.fresh_entry_check import FreshEntryCheck
from service.guard.fresh_entry_check import LocalDataMissingError as FreshEntryLocalDataMissingError
from service.guard.models.checklist import ChecklistSubmission
from service.guard.models.confrontation_declaration import ConfrontationDeclaration
from service.guard.persona_stress_narrator import (
    PersonaStressNarrator,
    pending_persona_stress,
)
from service.portfolio.analyzer import PortfolioAnalyzer
from service.report.comprehensive_narrator import narrate_comprehensive_report
from service.report.dashboard_builder import DashboardBuilder, LocalDataMissingError
from service.sentiment.analyzer import SentimentAnalyzer
from service.tech.analyzer import TechAnalyzer
from service.trade_review.attribution import TradeReviewAnalyzer
from service.value.analyzer import ValueAnalyzer
from service.value.anchor import historical_high
from service.value.router import _PROTOTYPE_METHODS

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _configure_cli_logging(level_name: str = "ERROR") -> None:
    """CLI 默认仅向 stderr 输出 ERROR，避免 PowerShell 将 WARNING 误判为失败。"""
    import logging

    level = getattr(logging, level_name.upper(), logging.ERROR)
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def _resolve_target_codes(code: str | None, use_watchlist: bool) -> list[str]:
    """解析单票 code 或 --watchlist。"""
    if use_watchlist and code:
        print("[error] 请只指定股票代码或 --watchlist，不要同时使用", file=sys.stderr)
        raise SystemExit(2)
    if use_watchlist:
        codes = watchlist_codes()
        if not codes:
            print(
                f"[error] 常看列表为空，请先 watchlist add，或编辑 {watchlist_path()}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return codes
    if not code:
        print("[error] 请指定股票代码，或使用 --watchlist", file=sys.stderr)
        raise SystemExit(2)
    return [code]


def _batch_output_path(
    output: str | None, code: str, kind: str, *, as_json: bool = False
) -> str | None:
    """批量模式下将 -o 视为目录，写入 {code}_{kind}.md|.json。"""
    if not output:
        return None
    out = Path(output)
    # 单文件后缀误传时仍落到父目录
    if out.suffix.lower() in {".txt", ".json", ".md"}:
        out = out.parent if out.parent != Path("") else Path(".")
    out.mkdir(parents=True, exist_ok=True)
    ext = ".json" if as_json else ".md"
    return str(out / f"{code}_{kind}{ext}")


def run_sync(code: str, realtime: bool = False, config: dict[str, Any] | None = None) -> None:
    """同步单票价值面快照与 K 线数据（唯一联网路径）。"""
    cfg = config or load_app_config()
    _configure_cli_logging(cfg.get("logging", {}).get("cli_level", "ERROR"))
    progress = CliProgress("sync", enabled=cli_progress_enabled(cfg))
    progress_cb = progress.callback

    progress.emit(f"开始同步 {code}" + ("（含实时报价）" if realtime else ""))

    progress.emit("初始化数据库…")
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        value_provider = StockDataProvider.from_config(cfg, repo=snapshot_repo)
        value_provider.get_stock_data(code, on_progress=progress_cb)

        kline_repo = KlineRepo(session)
        kline_provider = KlineProvider.from_config(cfg, kline_repo)
        df, kline_warnings, quote_mode = kline_provider.get_kline(
            code,
            days=cfg.get("tech", {}).get("kline_days", 90),
            use_realtime=realtime,
            persist_today=realtime,
            on_progress=progress_cb,
        )
        # 先提交价值面 + K 线，避免筹码接口挂起导致整次 sync 回滚
        progress.emit("正在提交价值面与 K 线…")
        session.commit()

        chip_provider = ChipDistributionProvider.from_config(
            cfg, ChipDistributionRepo(session)
        )
        _, chip_warnings = chip_provider.get_latest(code, offline=False, on_progress=progress_cb)
        progress.emit("正在提交筹码分布…")
        session.commit()

        kline_status = f"K线 {len(df)}行 OK"
        if realtime:
            kline_status += f" (quote_mode: {quote_mode})"
        for w in kline_warnings:
            if "realtime" in w.lower() or "overlay" in w.lower() or "降级" in w:
                print(f"[warn] {w}", file=sys.stderr)
        for w in chip_warnings:
            print(f"[warn] {w}", file=sys.stderr)

        chip_status = "筹码分布 OK" if not chip_warnings else "筹码分布已降级"
        progress.emit(f"完成：value snapshot OK | {kline_status} | {chip_status}")
    except Exception as exc:
        session.rollback()
        print(f"[error] 数据拉取失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        session.close()


def run_sync_market(config: dict[str, Any] | None = None) -> None:
    """联网同步全市场情绪快照；不接收股票代码。"""
    cfg = config or load_app_config()
    _configure_cli_logging(cfg.get("logging", {}).get("cli_level", "ERROR"))
    progress = CliProgress("sync", enabled=cli_progress_enabled(cfg))
    # 情绪能力源：tushare / akshare（遗留）；不硬编码「必须 AKShare」
    has_sentiment_source = is_data_source_enabled(cfg, "tushare") or is_data_source_enabled(
        cfg, "akshare"
    )
    if not has_sentiment_source:
        print(
            "[error] 市场情绪同步依赖已配置的数据源，请在 config/app.yaml 的 "
            "data_sources.enabled 中启用 tushare（推荐）或 akshare（遗留）",
            file=sys.stderr,
        )
        raise SystemExit(1)
    progress.emit("开始同步全市场情绪数据…")
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        snapshot = MarketSentimentProvider.from_config(
            cfg, MarketSentimentRepo(session)
        ).fetch_and_persist_today()
        session.commit()
        message = (
            "市场情绪同步完成："
            f"涨停 {snapshot.get('limit_up_count', 'N/A')} | "
            f"跌停 {snapshot.get('limit_down_count', 'N/A')} | "
            f"指数 {_format_optional(snapshot.get('fear_greed_index'))}"
        )
        if snapshot.get("source"):
            message += f" | 源 {snapshot['source']}"
        progress.emit(message)
        if not progress.enabled:
            print(message)
        for warning in snapshot.get("warnings") or []:
            print(f"[warn] {warning}", file=sys.stderr)
    except Exception as exc:
        session.rollback()
        print(f"[error] 市场情绪同步失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        session.close()


def _format_optional(value: Any) -> str:
    return f"{float(value):.1f}" if value is not None else "N/A"


def run_report_tech(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """离线生成技术面报告。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 技术面报告（离线）…")

    analyzer = TechAnalyzer.from_config(cfg)
    result = analyzer.analyze(code, offline=True)

    if any("无K线缓存" in w for w in result.warnings) or any(
        "无K线缓存" in r for r in result.risk_factors
    ):
        print(f"[error] 未找到 {code} 的 K线缓存，请先运行 sync", file=sys.stderr)
        raise SystemExit(1)

    text = format_tech_report(result, as_json=as_json)
    _emit_report(text, output, progress)


def run_report_value(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
    show_anchor_price: bool = False,
) -> None:
    """离线生成价值面报告。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 价值面报告（离线）…")

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        progress.emit("正在加载本地价值快照…")
        analyzer = ValueAnalyzer.from_config(
            cfg,
            repo=snapshot_repo,
            override_repo=PrototypeOverrideRepo(session),
        )
        result = analyzer.analyze_offline(code)

        if result is None:
            print(f"[error] 未找到 {code} 的价值快照，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        progress.emit("正在运行估值分析…")
        anchor_high = historical_high(code, KlineRepo(session)) if show_anchor_price else None
        text = format_value_report(
            result,
            as_json=as_json,
            show_anchor_price=show_anchor_price,
            anchor_high=anchor_high,
        )
        _emit_report(text, output, progress)
    finally:
        session.close()


def run_report_sentiment(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """严格离线生成市场情绪报告。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        analyzer = SentimentAnalyzer(
            MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
        )
        result = analyzer.analyze_offline(code)
        if result is None:
            print("[error] 未找到市场情绪数据，请先运行 sync market", file=sys.stderr)
            raise SystemExit(1)
        _emit_report(format_sentiment_report(result, as_json=as_json), output)
    finally:
        session.close()


def run_report_dual(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """离线生成红蓝对抗证据分桶（Level 0）。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 红蓝对抗证据分桶（离线）…")

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        progress.emit("正在加载本地快照并跑双轨离线分析…")
        value_analyzer = ValueAnalyzer.from_config(
            cfg,
            repo=snapshot_repo,
            override_repo=PrototypeOverrideRepo(session),
        )
        tech_analyzer = TechAnalyzer.from_config(cfg)
        dual = DualTrackAnalyzer(
            value_analyzer,
            tech_analyzer,
            sentiment_analyzer=SentimentAnalyzer(
                MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
            ),
        )
        report = dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = report.tech_result is None or any(
            "无K线缓存" in w for w in report.tech_result.warnings
        ) or any("无K线缓存" in r for r in report.tech_result.risk_factors)
        if no_value and no_tech:
            print(f"[error] 未找到 {code} 的本地数据，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        buckets = EvidenceBucketer().bucket(report)
        text = format_dual_report(
            code,
            buckets.bull_evidence,
            buckets.bear_evidence,
            analysis_summary=report.analysis_summary,
            as_json=as_json,
            sentiment_result=report.sentiment_result,
            value_result=report.value_result,
            tech_result=report.tech_result,
        )
        _emit_report(text, output, progress)
    finally:
        session.close()


def run_report_confront(
    code: str,
    *,
    narrate: bool = False,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """离线证据分桶 + 可选 LLM 互驳叙事（产品主路径）。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 红蓝对抗报告（离线 Level 0{' + narrate' if narrate else ''}）…")

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        progress.emit("正在加载本地快照并跑双轨离线分析…")
        value_analyzer = ValueAnalyzer.from_config(
            cfg,
            repo=snapshot_repo,
            override_repo=PrototypeOverrideRepo(session),
        )
        tech_analyzer = TechAnalyzer.from_config(cfg)
        dual = DualTrackAnalyzer(
            value_analyzer,
            tech_analyzer,
            sentiment_analyzer=SentimentAnalyzer(
                MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
            ),
        )
        report = dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = report.tech_result is None or any(
            "无K线缓存" in w for w in report.tech_result.warnings
        ) or any("无K线缓存" in r for r in report.tech_result.risk_factors)
        if no_value and no_tech:
            print(f"[error] 未找到 {code} 的本地数据，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        buckets = EvidenceBucketer().bucket(report)
        narrator = ConfrontationNarrator()
        evidence = narrator.build_evidence(
            buckets, code=code, analysis_summary=report.analysis_summary
        )

        narrate_status = NARRATE_SKIPPED
        narrative = None
        narrate_error = None
        from_cache = False
        low_confidence_warning = False

        if narrate:
            progress.emit("正在调用 LLM 生成互驳叙事…")
            cache = LLMNarrateCacheRepo(session)
            outcome = narrator.narrate(
                buckets,
                code=code,
                analysis_summary=report.analysis_summary,
                config=cfg,
                cache=cache,
            )
            from_cache = bool(outcome.result.from_cache)
            low_confidence_warning = bool(outcome.result.low_confidence_warning)
            if outcome.result.ok and outcome.narrative is not None:
                narrate_status = NARRATE_OK
                narrative = outcome.narrative
            else:
                narrate_status = NARRATE_FAILED
                narrate_error = outcome.result.error or "LLM 叙事失败"
                progress.emit(f"叙事失败，仅输出 Level 0：{narrate_error}")

        repo = ConfrontationRepo(session)
        record = repo.save(
            code=code,
            evidence=evidence,
            narrate_status=narrate_status,
            narrative=narrative,
        )
        session.commit()

        text = format_confront_report(
            code=code,
            evidence=evidence,
            narrate_status=narrate_status,
            narrative=narrative,
            confrontation_id=record.id,
            narrate_error=narrate_error,
            from_cache=from_cache,
            low_confidence_warning=low_confidence_warning,
            as_json=as_json,
        )
        _emit_report(text, output, progress)

        if narrate and narrate_status == NARRATE_FAILED:
            raise SystemExit(1)
    finally:
        session.close()


def run_report_persona_stress(
    code: str,
    *,
    narrate: bool = False,
    as_json: bool = False,
    output: str | None = None,
    confrontation_id: int | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """同一 numbered evidence 上的三 persona lens（可选 --narrate）。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(
        f"生成 {code} Persona 压力测试"
        f"（Level 0{' + narrate' if narrate else ''}）…"
    )

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        repo = ConfrontationRepo(session)
        narrator = PersonaStressNarrator()
        existing: ConfrontationRecord | None = None

        if confrontation_id is not None:
            existing = repo.get(confrontation_id)
            if existing is None:
                print(f"[error] confrontation_id={confrontation_id} 不存在", file=sys.stderr)
                raise SystemExit(1)
            if existing.code != code:
                print(
                    f"[error] confrontation_id={confrontation_id} 属于 {existing.code}，"
                    f"与请求代码 {code} 不一致",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            evidence = existing.evidence or {}
            if not evidence.get("bull_evidence") and not evidence.get("bear_evidence"):
                print(
                    f"[error] confrontation_id={confrontation_id} 无可用 evidence",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            progress.emit(f"复用 confrontation_id={confrontation_id} 的 evidence…")
        else:
            snapshot_repo = StockSnapshotRepo(session)
            progress.emit("正在加载本地快照并跑双轨离线分析…")
            value_analyzer = ValueAnalyzer.from_config(
                cfg,
                repo=snapshot_repo,
                override_repo=PrototypeOverrideRepo(session),
            )
            tech_analyzer = TechAnalyzer.from_config(cfg)
            dual = DualTrackAnalyzer(
                value_analyzer,
                tech_analyzer,
                sentiment_analyzer=SentimentAnalyzer(
                    MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
                ),
            )
            report = dual.analyze_offline(code)

            no_value = report.value_result is None
            no_tech = report.tech_result is None or any(
                "无K线缓存" in w for w in report.tech_result.warnings
            ) or any("无K线缓存" in r for r in report.tech_result.risk_factors)
            if no_value and no_tech:
                print(f"[error] 未找到 {code} 的本地数据，请先运行 sync", file=sys.stderr)
                raise SystemExit(1)

            buckets = EvidenceBucketer().bucket(report)
            evidence = narrator.build_evidence(
                buckets, code=code, analysis_summary=report.analysis_summary
            )

        if narrate:
            progress.emit("正在调用 LLM 生成三 persona lens…")
            cache = LLMNarrateCacheRepo(session)
            outcome = narrator.stress(
                evidence,
                config=cfg,
                cache=cache,
            )
            persona_payload = outcome.payload
        else:
            persona_payload = pending_persona_stress()

        if existing is not None:
            record = repo.update_persona_stress(existing.id, persona_payload)
        else:
            record = repo.save(
                code=code,
                evidence=evidence,
                narrate_status=NARRATE_SKIPPED,
                persona_stress=persona_payload,
            )
        session.commit()

        text = format_persona_stress_report(
            code=code,
            evidence=evidence,
            persona_stress=persona_payload,
            confrontation_id=record.id,
            as_json=as_json,
        )
        _emit_report(text, output, progress)
    finally:
        session.close()


def run_report_dashboard(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """离线生成多维看板汇总。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 多维看板（离线）…")

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        progress.emit("正在加载本地快照并聚合看板…")
        value_analyzer = ValueAnalyzer.from_config(
            cfg,
            repo=snapshot_repo,
            override_repo=PrototypeOverrideRepo(session),
        )
        tech_analyzer = TechAnalyzer.from_config(cfg)
        builder = DashboardBuilder(value_analyzer, tech_analyzer, config=cfg)
        try:
            view = builder.build(code)
        except LocalDataMissingError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        text = format_dashboard_report(view, as_json=as_json)
        _emit_report(text, output, progress)
    finally:
        session.close()


def run_report_summary(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    narrate: bool = False,
    config: dict[str, Any] | None = None,
) -> None:
    """综合摘要：默认离线；`--narrate` 时额外调用 LLM 叙事。"""
    cfg = config or load_app_config()
    progress = CliProgress("report", enabled=cli_progress_enabled(cfg))
    progress.emit(f"生成 {code} 综合摘要（离线）…" + (" + LLM 叙事" if narrate else ""))

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        snapshot_repo = StockSnapshotRepo(session)
        progress.emit("正在加载本地快照并跑双轨离线分析…")
        value_analyzer = ValueAnalyzer.from_config(
            cfg,
            repo=snapshot_repo,
            override_repo=PrototypeOverrideRepo(session),
        )
        tech_analyzer = TechAnalyzer.from_config(cfg)
        dual = DualTrackAnalyzer(
            value_analyzer,
            tech_analyzer,
            sentiment_analyzer=SentimentAnalyzer(
                MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
            ),
        )
        report = dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = report.tech_result is None or any(
            "无K线缓存" in w for w in report.tech_result.warnings
        ) or any("无K线缓存" in r for r in report.tech_result.risk_factors)
        if no_value and no_tech:
            print(f"[error] 未找到 {code} 的本地数据，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        buckets = EvidenceBucketer().bucket(report)
        name = ""
        if report.value_result is not None and report.value_result.name:
            name = report.value_result.name
        deterministic = {
            "code": code,
            "name": name or None,
            "analysis_summary": report.analysis_summary,
            "combined_signal": report.combined_signal.value
            if report.combined_signal
            else None,
            "value_rating": report.value_rating.value if report.value_rating else None,
            "bull_evidence_count": len(buckets.bull_evidence),
            "bear_evidence_count": len(buckets.bear_evidence),
        }

        narrative = None
        narrative_error = None
        if narrate:
            progress.emit("正在调用 LLM 生成综合叙事（联网）…")
            cache = LLMNarrateCacheRepo(session)
            result = narrate_comprehensive_report(report, config=cfg, cache=cache)
            session.commit()
            if result.ok and result.data is not None:
                narrative = result.data
            else:
                narrative_error = result.error or "未知错误"

        text = format_summary_report(
            deterministic,
            narrative=narrative,
            narrative_error=narrative_error,
            as_json=as_json,
        )
        _emit_report(text, output, progress)
    finally:
        session.close()


def run_position_set(
    code: str,
    cost_price: float,
    shares: int,
    config: dict[str, Any] | None = None,
) -> None:
    """录入或覆盖一只股票的当前持仓。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        PositionRepo(session).upsert(code, cost_price, shares)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"持仓已录入: {code} | 成本={cost_price:.2f} | 股数={shares}")


def run_trade_record(
    code: str,
    action: str,
    price: float,
    quantity: int,
    *,
    trade_date: str | None = None,
    checklist_id: int | None = None,
    confrontation_id: int | None = None,
    note: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """校验并持久化一条本地交易记录。"""
    normalized_action = action.upper()
    if normalized_action not in {"BUY", "SELL"}:
        print("[error] action 必须为 buy 或 sell", file=sys.stderr)
        raise SystemExit(2)
    if price <= 0:
        print("[error] price 必须大于 0", file=sys.stderr)
        raise SystemExit(2)
    if quantity <= 0:
        print("[error] quantity 必须大于 0", file=sys.stderr)
        raise SystemExit(2)
    if not is_a_share(code):
        print("[error] 仅支持 A 股 6 位股票代码", file=sys.stderr)
        raise SystemExit(2)
    try:
        parsed_date = datetime.fromisoformat(trade_date) if trade_date else datetime.now()
    except ValueError as exc:
        print("[error] date 必须为 ISO 日期，例如 2026-08-01", file=sys.stderr)
        raise SystemExit(2) from exc

    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        if confrontation_id is not None:
            record = ConfrontationRepo(session).get(confrontation_id)
            if record is None:
                print(f"[error] confrontation_id={confrontation_id} 不存在", file=sys.stderr)
                raise SystemExit(2)
            if record.code != code:
                print(
                    f"[warn] confrontation 所属 {record.code} 与交易 {code} 不一致，仍写入关联"
                )
        TradeRecordRepo(session).add(
            TradeRecord(
                code=code,
                action=normalized_action,
                trade_date=parsed_date,
                price=price,
                quantity=quantity,
                checklist_id=checklist_id,
                confrontation_id=confrontation_id,
                note=note,
            )
        )
        session.commit()
    except SystemExit:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"交易已录入: {code} | {normalized_action} | 价格={price:.2f} | 数量={quantity}")


def run_report_trade_review(
    code: str | None = None,
    *,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """严格离线输出全部或单标的交易复盘报告。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        trade_repo = TradeRecordRepo(session)
        records = trade_repo.find_by_code(code) if code else trade_repo.find_all()
        if not records:
            print("[error] 未找到交易记录，请先使用 trade record 录入交易", file=sys.stderr)
            raise SystemExit(1)
        checklist_ids = {record.checklist_id for record in records if record.checklist_id is not None}
        checklists = [
            record
            for record in session.query(ChecklistRecord).filter(ChecklistRecord.id.in_(checklist_ids)).all()
        ] if checklist_ids else []
        confrontation_ids = {
            record.confrontation_id
            for record in records
            if getattr(record, "confrontation_id", None) is not None
        }
        declare_stances: dict[int, str] = {}
        for cid in confrontation_ids:
            crec = ConfrontationRepo(session).get(cid)
            if crec is None or not crec.declaration:
                continue
            stance = crec.declaration.get("stance")
            if stance:
                declare_stances[cid] = str(stance)
        result = TradeReviewAnalyzer().analyze(
            records, checklists=checklists, declare_stances=declare_stances
        )
        _emit_report(format_trade_review_report(result, as_json=as_json), output)
    finally:
        session.close()


def run_report_portfolio(
    code: str | None = None,
    *,
    add_quantity: int | None = None,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """严格离线输出组合集中度，并可纯内存模拟加仓。"""
    if add_quantity is not None and not code:
        print("[error] --add-quantity 必须与 --code 一起使用", file=sys.stderr)
        raise SystemExit(2)
    if add_quantity is not None and add_quantity <= 0:
        print("[error] --add-quantity 必须大于 0", file=sys.stderr)
        raise SystemExit(2)

    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        analyzer = PortfolioAnalyzer(TradeRecordRepo(session), StockSnapshotRepo(session))
        result = (
            analyzer.simulate_add(code, add_quantity)
            if code is not None and add_quantity is not None
            else analyzer.analyze_offline()
        )
        if add_quantity is not None and "以下为模拟计算，不代表任何实际交易操作" not in result.warnings:
            result.warnings.append("以下为模拟计算，不代表任何实际交易操作")
        if not result.positions:
            print("[error] 当前无持仓记录，请先使用 trade record 录入交易", file=sys.stderr)
            raise SystemExit(1)
        if code is not None:
            exposure = analyzer.industry_exposure(code)
            if exposure is not None:
                result.warnings.append(f"{code} 所属行业当前组合暴露度: {exposure:.1%}")
        _emit_report(format_portfolio_report(result, as_json=as_json), output)
    finally:
        session.close()


def run_entry_check(
    code: str,
    as_json: bool = False,
    output: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """严格离线生成无仓位视角入场检查。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        snapshot_repo = StockSnapshotRepo(session)
        dual = DualTrackAnalyzer(
            ValueAnalyzer.from_config(cfg, repo=snapshot_repo),
            TechAnalyzer.from_config(cfg),
            sentiment_analyzer=SentimentAnalyzer(
                MarketSentimentProvider.from_config(cfg, MarketSentimentRepo(session))
            ),
        )
        try:
            view = FreshEntryCheck(dual, PositionRepo(session)).build(code)
        except FreshEntryLocalDataMissingError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        _emit_report(format_entry_check_report(view, as_json=as_json), output)
    finally:
        session.close()


def _prompt_optional_price(label: str) -> float | None:
    """采集可选价格；空值留给校验器输出统一的缺失字段原因。"""
    raw = input(label).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print(f"[warn] {label.rstrip('：:')}格式无效，将按未填写处理")
        return None


def run_checklist_submit(
    code: str,
    action: str | None = None,
    *,
    confrontation_id: int | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """交互式采集、校验并留痕一次 Checklist 提交。"""
    cfg = config or load_app_config()
    print(f"开始填写 {code} 的 Checklist（价值理由至少 2 条；直接回车结束理由输入）")
    if confrontation_id is None:
        print("提示：可用 --confrontation-id 关联红蓝对抗声明（可选）")
    value_reasons: list[str] = []
    while True:
        reason = input(f"请输入第 {len(value_reasons) + 1} 条价值理由：").strip()
        if not reason:
            break
        value_reasons.append(reason)

    submission = ChecklistSubmission(
        code=code,
        action=action,
        value_reasons=value_reasons,
        tech_alignment=input("短期技术面配合情况：").strip() or None,
        sentiment_position=input("当前情绪位置及解读：").strip() or None,
        stop_loss_price=_prompt_optional_price("止损点："),
        take_profit_price=_prompt_optional_price("止盈点："),
    )
    result = ChecklistValidator().validate(submission)

    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        if confrontation_id is not None:
            record = ConfrontationRepo(session).get(confrontation_id)
            if record is None:
                print(f"[error] confrontation_id={confrontation_id} 不存在", file=sys.stderr)
                raise SystemExit(2)
            if record.code != code:
                print(
                    f"[warn] confrontation 所属 {record.code} 与 checklist {code} 不一致，仍写入关联"
                )
        ChecklistRepo(session).save(
            submission, result, confrontation_id=confrontation_id
        )
        session.commit()
    except SystemExit:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if result.passed:
        print("Checklist 提交成功（合规）")
        return

    print("Checklist 提交被拒绝：")
    for reason in result.rejection_reasons:
        print(f"  - {reason}")
    print("本次提交不构成合规 Checklist")


def run_checklist_show(
    code: str,
    as_json: bool = False,
    config: dict[str, Any] | None = None,
) -> None:
    """显示某只股票所有已留痕的 Checklist 提交。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        records = ChecklistRepo(session).list_by_code(code)
        if not records:
            print(f"暂无 {code} 的 Checklist 记录")
            return
        print(format_checklist_records(code, records, as_json=as_json))
    finally:
        session.close()


def _parse_refs_csv(raw: str) -> list[int]:
    if not raw.strip():
        return []
    refs: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        refs.append(int(part))
    return refs


def _prompt_declaration() -> ConfrontationDeclaration:
    print("填写 Confrontation 声明（evidence 引用用逗号分隔序号，如 1,2）")
    stance = input("stance [adopt_bull|adopt_bear|partial|abstain]：").strip()
    adopted_side = input("adopted_side [bull|bear|none]：").strip() or "none"
    rejected_side = input("rejected_side [bull|bear|none]：").strip() or "none"
    adopted_bull = _parse_refs_csv(input("adopted bull refs：").strip())
    adopted_bear = _parse_refs_csv(input("adopted bear refs：").strip())
    rejected_bull = _parse_refs_csv(input("rejected bull refs：").strip())
    rejected_bear = _parse_refs_csv(input("rejected bear refs：").strip())
    rationale = input("rejection_rationale（含 [n] 引用）：").strip()
    uncertainty = input("residual_uncertainty（可空）：").strip()
    confidence_raw = input("confidence [0-1]：").strip() or "0.5"
    from service.guard.models.confrontation_declaration import SideEvidenceRefs

    return ConfrontationDeclaration(
        stance=stance,
        adopted_side=adopted_side,
        rejected_side=rejected_side,
        adopted_evidence_refs=SideEvidenceRefs(bull=adopted_bull, bear=adopted_bear),
        rejected_evidence_refs=SideEvidenceRefs(bull=rejected_bull, bear=rejected_bear),
        rejection_rationale=rationale,
        residual_uncertainty=uncertainty,
        confidence=float(confidence_raw),
    )


def run_confront_declare(
    confrontation_id: int,
    *,
    json_file: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """提交结构化 confrontation 声明。"""
    import json

    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        repo = ConfrontationRepo(session)
        record = repo.get(confrontation_id)
        if record is None:
            print(f"[error] confrontation_id={confrontation_id} 不存在", file=sys.stderr)
            raise SystemExit(2)

        if json_file:
            payload = json.loads(Path(json_file).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                print("[error] --json-file 须为 JSON object", file=sys.stderr)
                raise SystemExit(2)
            declaration = ConfrontationDeclaration.from_dict(payload)
            raw_for_forbidden = payload
        else:
            declaration = _prompt_declaration()
            raw_for_forbidden = declaration.to_dict()

        result = ConfrontationDeclarationValidator().validate(
            raw_for_forbidden,
            evidence=record.evidence or {},
            already_declared=record.declare_status == DECLARE_OK,
        )
        if not result.ok:
            print("Declare 校验失败：", file=sys.stderr)
            for err in result.errors:
                print(f"  - {err}", file=sys.stderr)
            raise SystemExit(1)

        repo.update_declare(confrontation_id, declaration.to_dict(), declare_status=DECLARE_OK)
        session.commit()
        print(f"Declare 已保存：confrontation_id={confrontation_id} stance={declaration.stance}")
    except SystemExit:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_confront_show(
    code: str,
    *,
    as_json: bool = False,
    config: dict[str, Any] | None = None,
) -> None:
    """列出股票的 confrontation / declare 历史。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        records = ConfrontationRepo(session).list_by_code(code)
        print(format_confrontation_history(code, records, as_json=as_json))
    finally:
        session.close()


def run_value_override(
    code: str,
    prototype: str,
    reason: str,
    config: dict[str, Any] | None = None,
) -> None:
    """设置或更新一只股票的估值原型人工覆盖。"""
    cfg = config or load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        PrototypeOverrideRepo(session).upsert(code, prototype, reason)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"已设置 {code} 原型覆盖为 {prototype}")


def run_watchlist_list() -> None:
    stocks = load_watchlist()
    path = watchlist_path()
    if not stocks:
        print(f"常看列表为空（{path}）")
        print("添加：python -m apps.cli watchlist add <代码> [--name 名称]")
        return
    print(f"常看列表（{len(stocks)}）→ {path}")
    for i, s in enumerate(stocks, 1):
        name = s.get("name") or ""
        print(f"  {i}. {s['code']}" + (f"  {name}" if name else ""))


def run_watchlist_add(code: str, name: str | None = None) -> None:
    stocks, created = add_to_watchlist(code, name=name)
    action = "已添加" if created else "已在列表中（已更新名称）" if name else "已在列表中"
    print(f"{action}: {code}" + (f" ({name})" if name else ""))
    print(f"当前共 {len(stocks)} 只 → {watchlist_path()}")
    print("多设备同步：git add config/watchlist.yaml && git commit && git push")


def run_watchlist_remove(code: str) -> None:
    stocks, removed = remove_from_watchlist(code)
    if not removed:
        print(f"[warn] 列表中无此代码: {code}", file=sys.stderr)
        raise SystemExit(1)
    print(f"已移除: {code}")
    print(f"当前共 {len(stocks)} 只 → {watchlist_path()}")


def _emit_report(text: str, output: str | None, progress: CliProgress | None = None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        msg = f"已保存至 {output}"
        if progress and progress.enabled:
            progress.emit(msg)
        else:
            print(msg)
    else:
        print(text)


def _run_for_codes(
    codes: list[str],
    *,
    label: str,
    fn: Callable[..., None],
    batch: bool,
    output: str | None,
    kind: str,
    **kwargs: Any,
) -> None:
    failed: list[str] = []
    for i, code in enumerate(codes, 1):
        if batch and len(codes) > 1:
            print(f"\n======== [{i}/{len(codes)}] {label} {code} ========", flush=True)
        out = (
            _batch_output_path(
                output, code, kind, as_json=bool(kwargs.get("as_json"))
            )
            if batch
            else output
        )
        try:
            fn(code, output=out, **kwargs)
        except SystemExit as exc:
            if exc.code not in (0, None):
                failed.append(code)
                continue
            raise
    if failed:
        print(f"[error] 失败 {len(failed)}/{len(codes)}: {', '.join(failed)}", file=sys.stderr)
        raise SystemExit(1)


def _add_code_or_watchlist(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "code",
        nargs="?",
        default=None,
        help="股票代码，如 600519；与 --watchlist 二选一",
    )
    parser.add_argument(
        "--watchlist",
        action="store_true",
        help="对 config/watchlist.yaml 常看列表批量执行",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps.cli", description="stock_copilot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_parser = sub.add_parser("sync", help="同步数据（联网）；可单票或 --watchlist")
    _add_code_or_watchlist(sync_parser)
    sync_parser.add_argument(
        "--realtime",
        action="store_true",
        help="叠加当日实时报价并持久化当日 K 线",
    )
    sync_parser.add_argument(
        "--quiet",
        action="store_true",
        help="不输出阶段性进度（仅保留最终结果与错误）",
    )

    report_parser = sub.add_parser("report", help="生成离线分析报告")
    report_sub = report_parser.add_subparsers(dest="report_type", required=True)

    def _add_report_common(p: argparse.ArgumentParser) -> None:
        _add_code_or_watchlist(p)
        p.add_argument("--json", action="store_true", help="JSON 输出")
        p.add_argument(
            "--output",
            "-o",
            help="单票：文件路径；--watchlist：输出目录（写入 {code}_*.md / *.json）",
        )
        p.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    _add_report_common(report_sub.add_parser("tech", help="技术面报告"))
    value_report_parser = report_sub.add_parser("value", help="价值面报告")
    _add_report_common(value_report_parser)
    value_report_parser.add_argument(
        "--show-anchor-price",
        action="store_true",
        help="显式展示历史最高价（默认隐藏，以避免形成价格锚点）",
    )
    _add_report_common(
        report_sub.add_parser("dual", help="红蓝对抗证据分桶（离线 Level 0）")
    )
    confront_parser = report_sub.add_parser(
        "confront",
        help="红蓝对抗报告（离线 Level 0；--narrate 联网 LLM 互驳）",
    )
    _add_report_common(confront_parser)
    confront_parser.add_argument(
        "--narrate",
        action="store_true",
        help="显式联网调用 LLM 生成互驳叙事（需配置 llm: 或 LLM_API_KEY）",
    )
    persona_parser = report_sub.add_parser(
        "persona-stress",
        help="Persona 压力测试（同 evidence 三 lens；--narrate 联网）",
    )
    _add_report_common(persona_parser)
    persona_parser.add_argument(
        "--narrate",
        action="store_true",
        help="显式联网调用 LLM 生成三 persona 解读（需配置 llm: 或 LLM_API_KEY）",
    )
    persona_parser.add_argument(
        "--confrontation-id",
        type=int,
        help="挂载到已有 confrontation 记录（复用 evidence，不新建快照）",
    )
    sentiment_report_parser = report_sub.add_parser("sentiment", help="市场情绪报告（严格离线）")
    sentiment_report_parser.add_argument("code", help="股票代码，仅用于报告标识")
    sentiment_report_parser.add_argument("--json", action="store_true", help="JSON 输出")
    sentiment_report_parser.add_argument("--output", "-o", help="输出文件路径")
    sentiment_report_parser.add_argument("--quiet", action="store_true", help="不输出阶段性进度")
    _add_report_common(report_sub.add_parser("dashboard", help="多维看板汇总（离线）"))
    summary_parser = report_sub.add_parser(
        "summary", help="综合摘要（默认离线；--narrate 联网 LLM 叙事）"
    )
    _add_report_common(summary_parser)
    summary_parser.add_argument(
        "--narrate",
        action="store_true",
        help="显式联网调用 LLM 生成综合叙事（需配置 llm: 或 LLM_API_KEY）",
    )
    trade_review_parser = report_sub.add_parser("trade-review", help="交易复盘归因报告（严格离线）")
    trade_review_parser.add_argument("--code", help="仅复盘指定股票代码")
    trade_review_parser.add_argument("--json", action="store_true", help="JSON 输出")
    trade_review_parser.add_argument("--output", "-o", help="输出文件路径")
    trade_review_parser.add_argument("--quiet", action="store_true", help="不输出阶段性进度")
    portfolio_parser = report_sub.add_parser("portfolio", help="持仓组合集中度与行业暴露度（严格离线）")
    portfolio_parser.add_argument("--code", help="目标股票代码；用于查看行业暴露度或模拟加仓")
    portfolio_parser.add_argument("--add-quantity", type=int, help="假设加仓数量，仅做内存模拟")
    portfolio_parser.add_argument("--json", action="store_true", help="JSON 输出")
    portfolio_parser.add_argument("--output", "-o", help="输出文件路径")
    portfolio_parser.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    trade_parser = sub.add_parser("trade", help="录入交易记录")
    trade_sub = trade_parser.add_subparsers(dest="trade_action", required=True)
    trade_record = trade_sub.add_parser("record", help="录入一笔买入或卖出交易")
    trade_record.add_argument("code", help="A 股股票代码")
    trade_record.add_argument("action", help="buy 或 sell（大小写不敏感）")
    trade_record.add_argument("price", type=float, help="成交价格")
    trade_record.add_argument("quantity", type=int, help="成交数量")
    trade_record.add_argument("--date", help="成交日期（ISO 格式，如 2026-08-01）")
    trade_record.add_argument("--checklist-id", type=int, help="关联的 Checklist 记录 ID（软引用）")
    trade_record.add_argument(
        "--confrontation-id",
        type=int,
        help="关联的 confrontation 记录 ID（软引用）",
    )
    trade_record.add_argument("--note", help="备注")

    confront_cmd = sub.add_parser("confront", help="红蓝对抗声明与历史查询")
    confront_sub = confront_cmd.add_subparsers(dest="confront_action", required=True)
    confront_declare = confront_sub.add_parser("declare", help="提交结构化立场声明")
    confront_declare.add_argument("confrontation_id", type=int, help="confrontation 记录 ID")
    confront_declare.add_argument("--json-file", help="从 JSON 文件读取 declare payload")
    confront_show = confront_sub.add_parser("show", help="列出某票 confrontation 历史")
    confront_show.add_argument("code", help="股票代码")
    confront_show.add_argument("--json", action="store_true", help="JSON 输出")

    wl_parser = sub.add_parser("watchlist", help="维护常看股票列表（config/watchlist.yaml）")
    wl_sub = wl_parser.add_subparsers(dest="watchlist_action", required=True)
    wl_sub.add_parser("list", help="列出常看股票")
    add_p = wl_sub.add_parser("add", help="加入常看列表")
    add_p.add_argument("code", help="股票代码")
    add_p.add_argument("--name", help="可选名称")
    rm_p = wl_sub.add_parser("remove", help="从常看列表移除")
    rm_p.add_argument("code", help="股票代码")

    checklist_parser = sub.add_parser("checklist", help="提交或查看决策 Checklist")
    checklist_sub = checklist_parser.add_subparsers(dest="checklist_action", required=True)
    checklist_submit = checklist_sub.add_parser("submit", help="交互式提交 Checklist")
    checklist_submit.add_argument("code", help="股票代码")
    checklist_submit.add_argument("--action", choices=("buy", "sell"), help="交易意图")
    checklist_submit.add_argument(
        "--confrontation-id",
        type=int,
        help="关联的 confrontation 记录 ID（可选软链）",
    )
    checklist_show = checklist_sub.add_parser("show", help="查看 Checklist 历史记录")
    checklist_show.add_argument("code", help="股票代码")
    checklist_show.add_argument("--json", action="store_true", help="JSON 输出")

    position_parser = sub.add_parser("position", help="维护最小持仓记录")
    position_sub = position_parser.add_subparsers(dest="position_action", required=True)
    position_set = position_sub.add_parser("set", help="录入或更新当前持仓")
    position_set.add_argument("code", help="股票代码")
    position_set.add_argument("--cost", type=float, required=True, help="持仓成本价")
    position_set.add_argument("--shares", type=int, required=True, help="持仓股数")

    entry_check = sub.add_parser("entry-check", help="无仓位视角入场检查（严格离线）")
    entry_check.add_argument("code", help="股票代码")
    entry_check.add_argument("--json", action="store_true", help="JSON 输出")
    entry_check.add_argument("--output", "-o", help="输出文件路径")
    entry_check.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    value_parser = sub.add_parser("value", help="管理价值面设置")
    value_sub = value_parser.add_subparsers(dest="value_action", required=True)
    value_override = value_sub.add_parser("override", help="设置股票估值原型人工覆盖")
    value_override.add_argument("code", help="股票代码")
    value_override.add_argument("prototype", choices=list(_PROTOTYPE_METHODS), help="目标估值原型")
    value_override.add_argument("--reason", required=True, help="覆盖原因")

    feishu_parser = sub.add_parser("feishu", help="飞书 dual 推送（经 lark-cli）")
    feishu_sub = feishu_parser.add_subparsers(dest="feishu_action", required=True)
    feishu_push = feishu_sub.add_parser("push", help="生成 dual.md 并经 lark-cli 新建文档+发消息")
    _add_code_or_watchlist(feishu_push)
    feishu_push.add_argument("--dry-run", action="store_true", help="只写本地 dual.md，不调用 lark-cli")
    feishu_push.add_argument("--sync", action="store_true", help="推送前同步（覆盖配置）")
    feishu_push.add_argument("--no-sync", action="store_true", help="推送前不同步（覆盖配置）")
    feishu_push.add_argument("--realtime", action="store_true", help="sync 时叠加实时报价")
    feishu_push.add_argument(
        "--slot",
        help="推送时段 0830/0900/1300/1700；默认 FEISHU_SLOT 或当前 HHmm",
    )
    feishu_push.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    return parser


def _resolve_feishu_slot(explicit: str | None) -> str:
    raw = (explicit or os.environ.get("FEISHU_SLOT") or datetime.now().strftime("%H%M")).strip()
    return raw or datetime.now().strftime("%H%M")


def _quiet_config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(config or {})
    logging_cfg = dict(cfg.get("logging") or {})
    logging_cfg["cli_progress"] = False
    cfg["logging"] = logging_cfg
    return cfg


def _write_dual_md(code: str, dest: Path, config: dict[str, Any] | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_report_dual(code, output=str(dest), as_json=False, config=_quiet_config(config))
    except SystemExit as exc:
        raise RuntimeError(f"report dual 退出码 {exc.code}") from exc


def run_feishu_push_cmd(
    codes: list[str],
    *,
    dry_run: bool = False,
    do_sync: bool | None = None,
    realtime: bool = False,
    slot: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    cfg = config or load_app_config()
    slot_key = _resolve_feishu_slot(slot)
    feishu_cfg = resolve_feishu_config(cfg)

    def _sync(code: str) -> None:
        run_sync(code, realtime=realtime, config=cfg)

    def _write(code: str, dest: Path) -> None:
        _write_dual_md(code, dest, cfg)

    try:
        outcome = run_feishu_push(
            codes,
            config=cfg,
            write_dual=_write,
            reports_dir=reports_root(cfg, _REPO_ROOT),
            slot=slot_key,
            dry_run=dry_run,
            do_sync=do_sync,
            sync_fn=_sync,
            today=datetime.now().date(),
            feishu_cfg=feishu_cfg,
        )
    except FeishuPublisherError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if outcome.skipped:
        print(f"[skip] {outcome.skip_reason}")
        return
    for code, path in outcome.local_paths.items():
        print(f"[ok] {code} 本地 {path}")
    if outcome.failed:
        detail = "; ".join(f"{c}: {err}" for c, err in outcome.failed)
        print(f"[error] 失败 {len(outcome.failed)}/{len(codes)}: {detail}", file=sys.stderr)
        raise SystemExit(1)
    print(
        f"飞书推送完成 {len(outcome.succeeded)}/{len(codes)}"
        + ("（dry-run）" if dry_run else "")
    )


def main(argv: list[str] | None = None) -> None:
    setup_utf8_console()
    args = build_parser().parse_args(argv)

    config_override: dict[str, Any] | None = None
    if getattr(args, "quiet", False):
        config_override = load_app_config()
        config_override.setdefault("logging", {})["cli_progress"] = False

    try:
        if args.command == "feishu":
            if args.feishu_action == "push":
                if args.sync and args.no_sync:
                    print("[error] --sync 与 --no-sync 不能同时使用", file=sys.stderr)
                    raise SystemExit(2)
                if args.sync:
                    do_sync: bool | None = True
                elif args.no_sync:
                    do_sync = False
                else:
                    do_sync = None
                codes = _resolve_target_codes(getattr(args, "code", None), bool(args.watchlist))
                run_feishu_push_cmd(
                    codes,
                    dry_run=bool(args.dry_run),
                    do_sync=do_sync,
                    realtime=bool(args.realtime),
                    slot=args.slot,
                    config=config_override,
                )
            return
        if args.command == "watchlist":
            if args.watchlist_action == "list":
                run_watchlist_list()
            elif args.watchlist_action == "add":
                run_watchlist_add(args.code, name=args.name)
            elif args.watchlist_action == "remove":
                run_watchlist_remove(args.code)
            return
        if args.command == "checklist":
            if args.checklist_action == "submit":
                run_checklist_submit(
                    args.code,
                    action=args.action,
                    confrontation_id=getattr(args, "confrontation_id", None),
                    config=config_override,
                )
            elif args.checklist_action == "show":
                run_checklist_show(args.code, as_json=args.json, config=config_override)
            return
        if args.command == "confront":
            if args.confront_action == "declare":
                run_confront_declare(
                    args.confrontation_id,
                    json_file=args.json_file,
                    config=config_override,
                )
            elif args.confront_action == "show":
                run_confront_show(
                    args.code, as_json=args.json, config=config_override
                )
            return
        if args.command == "position":
            if args.position_action == "set":
                run_position_set(
                    args.code,
                    cost_price=args.cost,
                    shares=args.shares,
                    config=config_override,
                )
            return
        if args.command == "trade":
            if args.trade_action == "record":
                run_trade_record(
                    args.code,
                    args.action,
                    args.price,
                    args.quantity,
                    trade_date=args.date,
                    checklist_id=args.checklist_id,
                    confrontation_id=getattr(args, "confrontation_id", None),
                    note=args.note,
                    config=config_override,
                )
            return
        if args.command == "entry-check":
            run_entry_check(
                args.code,
                as_json=args.json,
                output=args.output,
                config=config_override,
            )
            return
        if args.command == "value":
            if args.value_action == "override":
                run_value_override(
                    args.code,
                    args.prototype,
                    args.reason,
                    config=config_override,
                )
            return
        if args.command == "report" and args.report_type == "trade-review":
            run_report_trade_review(
                args.code,
                as_json=args.json,
                output=args.output,
                config=config_override,
            )
            return
        if args.command == "report" and args.report_type == "portfolio":
            run_report_portfolio(
                args.code,
                add_quantity=args.add_quantity,
                as_json=args.json,
                output=args.output,
                config=config_override,
            )
            return

        if args.command == "sync" and args.code == "market":
            run_sync_market(config=config_override)
            return

        use_wl = bool(getattr(args, "watchlist", False))
        codes = _resolve_target_codes(getattr(args, "code", None), use_wl)

        if args.command == "sync":
            if len(codes) == 1 and not use_wl:
                run_sync(codes[0], realtime=args.realtime, config=config_override)
            else:
                _run_for_codes(
                    codes,
                    label="sync",
                    fn=lambda code, output=None, **kw: run_sync(
                        code, realtime=args.realtime, config=config_override
                    ),
                    batch=True,
                    output=None,
                    kind="sync",
                )
        elif args.command == "report":
            report_fns = {
                "tech": (run_report_tech, "tech"),
                "value": (run_report_value, "value"),
                "dual": (run_report_dual, "dual"),
                "confront": (run_report_confront, "confront"),
                "persona-stress": (run_report_persona_stress, "persona-stress"),
                "sentiment": (run_report_sentiment, "sentiment"),
                "dashboard": (run_report_dashboard, "dashboard"),
                "summary": (run_report_summary, "summary"),
            }
            fn, kind = report_fns[args.report_type]
            extra: dict[str, Any] = {
                "as_json": args.json,
                "config": config_override,
            }
            if args.report_type in ("summary", "confront", "persona-stress"):
                extra["narrate"] = bool(getattr(args, "narrate", False))
            if args.report_type == "persona-stress":
                extra["confrontation_id"] = getattr(args, "confrontation_id", None)
            if args.report_type == "value":
                extra["show_anchor_price"] = bool(args.show_anchor_price)
            if len(codes) == 1 and not use_wl:
                fn(codes[0], output=args.output, **extra)
            else:
                _run_for_codes(
                    codes,
                    label=f"report {args.report_type}",
                    fn=fn,
                    batch=True,
                    output=args.output,
                    kind=kind,
                    **extra,
                )
    except UnsupportedMarketError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KlineUnavailableError as exc:
        print(f"[error] 数据拉取失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
