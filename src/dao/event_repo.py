"""治理事件与北向资金 Repository：5 张治理事件表 + northbound_flow。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from dao.models import (
    BlockTrade,
    HolderTrade,
    NorthboundFlow,
    PledgeStat,
    Repurchase,
    ShareFloat,
)


class _EventRepo:
    """治理事件表通用仓库：按 code 全量刷新 + 按事件日期查询。"""

    _model: Any = None
    _date_field: str = "ann_date"
    _columns: tuple[str, ...] = ()

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        code = records[0]["code"]
        self._session.query(self._model).filter(self._model.code == code).delete()
        for record in records:
            values: dict[str, Any] = {
                "code": record["code"],
                self._date_field: record.get(self._date_field),
            }
            for column in self._columns:
                values[column] = record.get(column)
            self._session.add(self._model(**values))
        self._session.flush()

    def query_latest(self, code: str) -> dict[str, Any] | None:
        row = (
            self._session.query(self._model)
            .filter(self._model.code == code)
            .order_by(getattr(self._model, self._date_field).desc())
            .first()
        )
        return self._to_dict(row) if row is not None else None

    def query_range(self, code: str, days: int) -> list[dict[str, Any]]:
        """返回该股最近 ``days`` 条事件，按事件日期升序。"""
        if days <= 0:
            return []
        rows = (
            self._session.query(self._model)
            .filter(self._model.code == code)
            .order_by(getattr(self._model, self._date_field).desc())
            .limit(days)
            .all()
        )
        return [self._to_dict(row) for row in reversed(rows)]

    @staticmethod
    def _to_dict(row: Any) -> dict[str, Any]:
        data: dict[str, Any] = {"code": row.code}
        for column in row.__table__.columns:
            name = str(column.name)
            if name in ("code", "id"):
                continue
            data[name] = getattr(row, name)
        return data


class HolderTradeRepo(_EventRepo):
    _model = HolderTrade
    _date_field = "ann_date"
    _columns = ("holder_name", "holder_type", "in_de", "change_vol", "change_ratio")


class RepurchaseRepo(_EventRepo):
    _model = Repurchase
    _date_field = "ann_date"
    _columns = ("proc", "vol", "amount")


class ShareFloatRepo(_EventRepo):
    _model = ShareFloat
    _date_field = "float_date"
    _columns = ("ann_date", "float_share", "float_ratio")


class PledgeStatRepo(_EventRepo):
    _model = PledgeStat
    _date_field = "end_date"
    _columns = ("pledge_ratio", "unrest_pledge", "total_share")


class BlockTradeRepo(_EventRepo):
    _model = BlockTrade
    _date_field = "trade_date"
    _columns = ("price", "vol", "amount", "discount")


class NorthboundFlowRepo:
    """北向资金市场级日度缓存仓库。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        dates = [r["trade_date"] for r in records]
        self._session.query(NorthboundFlow).filter(
            NorthboundFlow.trade_date.in_(dates)
        ).delete()
        for record in records:
            self._session.add(
                NorthboundFlow(
                    trade_date=record["trade_date"],
                    north_money=record.get("north_money"),
                    south_money=record.get("south_money"),
                )
            )
        self._session.flush()

    def query_northbound(self, days: int) -> list[dict[str, Any]]:
        """返回最近 ``days`` 个交易日的北向资金记录，按 trade_date 升序。"""
        if days <= 0:
            return []
        rows = (
            self._session.query(NorthboundFlow)
            .order_by(NorthboundFlow.trade_date.desc())
            .limit(days)
            .all()
        )
        return [
            {
                "trade_date": row.trade_date,
                "north_money": row.north_money,
                "south_money": row.south_money,
                "fetched_at": row.fetched_at,
            }
            for row in reversed(rows)
        ]
