"""LLM narrate 幂等缓存仓库。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from dao.models import LLMNarrateCache

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LLMNarrateCacheRepo:
    """按 cache_key 读写 narrate 结果。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, cache_key: str) -> dict[str, Any] | None:
        row = self._session.get(LLMNarrateCache, cache_key)
        if row is None:
            return None
        try:
            data = json.loads(row.result_json)
            if isinstance(data, dict):
                return data
        except (TypeError, json.JSONDecodeError):
            logger.warning("llm_narrate_cache 解析失败: %s", cache_key[:16])
        return None

    def set(self, cache_key: str, result: dict[str, Any]) -> None:
        payload = json.dumps(result, ensure_ascii=False, default=str)
        existing = self._session.get(LLMNarrateCache, cache_key)
        if existing is None:
            self._session.add(
                LLMNarrateCache(
                    cache_key=cache_key,
                    result_json=payload,
                    created_at=_utcnow(),
                )
            )
        else:
            existing.result_json = payload
            existing.created_at = _utcnow()
        self._session.flush()
