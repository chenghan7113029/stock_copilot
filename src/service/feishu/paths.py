"""本地 dual.md 路径。"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def dual_md_path(reports_dir: Path, *, day: date, slot: str, code: str) -> Path:
    slot_key = str(slot).strip() or "0000"
    folder = Path(reports_dir) / "feishu" / day.isoformat() / slot_key
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{code}_dual.md"
