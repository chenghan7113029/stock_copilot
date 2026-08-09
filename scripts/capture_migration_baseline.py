#!/usr/bin/env python3
"""采集迁移离线基线（strict offline reports → test/fixtures/migration_baseline）。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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

DEFAULT_CODES = ("600519", "601398", "601939")
DEFAULT_KINDS = ("tech", "value", "dual")
SEED_DB = ROOT / "data" / "fixtures" / "stock_copilot_seed.db"
OUT_DIR = ROOT / "test" / "fixtures" / "migration_baseline"


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def run_offline_json(code: str, kind: str, config: dict[str, Any]) -> dict[str, Any]:
    """生成单票离线 JSON（与 CLI report --json 契约对齐的核心字段）。"""
    from apps.formatters import format_dual_report, format_tech_report, format_value_report
    from dao.engine import Base, create_db_engine, ensure_sqlite_schema, make_session_factory
    from dao.kline_repo import KlineRepo
    from dao.chip_distribution_repo import ChipDistributionRepo
    from dao.stock_snapshot_repo import StockSnapshotRepo
    from data_provider.chip_distribution_provider import ChipDistributionProvider
    from data_provider.kline_provider import KlineProvider
    from data_provider.manager import SourceManager
    from data_provider.provider import StockDataProvider
    from service.dual_track.analyzer import DualTrackAnalyzer
    from service.dual_track.evidence_bucketer import EvidenceBucketer
    from service.tech.analyzer import TechAnalyzer
    from service.tech.config import TechAnalysisConfig
    from service.value.analyzer import ValueAnalyzer
    from service.value.valuation.assumptions import AssumptionProvider
    from service.value.valuation.engine import default_engine

    engine = create_db_engine(config)
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = make_session_factory(engine)()
    try:
        # 离线采集：允许空 data_sources，避免实例化任何联网 fetcher
        manager = SourceManager([])
        provider = StockDataProvider(manager, repo=StockSnapshotRepo(session), config=config)
        value_analyzer = ValueAnalyzer(
            provider,
            engine=default_engine(assumptions=AssumptionProvider(config)),
        )
        kline_provider = KlineProvider(KlineRepo(session), kline_fetchers=[])
        chip_provider = ChipDistributionProvider(
            ChipDistributionRepo(session), chip_fetchers=[]
        )
        tech_analyzer = TechAnalyzer(
            kline_provider=kline_provider,
            config=TechAnalysisConfig(kline_days=config.get("tech", {}).get("kline_days", 90)),
            chip_provider=chip_provider,
        )

        if kind == "tech":
            result = tech_analyzer.analyze(code, offline=True)
            return json.loads(format_tech_report(result, as_json=True))
        if kind == "value":
            result = value_analyzer.analyze_offline(code)
            if result is None:
                return {"code": code, "error": "no_value_snapshot"}
            return json.loads(format_value_report(result, as_json=True))
        if kind == "dual":
            report = DualTrackAnalyzer(value_analyzer, tech_analyzer).analyze_offline(code)
            buckets = EvidenceBucketer().bucket(report)
            return json.loads(
                format_dual_report(
                    code,
                    buckets.bull_evidence,
                    buckets.bear_evidence,
                    analysis_summary=report.analysis_summary,
                    as_json=True,
                    sentiment_result=report.sentiment_result,
                )
            )
        raise ValueError(f"unknown kind: {kind}")
    finally:
        session.close()
        engine.dispose()


def capture(
    *,
    codes: tuple[str, ...] = DEFAULT_CODES,
    out_dir: Path = OUT_DIR,
    seed_db: Path = SEED_DB,
) -> Path:
    if not seed_db.is_file():
        raise FileNotFoundError(f"seed DB missing: {seed_db}")

    seed_out = out_dir / "seed"
    seed_out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="migration_baseline_") as tmp:
        tmp_db = Path(tmp) / "stock_copilot_seed_copy.db"
        shutil.copy2(seed_db, tmp_db)
        db_url = "sqlite:///" + tmp_db.resolve().as_posix()
        config = {
            "db": {"url": db_url},
            "data_sources": {"enabled": []},
            "tech": {"kline_days": 90},
            "logging": {"cli_progress": False},
        }

        file_hashes: dict[str, str] = {}
        for code in codes:
            for kind in DEFAULT_KINDS:
                payload = strip_non_deterministic(run_offline_json(code, kind, config))
                name = f"report_{kind}_{code}.json"
                path = seed_out / name
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                file_hashes[name] = stable_hash(payload)
                print(f"wrote {path.relative_to(ROOT)} hash={file_hashes[name][:12]}")

    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "seed_db": str(seed_db.as_posix()),
        "codes": list(codes),
        "kinds": list(DEFAULT_KINDS),
        "file_hashes": file_hashes,
        "float_rel_tol": 1e-6,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", nargs="*", default=list(DEFAULT_CODES))
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--seed-db", type=Path, default=SEED_DB)
    args = parser.parse_args()
    capture(codes=tuple(args.codes), out_dir=args.out_dir, seed_db=args.seed_db)


if __name__ == "__main__":
    main()
