"""本地飞书推送 markdown 路径。"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def feishu_md_path(
    reports_dir: Path,
    *,
    day: date,
    slot: str,
    code: str,
    suffix: str,
) -> Path:
    """``reports/feishu/{date}/{slot}/{code}_{suffix}.md``"""
    slot_key = str(slot).strip() or "0000"
    folder = Path(reports_dir) / "feishu" / day.isoformat() / slot_key
    folder.mkdir(parents=True, exist_ok=True)
    safe_suffix = str(suffix).strip().replace("/", "_").replace("\\", "_") or "report"
    return folder / f"{code}_{safe_suffix}.md"


def dual_md_path(reports_dir: Path, *, day: date, slot: str, code: str) -> Path:
    """兼容旧 dual 路径（``{code}_dual.md``）。"""
    return feishu_md_path(reports_dir, day=day, slot=slot, code=code, suffix="dual")
