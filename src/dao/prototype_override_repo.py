"""用户估值原型覆盖记录仓库。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from dao.models import PrototypeOverrideRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PrototypeOverrideRepo:
    """按股票代码读写当前生效的人工原型覆盖。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, code: str, prototype: str, reason: str) -> None:
        """插入或更新覆盖记录，首次创建时间保持不变。"""
        now = _utcnow()
        stmt = (
            sqlite_insert(PrototypeOverrideRecord)
            .values(
                code=code,
                prototype=prototype,
                reason=reason,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "prototype": prototype,
                    "reason": reason,
                    "updated_at": now,
                },
            )
        )
        self._session.execute(stmt)

    def get_by_code(self, code: str) -> PrototypeOverrideRecord | None:
        """返回股票当前生效的人工覆盖记录。"""
        return self._session.get(PrototypeOverrideRecord, code)
