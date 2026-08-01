"""stock_copilot CLI：sync / report / watchlist。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

from apps.formatters import (
    format_dashboard_report,
    format_dual_report,
    format_summary_report,
    format_tech_report,
    format_value_report,
)
from common.cli_progress import CliProgress, cli_progress_enabled
from common.config_loader import load_app_config
from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from common.watchlist import (
    add_to_watchlist,
    load_watchlist,
    remove_from_watchlist,
    watchlist_codes,
    watchlist_path,
)
from common.win_console import setup_utf8_console
from dao.engine import Base, create_db_engine, ensure_sqlite_schema, make_session_factory
from dao.kline_repo import KlineRepo
from dao.llm_narrate_cache_repo import LLMNarrateCacheRepo
from dao.models import Kline  # noqa: F401 — register ORM model
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.kline_provider import KlineProvider
from data_provider.provider import StockDataProvider
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.evidence_bucketer import EvidenceBucketer
from service.report.comprehensive_narrator import narrate_comprehensive_report
from service.report.dashboard_builder import DashboardBuilder, LocalDataMissingError
from service.tech.analyzer import TechAnalyzer
from service.value.analyzer import ValueAnalyzer


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


def _batch_output_path(output: str | None, code: str, kind: str) -> str | None:
    """批量模式下将 -o 视为目录，写入 {code}_{kind}.txt|.json。"""
    if not output:
        return None
    out = Path(output)
    # 单文件后缀误传时仍落到父目录
    if out.suffix.lower() in {".txt", ".json", ".md"}:
        out = out.parent if out.parent != Path("") else Path(".")
    out.mkdir(parents=True, exist_ok=True)
    return str(out / f"{code}_{kind}.txt")


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
        kline_provider = KlineProvider(kline_repo)
        df, kline_warnings, quote_mode = kline_provider.get_kline(
            code,
            days=cfg.get("tech", {}).get("kline_days", 90),
            use_realtime=realtime,
            persist_today=realtime,
            on_progress=progress_cb,
        )

        progress.emit("正在提交数据库事务…")
        session.commit()

        kline_status = f"K线 {len(df)}行 OK"
        if realtime:
            kline_status += f" (quote_mode: {quote_mode})"
        for w in kline_warnings:
            if "realtime" in w.lower() or "overlay" in w.lower() or "降级" in w:
                print(f"[warn] {w}", file=sys.stderr)

        progress.emit(f"完成：value snapshot OK | {kline_status}")
    except Exception as exc:
        session.rollback()
        print(f"[error] 数据拉取失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        session.close()


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

    if any("无缓存" in w for w in result.warnings) or any(
        "无缓存" in r for r in result.risk_factors
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
        analyzer = ValueAnalyzer.from_config(cfg, repo=snapshot_repo)
        result = analyzer.analyze_offline(code)

        if result is None:
            print(f"[error] 未找到 {code} 的价值快照，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        progress.emit("正在运行估值分析…")
        text = format_value_report(result, as_json=as_json)
        _emit_report(text, output, progress)
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
        value_analyzer = ValueAnalyzer.from_config(cfg, repo=snapshot_repo)
        tech_analyzer = TechAnalyzer.from_config(cfg)
        dual = DualTrackAnalyzer(value_analyzer, tech_analyzer)
        report = dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = report.tech_result is None or any(
            "无缓存" in w for w in report.tech_result.warnings
        ) or any("无缓存" in r for r in report.tech_result.risk_factors)
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
        value_analyzer = ValueAnalyzer.from_config(cfg, repo=snapshot_repo)
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
        value_analyzer = ValueAnalyzer.from_config(cfg, repo=snapshot_repo)
        tech_analyzer = TechAnalyzer.from_config(cfg)
        dual = DualTrackAnalyzer(value_analyzer, tech_analyzer)
        report = dual.analyze_offline(code)

        no_value = report.value_result is None
        no_tech = report.tech_result is None or any(
            "无缓存" in w for w in report.tech_result.warnings
        ) or any("无缓存" in r for r in report.tech_result.risk_factors)
        if no_value and no_tech:
            print(f"[error] 未找到 {code} 的本地数据，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        buckets = EvidenceBucketer().bucket(report)
        deterministic = {
            "code": code,
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
        out = _batch_output_path(output, code, kind) if batch else output
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
            help="单票：文件路径；--watchlist：输出目录（写入 {code}_*.txt）",
        )
        p.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    _add_report_common(report_sub.add_parser("tech", help="技术面报告"))
    _add_report_common(report_sub.add_parser("value", help="价值面报告"))
    _add_report_common(
        report_sub.add_parser("dual", help="红蓝对抗证据分桶（离线 Level 0）")
    )
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

    wl_parser = sub.add_parser("watchlist", help="维护常看股票列表（config/watchlist.yaml）")
    wl_sub = wl_parser.add_subparsers(dest="watchlist_action", required=True)
    wl_sub.add_parser("list", help="列出常看股票")
    add_p = wl_sub.add_parser("add", help="加入常看列表")
    add_p.add_argument("code", help="股票代码")
    add_p.add_argument("--name", help="可选名称")
    rm_p = wl_sub.add_parser("remove", help="从常看列表移除")
    rm_p.add_argument("code", help="股票代码")

    return parser


def main(argv: list[str] | None = None) -> None:
    setup_utf8_console()
    args = build_parser().parse_args(argv)

    config_override: dict[str, Any] | None = None
    if getattr(args, "quiet", False):
        config_override = load_app_config()
        config_override.setdefault("logging", {})["cli_progress"] = False

    try:
        if args.command == "watchlist":
            if args.watchlist_action == "list":
                run_watchlist_list()
            elif args.watchlist_action == "add":
                run_watchlist_add(args.code, name=args.name)
            elif args.watchlist_action == "remove":
                run_watchlist_remove(args.code)
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
                "dashboard": (run_report_dashboard, "dashboard"),
                "summary": (run_report_summary, "summary"),
            }
            fn, kind = report_fns[args.report_type]
            extra: dict[str, Any] = {
                "as_json": args.json,
                "config": config_override,
            }
            if args.report_type == "summary":
                extra["narrate"] = bool(getattr(args, "narrate", False))
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
