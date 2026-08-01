"""TradeRecord 持久化仓库。"""

from __future__ import annotations

from collections import deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from dao.models import TradeRecord


class TradeRecordRepo:
    """读写交易记录，并按 FIFO 计算剩余未平仓买入批次。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: TradeRecord) -> None:
        self._session.add(record)
        self._session.flush()

    def find_by_code(self, code: str) -> list[TradeRecord]:
        return self._session.scalars(
            select(TradeRecord)
            .where(TradeRecord.code == code)
            .order_by(TradeRecord.trade_date.asc(), TradeRecord.id.asc())
        ).all()

    def find_all(self) -> list[TradeRecord]:
        return self._session.scalars(
            select(TradeRecord).order_by(TradeRecord.trade_date.asc(), TradeRecord.id.asc())
        ).all()

    def find_open_positions(self, code: str | None = None) -> list[TradeRecord]:
        """返回 FIFO 剩余 BUY 批次；每条记录的 ``quantity`` 为剩余数量。

        这是组合分析等消费者的只读输入契约：可选 ``code`` 过滤，
        返回的记录不带持久化主键，调用方须按 ``code`` 汇总数量。
        """
        records = self.find_by_code(code) if code else self.find_all()
        by_code: dict[str, deque[tuple[TradeRecord, int]]] = {}
        for record in records:
            lots = by_code.setdefault(record.code, deque())
            if record.action == "BUY":
                lots.append((record, record.quantity))
                continue
            remaining = record.quantity
            while remaining and lots:
                buy, available = lots[0]
                matched = min(remaining, available)
                remaining -= matched
                available -= matched
                if available:
                    lots[0] = (buy, available)
                else:
                    lots.popleft()

        positions: list[TradeRecord] = []
        for lots in by_code.values():
            for buy, remaining in lots:
                positions.append(
                    TradeRecord(
                        code=buy.code,
                        action=buy.action,
                        trade_date=buy.trade_date,
                        price=buy.price,
                        quantity=remaining,
                        checklist_id=buy.checklist_id,
                        note=buy.note,
                        created_at=buy.created_at,
                    )
                )
        return positions
