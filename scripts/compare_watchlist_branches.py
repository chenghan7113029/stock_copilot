#!/usr/bin/env python3
"""Watchlist 离线报告对比：当前 HEAD vs origin/main（同一份 SQLite 副本）。

通过各侧 worktree 内 `python -m apps.cli report {tech,value,dual} --json` 生成，
再用 feature 分支的 strip/hash 做稳定对比。

用法（仓库根目录）:
  py scripts/compare_watchlist_branches.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROD_DB = ROOT / "data" / "stock_copilot.db"
WATCHLIST = ROOT / "config" / "watchlist.yaml"
KINDS = ("tech", "value", "dual")


def load_codes() -> list[str]:
    import yaml

    data = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    return [str(s["code"]).zfill(6) for s in data.get("stocks", [])]


def codes_with_data(db: Path) -> set[str]:
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        snap = {r[0] for r in conn.execute("SELECT DISTINCT code FROM stock_snapshots")}
        kline = {r[0] for r in conn.execute("SELECT DISTINCT code FROM kline")}
        return snap | kline
    finally:
        conn.close()


def write_temp_config(tree: Path, db_path: Path, dest: Path) -> None:
    import yaml

    example = tree / "config" / "app.example.yaml"
    local = tree / "config" / "app.yaml"
    src = local if local.is_file() else example
    cfg = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    # Prefer ROOT app.yaml for tokens/logging if tree lacks one
    if not local.is_file() and (ROOT / "config" / "app.yaml").is_file():
        cfg = yaml.safe_load((ROOT / "config" / "app.yaml").read_text(encoding="utf-8")) or cfg
    cfg.setdefault("db", {})["url"] = "sqlite:///" + db_path.resolve().as_posix()
    cfg.setdefault("logging", {})["cli_progress"] = False
    cfg.setdefault("logging", {})["cli_level"] = "ERROR"
    # main 在空 enabled 时 SourceManager 会硬失败；保留至少 baostock 供构造，离线路径仍不联网
    enabled = (cfg.get("data_sources") or {}).get("enabled") or []
    if not enabled:
        cfg["data_sources"] = {"enabled": [{"name": "baostock", "priority": 1}]}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def run_capture_via_cli(tree: Path, db_copy: Path, codes: list[str], out_dir: Path) -> dict[str, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from common.migration_baseline import stable_hash, strip_non_deterministic

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wl_cfg_") as tmp:
        cfg_path = Path(tmp) / "app.yaml"
        write_temp_config(tree, db_copy, cfg_path)
        # CLI loads config/app.yaml relative to CWD; copy into tree/config temporarily
        tree_cfg = tree / "config" / "app.yaml"
        tree_cfg_bak = tree / "config" / "app.yaml.__compare_bak__"
        had_cfg = tree_cfg.is_file()
        if had_cfg:
            shutil.copy2(tree_cfg, tree_cfg_bak)
        shutil.copy2(cfg_path, tree_cfg)
        try:
            hashes: dict[str, str] = {}
            for code in codes:
                for kind in KINDS:
                    name = f"report_{kind}_{code}.json"
                    path = out_dir / name
                    cmd = [
                        sys.executable,
                        "-m",
                        "apps.cli",
                        "report",
                        kind,
                        code,
                        "--json",
                        "-o",
                        str(path),
                    ]
                    env = dict(**{k: v for k, v in __import__("os").environ.items()})
                    env["PYTHONPATH"] = str(tree / "src")
                    env["PYTHONIOENCODING"] = "utf-8"
                    print(f"[{tree.name}] report {kind} {code}…", flush=True)
                    proc = subprocess.run(
                        cmd,
                        cwd=str(tree),
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    if proc.returncode != 0 or not path.is_file():
                        payload = {
                            "code": code,
                            "kind": kind,
                            "error": "cli_failed",
                            "stderr": (proc.stderr or "")[-2000:],
                            "stdout": (proc.stdout or "")[-1000:],
                            "returncode": proc.returncode,
                        }
                        path.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                            + "\n",
                            encoding="utf-8",
                        )
                    else:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload = strip_non_deterministic(payload)
                        path.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                            + "\n",
                            encoding="utf-8",
                        )
                    hashes[name] = stable_hash(payload)
                    print(f"  hash={hashes[name][:12]}", flush=True)
            (out_dir / "_hashes.json").write_text(
                json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return hashes
        finally:
            if had_cfg and tree_cfg_bak.is_file():
                shutil.move(str(tree_cfg_bak), str(tree_cfg))
            elif tree_cfg.is_file() and not had_cfg:
                tree_cfg.unlink()
            if tree_cfg_bak.is_file():
                tree_cfg_bak.unlink(missing_ok=True)


def ensure_main_worktree() -> Path:
    main_wt = Path(tempfile.gettempdir()) / "stock_copilot_main_watchlist_compare"
    if main_wt.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(main_wt)],
            cwd=ROOT,
            check=False,
        )
        if main_wt.exists():
            shutil.rmtree(main_wt, ignore_errors=True)
    subprocess.check_call(["git", "fetch", "origin", "main"], cwd=ROOT)
    subprocess.check_call(
        ["git", "worktree", "add", "--detach", str(main_wt), "origin/main"],
        cwd=ROOT,
    )
    return main_wt


def main() -> int:
    if not PROD_DB.is_file():
        print(f"missing DB: {PROD_DB}", file=sys.stderr)
        return 1

    all_codes = load_codes()
    available = codes_with_data(PROD_DB)
    codes = [c for c in all_codes if c in available]
    missing = [c for c in all_codes if c not in available]
    print(f"watchlist={len(all_codes)} comparable={len(codes)} missing_in_db={missing}")
    if not codes:
        print("no codes with local data", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = ROOT / "reports" / f"watchlist_branch_compare_{stamp}"
    branch_dir = base / "branch"
    main_dir = base / "main"
    base.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wl_db_") as tmp:
        db_copy = Path(tmp) / "stock_copilot.db"
        shutil.copy2(PROD_DB, db_copy)

        branch_sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT)
            .decode()
            .strip()
        )
        branch_hashes = run_capture_via_cli(ROOT, db_copy, codes, branch_dir)

        main_wt = ensure_main_worktree()
        main_sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=main_wt)
            .decode()
            .strip()
        )
        shutil.copy2(PROD_DB, db_copy)
        main_hashes = run_capture_via_cli(main_wt, db_copy, codes, main_dir)

    diffs = []
    for name in sorted(set(branch_hashes) | set(main_hashes)):
        bh = branch_hashes.get(name)
        mh = main_hashes.get(name)
        if bh != mh:
            diffs.append({"file": name, "branch": bh, "main": mh})

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "branch_sha": branch_sha,
        "main_sha": main_sha,
        "codes": codes,
        "missing_in_db": missing,
        "diff_count": len(diffs),
        "diffs": diffs,
        "pass": len(diffs) == 0,
    }
    summary_path = base / "compare_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nsummary → {summary_path}")
    if diffs:
        print(f"[DIFF] {len(diffs)} file(s) differ")
        for d in diffs[:30]:
            print(f"  {d['file']}")
        return 2
    print("[PASS] offline watchlist reports match main vs branch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
