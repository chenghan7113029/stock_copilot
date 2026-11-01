"""龙虎榜 Repository：stock_top_list / stock_top_inst / top_list_sync_marker。

写入语义：top_list 与 top_inst 都是**市场级日快照**，按交易日整日替换
（先删该日、再批量插入），因此重复同步幂等、且不受源端同股同日多行影响。
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session

from dao.models import StockTopInst, StockTopList, TopListSyncMarker

_TOP_LIST_COLUMNS = (
    "name",
    "close",
    "pct_change",
    "turnover_rate",
    "amount",
    "l_sell",
    "l_buy",
    "l_amount",
    "net_amount",
    "net_rate",
    "amount_rate",
    "float_values",
)
_TOP_INST_COLUMNS = (
    "side",
    "exalter",
    "buy",
    "buy_rate",
    "sell",
    "sell_rate",
    "net_buy",
    "reason",
)


def _to_dict(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        name = str(column.name)
        if name == "id":
            continue
        data[name] = getattr(row, name)
    return data


class StockTopListRepo:
    """龙虎榜每日明细本地缓存仓库（金额单位：元）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_day(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        """整日替换写入；返回写入行数。空 records 视为清空该日。"""
        self._session.query(StockTopList).filter(
            StockTopList.trade_date == trade_date
        ).delete(synchronize_session=False)
        count = 0
        for record in records:
            values: dict[str, Any] = {
                "code": record["code"],
                "trade_date": record.get("trade_date", trade_date),
                "reason": record["reason"],
            }
            for column in _TOP_LIST_COLUMNS:
                values[column] = record.get(column)
            self._session.add(StockTopList(**values))
            count += 1
        self._session.flush()
        return count

    def upsert_batch(self, records: Iterable[dict[str, Any]]) -> None:
        """按记录的 trade_date 分组整日替换（重复调用幂等）。"""
        by_date: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_date.setdefault(str(record["trade_date"])[:10], []).append(record)
        for trade_date, day_records in by_date.items():
            self.replace_day(trade_date, day_records)

    def query_range(self, code: str, since_date: str) -> list[dict[str, Any]]:
        """返回该股 ``since_date`` 之后的全部上榜事件，按交易日/理由升序。"""
        rows = (
            self._session.query(StockTopList)
            .filter(StockTopList.code == code, StockTopList.trade_date >= since_date)
            .order_by(
                StockTopList.trade_date.asc(),
                StockTopList.reason.asc(),
            )
            .all()
        )
        return [_to_dict(row) for row in rows]

    def count_distinct_trade_dates(self, code: str, since_date: str) -> int:
        rows = (
            self._session.query(StockTopList.trade_date)
            .filter(StockTopList.code == code, StockTopList.trade_date >= since_date)
            .distinct()
            .all()
        )
        return len(rows)

    def count_day_rows(self, trade_date: str) -> int:
        return (
            self._session.query(StockTopList)
            .filter(StockTopList.trade_date == trade_date)
            .count()
        )


class StockTopInstRepo:
    """龙虎榜席位明细本地缓存仓库（金额单位：元）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_day(self, trade_date: str, records: list[dict[str, Any]]) -> int:
        self._session.query(StockTopInst).filter(
            StockTopInst.trade_date == trade_date
        ).delete(synchronize_session=False)
        count = 0
        for record in records:
            values: dict[str, Any] = {
                "code": record["code"],
                "trade_date": record.get("trade_date", trade_date),
            }
            for column in _TOP_INST_COLUMNS:
                values[column] = record.get(column)
            self._session.add(StockTopInst(**values))
            count += 1
        self._session.flush()
        return count

    def upsert_batch(self, records: Iterable[dict[str, Any]]) -> None:
        by_date: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_date.setdefault(str(record["trade_date"])[:10], []).append(record)
        for trade_date, day_records in by_date.items():
            self.replace_day(trade_date, day_records)

    def query_range(self, code: str, since_date: str) -> list[dict[str, Any]]:
        rows = (
            self._session.query(StockTopInst)
            .filter(StockTopInst.code == code, StockTopInst.trade_date >= since_date)
            .order_by(StockTopInst.trade_date.asc(), StockTopInst.id.asc())
            .all()
        )
        return [_to_dict(row) for row in rows]

    def count_day_rows(self, trade_date: str) -> int:
        return (
            self._session.query(StockTopInst)
            .filter(StockTopInst.trade_date == trade_date)
            .count()
        )

    def delete_day(self, trade_date: str) -> int:
        return (
            self._session.query(StockTopInst)
            .filter(StockTopInst.trade_date == trade_date)
            .delete(synchronize_session=False)
        )


class TopListSyncMarkerRepo:
    """龙虎榜交易日覆盖水位仓库。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def mark(self, trade_date: str, source: str | None = "tushare") -> None:
        """写入水位标记；已存在则更新 source/fetched_at（幂等）。"""
        existing = (
            self._session.query(TopListSyncMarker)
            .filter(TopListSyncMarker.trade_date == trade_date)
            .first()
        )
        if existing is None:
            self._session.add(
                TopListSyncMarker(trade_date=trade_date, source=source)
            )
        else:
            existing.source = source
        self._session.flush()

    def has(self, trade_date: str) -> bool:
        return (
            self._session.query(TopListSyncMarker)
            .filter(TopListSyncMarker.trade_date == trade_date)
            .first()
            is not None
        )

    def covered_dates(self, since_date: str) -> list[str]:
        rows = (
            self._session.query(TopListSyncMarker.trade_date)
            .filter(TopListSyncMarker.trade_date >= since_date)
            .order_by(TopListSyncMarker.trade_date.asc())
            .all()
        )
        return [str(row[0]) for row in rows]

    def count(self) -> int:
        return self._session.query(TopListSyncMarker).count()
