#!/usr/bin/env python
"""Cloud Agent / CI 环境 bootstrap：补齐非 git 资产。

幂等，可重复运行。install 钩子与本地手动均可调用：
    python scripts/cloud_bootstrap.py
    python scripts/cloud_bootstrap.py --check-only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("cloud_bootstrap")

_CONFIG_DIR = _REPO_ROOT / "config"
_APP_YAML = _CONFIG_DIR / "app.yaml"
_APP_EXAMPLE = _CONFIG_DIR / "app.example.yaml"
_DATA_DIR = _REPO_ROOT / "data"
_LIVE_DB = _DATA_DIR / "stock_copilot.db"
_SEED_DB = _DATA_DIR / "fixtures" / "stock_copilot_seed.db"
_STATUS_FILE = _DATA_DIR / "cloud-env.status.json"

_REF_REPOS: dict[str, str] = {
    "FinanceToolkit": "https://github.com/JerBouma/FinanceToolkit",
    "valueinvest": "https://github.com/wangzhe3224/valueinvest",
    "daily_stock_analysis": "https://github.com/ZhuLinsen/daily_stock_analysis",
}


def _ensure_dirs() -> None:
    for d in (_DATA_DIR, _REPO_ROOT / "ref", _REPO_ROOT / "reports", _REPO_ROOT / "log"):
        d.mkdir(parents=True, exist_ok=True)
    (_DATA_DIR / "fixtures").mkdir(parents=True, exist_ok=True)


def _ensure_app_yaml() -> str:
    if not _APP_YAML.exists():
        if not _APP_EXAMPLE.exists():
            raise FileNotFoundError(f"缺少 {_APP_EXAMPLE}")
        shutil.copy(_APP_EXAMPLE, _APP_YAML)
        return "created_from_example"
    return "existing"


def _enable_tushare_if_token() -> bool:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        return False

    try:
        import yaml
    except ImportError:
        logger.warning("缺少 pyyaml，无法自动启用 tushare")
        return False

    with _APP_YAML.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    enabled: list[dict] = config.setdefault("data_sources", {}).setdefault("enabled", [])
    changed = False
    tushare_entry = next(
        (s for s in enabled if str(s.get("name", "")).lower() == "tushare"),
        None,
    )
    if tushare_entry is None:
        enabled.append({"name": "tushare", "priority": 1})
        changed = True
    elif tushare_entry.get("priority") != 1:
        # 有 Token 时提升为最高优先级（阶段 B）
        tushare_entry["priority"] = 1
        changed = True
    if changed:
        with _APP_YAML.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
        return True
    return True


def _db_row_count(db_path: Path) -> int:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return 0
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        total = 0
        for table in ("stock_snapshots", "kline"):
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                total += int(row[0]) if row else 0
            except sqlite3.OperationalError:
                pass
        return total
    finally:
        conn.close()


def _ensure_live_db() -> str:
    if _db_row_count(_LIVE_DB) > 0:
        _migrate_sqlite_schema(_LIVE_DB)
        return "existing"
    if not _SEED_DB.exists():
        return "empty_no_seed"
    shutil.copy(_SEED_DB, _LIVE_DB)
    _migrate_sqlite_schema(_LIVE_DB)
    return "seeded_from_fixture"


def _migrate_sqlite_schema(db_path: Path) -> None:
    """复制 seed 后补齐 ORM 新增列（create_all 不 ALTER 已有表）。"""
    from dao.engine import create_db_engine, ensure_sqlite_schema

    config = {"db": {"url": f"sqlite:///{db_path.as_posix()}"}}
    engine = create_db_engine(config)
    ensure_sqlite_schema(engine)
    engine.dispose()


def _clone_ref_repos() -> dict[str, str]:
    ref_root = _REPO_ROOT / "ref"
    status: dict[str, str] = {}
    for name, url in _REF_REPOS.items():
        target = ref_root / name
        if target.exists() and any(target.iterdir()):
            status[name] = "existing"
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            status[name] = "cloned"
        except subprocess.CalledProcessError as exc:
            logger.warning("clone %s 失败: %s", name, exc.stderr or exc)
            status[name] = "failed"
    return status


def _tushare_available() -> bool:
    try:
        from common.config_loader import load_app_config, verify_tushare_access

        return verify_tushare_access(load_app_config())
    except Exception:
        return False


def run_bootstrap(*, check_only: bool = False) -> dict:
    _ensure_dirs()
    config_status = _ensure_app_yaml()
    tushare_enabled = _enable_tushare_if_token()
    db_status = _ensure_live_db()
    ref_status = {} if check_only else _clone_ref_repos()

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(_REPO_ROOT),
        "config_app_yaml": config_status,
        "tushare_token_present": bool(os.environ.get("TUSHARE_TOKEN", "").strip()),
        "tushare_enabled_in_yaml": tushare_enabled,
        "tushare_access_ok": _tushare_available() if tushare_enabled else False,
        "database": {
            "live_path": str(_LIVE_DB),
            "status": db_status,
            "row_count": _db_row_count(_LIVE_DB),
            "seed_fixture": str(_SEED_DB),
            "seed_exists": _SEED_DB.exists(),
        },
        "ref_repos": ref_status or {n: "skipped_check_only" for n in _REF_REPOS},
        "check_only": check_only,
    }

    _STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    return status


def _print_summary(status: dict) -> None:
    db = status["database"]
    print("=== cloud_bootstrap 完成 ===")
    print(f"  config/app.yaml : {status['config_app_yaml']}")
    print(f"  database        : {db['status']} ({db['row_count']} rows)")
    print(f"  TUSHARE_TOKEN   : {'yes' if status['tushare_token_present'] else 'no'}")
    if status["tushare_token_present"]:
        print(f"  tushare access  : {'ok' if status['tushare_access_ok'] else 'failed'}")
    for name, st in status.get("ref_repos", {}).items():
        print(f"  ref/{name:<22}: {st}")
    print(f"  status file     : {_STATUS_FILE}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Cloud Agent 环境 bootstrap")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="跳过 ref clone，仅检查/补齐 config 与 DB",
    )
    args = parser.parse_args()
    status = run_bootstrap(check_only=args.check_only)
    _print_summary(status)


if __name__ == "__main__":
    main()
