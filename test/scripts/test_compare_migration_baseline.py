"""迁移基线对比门禁。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_compare():
    import importlib.util

    path = ROOT / "scripts" / "compare_migration_baseline.py"
    spec = importlib.util.spec_from_file_location("compare_migration_baseline", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(
    not (ROOT / "test" / "fixtures" / "migration_baseline" / "manifest.json").is_file(),
    reason="migration baseline not captured yet",
)
def test_compare_migration_baseline_passes():
    code = _load_compare().compare()
    assert code == 0


def test_compare_fails_without_as_of(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "report_tech_600519.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "codes": ["600519"],
        "kinds": ["tech"],
        "float_rel_tol": 1e-6,
        "git_sha": "test",
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    seed_db = ROOT / "data" / "fixtures" / "stock_copilot_seed.db"
    if not seed_db.is_file():
        pytest.skip("seed db missing")
    code = _load_compare().compare(baseline_dir=tmp_path, seed_db=seed_db)
    assert code == 2


def test_run_offline_json_stable_under_fake_today(monkeypatch):
    """固定 as_of 时，伪造墙钟不改变 tech 关键字段。"""
    import importlib.util
    import shutil
    import tempfile
    from datetime import date

    seed_db = ROOT / "data" / "fixtures" / "stock_copilot_seed.db"
    if not seed_db.is_file():
        pytest.skip("seed db missing")

    path = ROOT / "scripts" / "capture_migration_baseline.py"
    spec = importlib.util.spec_from_file_location("capture_migration_baseline", path)
    assert spec and spec.loader
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "seed.db"
        shutil.copy2(seed_db, tmp_db)
        config = {
            "db": {"url": "sqlite:///" + tmp_db.resolve().as_posix()},
            "data_sources": {"enabled": []},
            "tech": {"kline_days": 90},
            "logging": {"cli_progress": False},
            "as_of": "2026-08-10",
        }
        a = capture.run_offline_json("600519", "tech", config, as_of="2026-08-10")

        class _FakeDate(date):
            @classmethod
            def today(cls):
                return date(2099, 12, 31)

        monkeypatch.setattr("data_provider.kline_provider.date", _FakeDate)
        b = capture.run_offline_json("600519", "tech", config, as_of="2026-08-10")

    assert a.get("current_price") == b.get("current_price")
    assert a.get("macd_dif") == b.get("macd_dif")
    assert a.get("kline_last_date") == b.get("kline_last_date")
