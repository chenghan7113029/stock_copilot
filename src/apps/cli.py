"""stock_copilot CLI：sync / report tech / report value。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from apps.formatters import format_tech_report, format_value_report
from common.cli_progress import CliProgress, cli_progress_enabled
from common.config_loader import load_app_config
from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from common.win_console import setup_utf8_console
from dao.engine import Base, create_db_engine, ensure_sqlite_schema, make_session_factory
from dao.kline_repo import KlineRepo
from dao.models import Kline  # noqa: F401 — register ORM model
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.kline_provider import KlineProvider
from data_provider.provider import StockDataProvider
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
        stock = value_provider.get_stock_data(code, on_progress=progress_cb)

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
        value_provider = StockDataProvider.from_config(cfg, repo=snapshot_repo)
        progress.emit("正在加载本地价值快照…")
        analyzer = ValueAnalyzer(value_provider)
        result = analyzer.analyze_offline(code)

        if result is None:
            print(f"[error] 未找到 {code} 的价值快照，请先运行 sync", file=sys.stderr)
            raise SystemExit(1)

        progress.emit("正在运行估值分析…")
        text = format_value_report(result, as_json=as_json)
        _emit_report(text, output, progress)
    finally:
        session.close()


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps.cli", description="stock_copilot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_parser = sub.add_parser("sync", help="同步单票数据（联网）")
    sync_parser.add_argument("code", help="股票代码，如 600519")
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

    tech_parser = report_sub.add_parser("tech", help="技术面报告")
    tech_parser.add_argument("code", help="股票代码")
    tech_parser.add_argument("--json", action="store_true", help="JSON 输出")
    tech_parser.add_argument("--output", "-o", help="写入文件路径")
    tech_parser.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    value_parser = report_sub.add_parser("value", help="价值面报告")
    value_parser.add_argument("code", help="股票代码")
    value_parser.add_argument("--json", action="store_true", help="JSON 输出")
    value_parser.add_argument("--output", "-o", help="写入文件路径")
    value_parser.add_argument("--quiet", action="store_true", help="不输出阶段性进度")

    return parser


def main(argv: list[str] | None = None) -> None:
    setup_utf8_console()
    args = build_parser().parse_args(argv)

    config_override: dict[str, Any] | None = None
    if getattr(args, "quiet", False):
        config_override = load_app_config()
        config_override.setdefault("logging", {})["cli_progress"] = False

    try:
        if args.command == "sync":
            run_sync(args.code, realtime=args.realtime, config=config_override)
        elif args.command == "report":
            if args.report_type == "tech":
                run_report_tech(
                    args.code, as_json=args.json, output=args.output, config=config_override
                )
            elif args.report_type == "value":
                run_report_value(
                    args.code, as_json=args.json, output=args.output, config=config_override
                )
    except UnsupportedMarketError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KlineUnavailableError as exc:
        print(f"[error] 数据拉取失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
