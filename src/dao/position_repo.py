"""最小持仓记录 Repository。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from dao.models import PositionRecord


class PositionRepo:
    """按股票代码维护一条当前持仓记录。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, code: str, cost_price: float, shares: int) -> None:
        record = self.get_by_code(code)
        if record is None:
            self._session.add(
                PositionRecord(code=code, cost_price=cost_price, shares=shares)
            )
            return

        record.cost_price = cost_price
        record.shares = shares

    def get_by_code(self, code: str) -> PositionRecord | None:
        return self._session.scalar(
            select(PositionRecord).where(PositionRecord.code == code)
        )
