"""Checklist 提交记录仓库。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from dao.models import ChecklistRecord
from service.guard.models.checklist import ChecklistSubmission, ChecklistValidationResult


class ChecklistRepo:
    """读写 Checklist 审计记录，并在 ORM 边界处理 JSON 数组。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        submission: ChecklistSubmission,
        result: ChecklistValidationResult,
        *,
        confrontation_id: int | None = None,
    ) -> None:
        self._session.add(
            ChecklistRecord(
                code=submission.code,
                action=submission.action,
                value_reasons_json=json.dumps(submission.value_reasons, ensure_ascii=False),
                tech_alignment=submission.tech_alignment,
                sentiment_position=submission.sentiment_position,
                stop_loss_price=submission.stop_loss_price,
                take_profit_price=submission.take_profit_price,
                passed=result.passed,
                rejection_reasons_json=json.dumps(result.rejection_reasons, ensure_ascii=False),
                confrontation_id=confrontation_id,
            )
        )
        self._session.flush()

    def list_by_code(self, code: str) -> list[ChecklistRecord]:
        records = self._session.scalars(
            select(ChecklistRecord)
            .where(ChecklistRecord.code == code)
            .order_by(ChecklistRecord.created_at.desc(), ChecklistRecord.id.desc())
        ).all()
        for record in records:
            record.value_reasons = self._load_json_array(record.value_reasons_json)
            record.rejection_reasons = self._load_json_array(record.rejection_reasons_json)
        return records

    @staticmethod
    def _load_json_array(payload: str) -> list[str]:
        try:
            data = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) and all(isinstance(item, str) for item in data) else []
