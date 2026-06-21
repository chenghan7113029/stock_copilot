"""K 线 Repository：SQLite kline 表 CRUD。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from dao.models import Kline

logger = logging.getLogger(__name__)


class KlineRepo:
    """日 K 线本地缓存仓库。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def query_range(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """查询指定 code 在 [start_date, end_date] 内的 K 线记录。"""
        rows = (
            self._session.query(Kline)
            .filter(
                Kline.code == code,
                Kline.trade_date >= start_date,
                Kline.trade_date <= end_date,
            )
            .order_by(Kline.trade_date)
            .all()
        )
        return [self._to_dict(row) for row in rows]

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        """批量 upsert K 线记录（code + trade_date 唯一键）。"""
        if not records:
            return
        for record in records:
            stmt = sqlite_insert(Kline).values(
                code=record["code"],
                trade_date=record["trade_date"],
                open=record.get("open"),
                high=record.get("high"),
                low=record.get("low"),
                close=record.get("close"),
                volume=record.get("volume"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "trade_date"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            self._session.execute(stmt)
        self._session.flush()

    @staticmethod
    def _to_dict(row: Kline) -> dict[str, Any]:
        return {
            "code": row.code,
            "trade_date": row.trade_date,
            "date": row.trade_date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
