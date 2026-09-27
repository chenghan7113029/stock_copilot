"""个股两融与主力资金流 Repository：stock_margin_detail / stock_moneyflow CRUD。"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from dao.models import StockMarginDetail, StockMoneyFlow

_MARGIN_COLUMNS = ("rzye", "rqye", "rzrqye", "rzmre", "rzche", "rqyl", "rqmcl")
_MONEYFLOW_COLUMNS = (
    "net_mf_amount",
    "buy_elg_amount",
    "sell_elg_amount",
    "buy_lg_amount",
    "sell_lg_amount",
)


def _upsert_batch(
    session: Session,
    model: Any,
    columns: Sequence[str],
    records: list[dict[str, Any]],
) -> None:
    if not records:
        return
    for record in records:
        stmt = sqlite_insert(model).values(
            code=record["code"],
            trade_date=record["trade_date"],
            **{column: record.get(column) for column in columns},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={column: getattr(stmt.excluded, column) for column in columns},
        )
        session.execute(stmt)
    session.flush()


def _query_latest(session: Session, model: Any, code: str) -> dict[str, Any] | None:
    row = (
        session.query(model)
        .filter(model.code == code)
        .order_by(model.trade_date.desc())
        .first()
    )
    return _to_dict(row) if row is not None else None


def _query_range(
    session: Session, model: Any, code: str, days: int
) -> list[dict[str, Any]]:
    """返回该股最近 ``days`` 个交易日记录，按 trade_date 升序。"""
    if days <= 0:
        return []
    rows = (
        session.query(model)
        .filter(model.code == code)
        .order_by(model.trade_date.desc())
        .limit(days)
        .all()
    )
    return [_to_dict(row) for row in reversed(rows)]


def _to_dict(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"code": row.code, "trade_date": row.trade_date}
    for column in row.__table__.columns:
        name = str(column.name)
        if name in ("code", "trade_date", "id"):
            continue
        data[name] = getattr(row, name)
    return data


class StockMarginDetailRepo:
    """个股两融明细本地缓存仓库（金额单位：元；数量单位：股）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        _upsert_batch(self._session, StockMarginDetail, _MARGIN_COLUMNS, records)

    def query_latest(self, code: str) -> dict[str, Any] | None:
        return _query_latest(self._session, StockMarginDetail, code)

    def query_range(self, code: str, days: int) -> list[dict[str, Any]]:
        return _query_range(self._session, StockMarginDetail, code, days)


class StockMoneyFlowRepo:
    """个股主力资金流本地缓存仓库（金额单位：万元）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        _upsert_batch(self._session, StockMoneyFlow, _MONEYFLOW_COLUMNS, records)

    def query_latest(self, code: str) -> dict[str, Any] | None:
        return _query_latest(self._session, StockMoneyFlow, code)

    def query_range(self, code: str, days: int) -> list[dict[str, Any]]:
        return _query_range(self._session, StockMoneyFlow, code, days)
