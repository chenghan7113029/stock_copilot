"""ConfrontationRecord 仓库。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from dao.models import ConfrontationRecord

NARRATE_OK = "ok"
NARRATE_SKIPPED = "skipped"
NARRATE_FAILED = "failed"


class ConfrontationRepo:
    """读写红蓝对抗会话记录。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        code: str,
        evidence: dict[str, Any],
        narrate_status: str,
        narrative: dict[str, Any] | None = None,
    ) -> ConfrontationRecord:
        record = ConfrontationRecord(
            code=code,
            evidence_json=json.dumps(evidence, ensure_ascii=False, default=str),
            narrative_json=(
                json.dumps(narrative, ensure_ascii=False, default=str) if narrative else None
            ),
            narrate_status=narrate_status,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, record_id: int) -> ConfrontationRecord | None:
        record = self._session.get(ConfrontationRecord, record_id)
        if record is not None:
            self._hydrate(record)
        return record

    def list_by_code(self, code: str) -> list[ConfrontationRecord]:
        records = list(
            self._session.scalars(
                select(ConfrontationRecord)
                .where(ConfrontationRecord.code == code)
                .order_by(ConfrontationRecord.created_at.desc(), ConfrontationRecord.id.desc())
            ).all()
        )
        for record in records:
            self._hydrate(record)
        return records

    @staticmethod
    def _hydrate(record: ConfrontationRecord) -> None:
        record.evidence = ConfrontationRepo._load_json(record.evidence_json) or {}
        record.narrative = ConfrontationRepo._load_json(record.narrative_json)

    @staticmethod
    def _load_json(payload: str | None) -> dict[str, Any] | None:
        if not payload:
            return None
        try:
            data = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None
