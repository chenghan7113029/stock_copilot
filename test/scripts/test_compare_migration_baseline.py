"""迁移基线对比门禁。"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not (ROOT / "test" / "fixtures" / "migration_baseline" / "manifest.json").is_file(),
    reason="migration baseline not captured yet",
)
def test_compare_migration_baseline_passes():
    import importlib.util

    path = ROOT / "scripts" / "compare_migration_baseline.py"
    spec = importlib.util.spec_from_file_location("compare_migration_baseline", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    code = mod.compare()
    assert code == 0
