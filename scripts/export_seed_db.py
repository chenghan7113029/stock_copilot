#!/usr/bin/env python
"""从本地 SQLite 导出 Cloud Agent seed fixture。

仅复制指定股票代码的 stock_snapshots 与 kline 行，供离线 report 使用。

用法：
    py scripts/export_seed_db.py --codes 600519,601398,601939
    py scripts/export_seed_db.py --source data/stock_copilot.db --out data/fixtures/stock_copilot_seed.db
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SOURCE = _REPO_ROOT / "data" / "stock_copilot.db"
_DEFAULT_OUT = _REPO_ROOT / "data" / "fixtures" / "stock_copilot_seed.db"
_TABLES = ("stock_snapshots", "kline")


def _migrate_schema(db_path: Path) -> None:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from dao.engine import create_db_engine, ensure_sqlite_schema

    engine = create_db_engine({"db": {"url": f"sqlite:///{db_path.as_posix()}"}})
    ensure_sqlite_schema(engine)
    engine.dispose()


def _parse_codes(raw: str) -> list[str]:
    return [c.strip() for c in raw.split(",") if c.strip()]


def export_seed_db(source: Path, out: Path, codes: list[str]) -> None:
    if not source.exists():
        print(f"[error] 源库不存在: {source}", file=sys.stderr)
        print("请先运行 sync 或 fetch_value_data.py 采集数据。", file=sys.stderr)
        raise SystemExit(1)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    shutil.copy(source, out)
    conn = sqlite3.connect(out)
    try:
        placeholders = ",".join("?" * len(codes))
        for table in _TABLES:
            try:
                conn.execute(
                    f"DELETE FROM {table} WHERE code NOT IN ({placeholders})",
                    codes,
                )
            except sqlite3.OperationalError as exc:
                print(f"[warn] 表 {table}: {exc}", file=sys.stderr)
        conn.commit()

        counts = {}
        for table in _TABLES:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = row[0] if row else 0
            except sqlite3.OperationalError:
                counts[table] = 0

        if counts.get("stock_snapshots", 0) == 0 and counts.get("kline", 0) == 0:
            out.unlink(missing_ok=True)
            print("[error] 导出后无数据，请确认源库含指定代码的快照/K线。", file=sys.stderr)
            raise SystemExit(1)

        _migrate_schema(out)

        print(f"已导出 seed DB: {out}")
        for table, n in counts.items():
            print(f"  {table}: {n} rows")
        print(f"  codes: {', '.join(codes)}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 Cloud Agent seed SQLite fixture")
    parser.add_argument(
        "--source",
        type=Path,
        default=_DEFAULT_SOURCE,
        help=f"源数据库（默认 {_DEFAULT_SOURCE}）",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"输出路径（默认 {_DEFAULT_OUT}）",
    )
    parser.add_argument(
        "--codes",
        default="600519,601398,601939",
        help="逗号分隔股票代码",
    )
    args = parser.parse_args()
    export_seed_db(args.source, args.out, _parse_codes(args.codes))


if __name__ == "__main__":
    main()
