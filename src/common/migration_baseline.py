"""迁移基线：离线报告规范化与采集辅助。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


DROP_KEYS = {
    "data_timestamp",
    "analyzed_at",
    "generated_at",
    "fetched_at",
    "report_path",
    "absolute_path",
}


def strip_non_deterministic(obj: Any) -> Any:
    """剔除易漂移字段，便于 S2 对比。"""
    if isinstance(obj, dict):
        return {
            k: strip_non_deterministic(v)
            for k, v in obj.items()
            if k not in DROP_KEYS and not str(k).endswith("_path")
        }
    if isinstance(obj, list):
        return [strip_non_deterministic(x) for x in obj]
    return obj


def stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
