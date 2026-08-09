#!/usr/bin/env python3
"""对比当前离线报告与 migration baseline（S2 硬门禁）。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from common.migration_baseline import stable_hash, strip_non_deterministic  # noqa: E402

OUT_DIR = ROOT / "test" / "fixtures" / "migration_baseline"
SEED_DB = ROOT / "data" / "fixtures" / "stock_copilot_seed.db"


def _load_capture():
    path = ROOT / "scripts" / "capture_migration_baseline.py"
    spec = importlib.util.spec_from_file_location("capture_migration_baseline", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _diff_values(
    expected: Any,
    actual: Any,
    path: str,
    *,
    rel_tol: float,
    diffs: list[dict[str, Any]],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            diffs.append(
                {"path": path, "reason": "type_mismatch", "expected": expected, "actual": actual}
            )
            return
        exp_keys = set(expected)
        act_keys = set(actual)
        for k in sorted(exp_keys | act_keys):
            p = f"{path}.{k}" if path else k
            if k not in exp_keys:
                diffs.append({"path": p, "reason": "unexpected_key", "actual": actual[k]})
            elif k not in act_keys:
                diffs.append({"path": p, "reason": "missing_key", "expected": expected[k]})
            else:
                _diff_values(expected[k], actual[k], p, rel_tol=rel_tol, diffs=diffs)
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            diffs.append(
                {"path": path, "reason": "type_mismatch", "expected": expected, "actual": actual}
            )
            return
        if len(expected) != len(actual):
            diffs.append(
                {
                    "path": path,
                    "reason": "list_length",
                    "expected": len(expected),
                    "actual": len(actual),
                }
            )
            return
        for i, (e, a) in enumerate(zip(expected, actual)):
            _diff_values(e, a, f"{path}[{i}]", rel_tol=rel_tol, diffs=diffs)
        return

    if _is_number(expected) and _is_number(actual):
        e = float(expected)
        a = float(actual)
        if math.isnan(e) and math.isnan(a):
            return
        denom = max(abs(e), abs(a), 1e-12)
        if abs(e - a) / denom > rel_tol and abs(e - a) > rel_tol:
            diffs.append(
                {
                    "path": path,
                    "reason": "float_drift",
                    "expected": e,
                    "actual": a,
                    "rel_tol": rel_tol,
                }
            )
        return

    if expected != actual:
        diffs.append(
            {"path": path, "reason": "value_mismatch", "expected": expected, "actual": actual}
        )


def compare(
    *,
    baseline_dir: Path = OUT_DIR,
    seed_db: Path = SEED_DB,
    report_path: Path | None = None,
) -> int:
    capture = _load_capture()
    manifest_path = baseline_dir / "manifest.json"
    seed_dir = baseline_dir / "seed"
    if not manifest_path.is_file():
        print(f"[error] missing baseline manifest: {manifest_path}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rel_tol = float(manifest.get("float_rel_tol", 1e-6))
    codes = tuple(manifest.get("codes") or capture.DEFAULT_CODES)
    kinds = tuple(manifest.get("kinds") or capture.DEFAULT_KINDS)

    all_diffs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="migration_compare_") as tmp:
        tmp_db = Path(tmp) / "seed_copy.db"
        shutil.copy2(seed_db, tmp_db)
        db_url = "sqlite:///" + tmp_db.resolve().as_posix()
        config = {
            "db": {"url": db_url},
            "data_sources": {"enabled": []},
            "tech": {"kline_days": 90},
            "logging": {"cli_progress": False},
        }

        for code in codes:
            for kind in kinds:
                name = f"report_{kind}_{code}.json"
                baseline_file = seed_dir / name
                if not baseline_file.is_file():
                    all_diffs.append({"path": name, "reason": "missing_baseline_file"})
                    continue
                expected = json.loads(baseline_file.read_text(encoding="utf-8"))
                actual = strip_non_deterministic(capture.run_offline_json(code, kind, config))
                file_diffs: list[dict[str, Any]] = []
                _diff_values(expected, actual, name, rel_tol=rel_tol, diffs=file_diffs)
                if file_diffs:
                    all_diffs.extend(file_diffs)
                else:
                    print(f"OK {name} hash={stable_hash(actual)[:12]}")

    payload = {
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "baseline_git_sha": manifest.get("git_sha"),
        "diff_count": len(all_diffs),
        "diffs": all_diffs,
    }
    if report_path is None:
        reports = ROOT / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports / f"migration_baseline_diff_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if all_diffs:
        print(f"[FAIL] {len(all_diffs)} diffs → {report_path}", file=sys.stderr)
        for d in all_diffs[:20]:
            print(f"  - {d}", file=sys.stderr)
        if len(all_diffs) > 20:
            print(f"  ... {len(all_diffs) - 20} more", file=sys.stderr)
        return 1

    print(f"[PASS] baseline match → {report_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--seed-db", type=Path, default=SEED_DB)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    raise SystemExit(
        compare(baseline_dir=args.baseline_dir, seed_db=args.seed_db, report_path=args.report)
    )


if __name__ == "__main__":
    main()
