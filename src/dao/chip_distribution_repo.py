"""筹码分布 Repository：SQLite chip_distribution 表 CRUD。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from dao.models import ChipDistribution


class ChipDistributionRepo:
    """筹码分布本地缓存仓库。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def query_latest(self, code: str) -> dict[str, Any] | None:
        row = (
            self._session.query(ChipDistribution)
            .filter(ChipDistribution.code == code)
            .order_by(ChipDistribution.trade_date.desc())
            .first()
        )
        return self._to_dict(row) if row is not None else None

    def query_range(self, code: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        rows = (
            self._session.query(ChipDistribution)
            .filter(
                ChipDistribution.code == code,
                ChipDistribution.trade_date >= start_date,
                ChipDistribution.trade_date <= end_date,
            )
            .order_by(ChipDistribution.trade_date)
            .all()
        )
        return [self._to_dict(row) for row in rows]

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        columns = (
            "winner_ratio",
            "avg_cost",
            "concentration_90",
            "concentration_70",
            "cost_90_low",
            "cost_90_high",
            "cost_70_low",
            "cost_70_high",
        )
        for record in records:
            stmt = sqlite_insert(ChipDistribution).values(
                code=record["code"],
                trade_date=record["trade_date"],
                **{column: record.get(column) for column in columns},
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "trade_date"],
                set_={column: getattr(stmt.excluded, column) for column in columns},
            )
            self._session.execute(stmt)
        self._session.flush()

    @staticmethod
    def _to_dict(row: ChipDistribution) -> dict[str, Any]:
        return {
            "code": row.code,
            "trade_date": row.trade_date,
            "winner_ratio": row.winner_ratio,
            "avg_cost": row.avg_cost,
            "concentration_90": row.concentration_90,
            "concentration_70": row.concentration_70,
            "cost_90_low": row.cost_90_low,
            "cost_90_high": row.cost_90_high,
            "cost_70_low": row.cost_70_low,
            "cost_70_high": row.cost_70_high,
        }
