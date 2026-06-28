#!/usr/bin/env python
"""CLI 全流程试运行：sync -> report tech -> report value。

默认对三只 A 股样本执行完整流程：
  - 600519 贵州茅台
  - 601398 工商银行
  - 601939 建设银行

Windows 推荐入口（勿直接用 python，可能是商店占位符）：
  py scripts/trial_cli_workflow.py
  scripts\\run_trial.cmd

用法见同目录 trial_cli_workflow.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from common.win_console import setup_utf8_console

setup_utf8_console()
print("trial_cli_workflow: starting...", flush=True)

DEFAULT_STOCKS: list[tuple[str, str]] = [
    ("600519", "贵州茅台"),
    ("601398", "工商银行"),
    ("601939", "建设银行"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI 全流程试运行：数据同步 + 技术面报告 + 价值面报告",
    )
    parser.add_argument(
        "--code", "-c",
        action="append",
        dest="codes",
        metavar="CODE",
        help="指定股票代码（可多次）；默认三只样本股",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="报告输出目录（默认 reports/trial/<时间戳>）",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="跳过 sync，直接基于本地缓存生成报告（须先 sync 过）",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="sync 时叠加当日实时报价（仅 sync 步骤生效）",
    )
    return parser.parse_args()


def _resolve_stocks(codes: list[str] | None) -> list[tuple[str, str]]:
    if not codes:
        return DEFAULT_STOCKS
    known = {c: n for c, n in DEFAULT_STOCKS}
    return [(c.strip(), known.get(c.strip(), c.strip())) for c in codes]


def _run_one(
    code: str,
    name: str,
    output_dir: Path,
    skip_sync: bool,
    realtime: bool,
    config: dict,
) -> bool:
    from apps.cli import run_report_tech, run_report_value, run_sync

    banner = f"[{code}] {name}"
    print(f"\n{'=' * 60}", flush=True)
    print(f"  {banner}", flush=True)
    print(f"{'=' * 60}", flush=True)

    try:
        if not skip_sync:
            print("  [1/3] sync (online)...", flush=True)
            print("        (may take 1-2 min per stock, please wait)", flush=True)
            run_sync(code, realtime=realtime, config=config)
        else:
            print("  [1/3] sync skipped", flush=True)

        tech_path = output_dir / f"{code}_tech.txt"
        value_path = output_dir / f"{code}_value.txt"

        print("  [2/3] report tech (offline)...", flush=True)
        run_report_tech(code, output=str(tech_path), config=config)

        print("  [3/3] report value (offline)...", flush=True)
        run_report_value(code, output=str(value_path), config=config)

        print(f"  OK  reports -> {tech_path.name}, {value_path.name}", flush=True)
        return True
    except SystemExit:
        print(f"  FAIL  {banner}  (see errors above)", file=sys.stderr)
        return False


def main() -> None:
    args = _parse_args()

    if sys.version_info < (3, 10):
        print(f"[ERROR] 需要 Python 3.10+，当前: {sys.version}", file=sys.stderr, flush=True)
        sys.exit(1)

    print("trial_cli_workflow: loading config...", flush=True)
    from common.config_loader import load_app_config

    config = load_app_config()
    stocks = _resolve_stocks(args.codes)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = _REPO_ROOT / "reports" / "trial" / ts
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60, flush=True)
    print("  stock_copilot CLI trial workflow", flush=True)
    print("=" * 60, flush=True)
    print(f"  stocks:     {', '.join(c for c, _ in stocks)}", flush=True)
    print(f"  skip-sync:  {args.skip_sync}", flush=True)
    print(f"  realtime:   {args.realtime}", flush=True)
    print(f"  output-dir: {output_dir}", flush=True)
    print("=" * 60, flush=True)
    ok, fail = 0, 0
    for code, name in stocks:
        if _run_one(code, name, output_dir, args.skip_sync, args.realtime, config):
            ok += 1
        else:
            fail += 1

    print("\n" + "=" * 60)
    print(f"  done: success={ok}, fail={fail}")
    print(f"  reports dir: {output_dir}")
    print("=" * 60 + "\n")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
