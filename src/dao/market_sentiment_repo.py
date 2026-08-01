"""市场级情绪快照的持久化仓库。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from dao.models import MarketSentimentSnapshot


class MarketSentimentRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, snapshot_data: dict[str, Any]) -> MarketSentimentSnapshot:
        trade_date = snapshot_data["trade_date"]
        row = self.get_by_date(trade_date)
        if row is None:
            row = MarketSentimentSnapshot(trade_date=trade_date)
            self._session.add(row)

        for field in (
            "limit_up_count",
            "limit_down_count",
            "up_count",
            "down_count",
            "margin_balance_change_pct",
            "turnover_percentile",
            "fear_greed_index",
        ):
            setattr(row, field, snapshot_data.get(field))
        self._session.flush()
        return row

    def get_latest(self) -> MarketSentimentSnapshot | None:
        return (
            self._session.query(MarketSentimentSnapshot)
            .order_by(MarketSentimentSnapshot.trade_date.desc())
            .first()
        )

    def get_by_date(self, trade_date: str) -> MarketSentimentSnapshot | None:
        return self._session.get(MarketSentimentSnapshot, trade_date)
