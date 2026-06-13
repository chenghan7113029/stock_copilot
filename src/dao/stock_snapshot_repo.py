"""StockSnapshot Repository：upsert / 查询。

原则：
- 按 (code, source, report_period) 唯一键 upsert（存在则更新，不存在则插入）
- 不写 csv；每个数据源独立存储，不互相覆盖
- 通用 SQLAlchemy（SQLite merge_or_insert；预留 MySQL on_conflict）
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from dao.models import StockSnapshot
from data_provider.base import FetchResult

logger = logging.getLogger(__name__)

# 快照字段（与 StockSnapshot 列名一致）
_SNAPSHOT_FIELDS = [
    "name", "exchange", "data_timestamp",
    "current_price", "shares_outstanding", "market_cap",
    "eps", "bvps", "dividend_per_share",
    "revenue", "net_income", "ebit", "operating_margin",
    "roe", "roic", "tax_rate", "pe_ratio", "pb_ratio",
    "fcf", "capex", "depreciation",
    "total_assets", "total_liabilities", "current_assets", "current_liabilities",
    "shareholder_equity", "net_debt", "short_term_debt", "long_term_debt",
    "interest_expense", "net_working_capital", "net_fixed_assets",
    "accounts_receivable", "inventory", "accounts_payable",
    "dividend_yield", "dividend_payout_ratio", "dividend_growth_rate",
    "growth_rate",
]


class StockSnapshotRepo:
    """原始快照存取仓库。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, snapshot: StockSnapshot) -> None:
        """按 (code, source, report_period) 唯一键 upsert。"""
        record = self._to_dict(snapshot)
        self._upsert_dict(record)

    def upsert_from_fetch_result(self, result: FetchResult) -> None:
        """从 FetchResult 直接落库，不经过 StockData 模型。"""
        if not result.ok:
            return

        report_period = self._infer_report_period(result.data)
        record: dict[str, Any] = {
            "code": result.code,
            "source": result.source,
            "report_period": report_period,
            "fetched_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        for field in _SNAPSHOT_FIELDS:
            v = result.data.get(field)
            if v is not None:
                record[field] = v

        # 处理 data_timestamp（可能是 isoformat 字符串）
        if "data_timestamp" in result.data:
            ts = result.data["data_timestamp"]
            record["data_timestamp"] = datetime.fromisoformat(ts) if isinstance(ts, str) else ts

        self._upsert_dict(record)

    def find_by_code(self, code: str) -> list[StockSnapshot]:
        """按 code 返回该股票所有来源的最新快照。"""
        return (
            self._session.query(StockSnapshot)
            .filter(StockSnapshot.code == code)
            .order_by(StockSnapshot.source, StockSnapshot.report_period.desc())
            .all()
        )

    def find_by_code_and_source(self, code: str, source: str) -> Optional[StockSnapshot]:
        """返回指定 code + source 的最新快照。"""
        return (
            self._session.query(StockSnapshot)
            .filter(StockSnapshot.code == code, StockSnapshot.source == source)
            .order_by(StockSnapshot.report_period.desc())
            .first()
        )

    # ── 私有 ─────────────────────────────────────────────────────────────────

    def _upsert_dict(self, record: dict[str, Any]) -> None:
        """SQLite insert or replace（通用 upsert）。"""
        stmt = (
            sqlite_insert(StockSnapshot)
            .values(**record)
            .on_conflict_do_update(
                index_elements=["code", "source", "report_period"],
                set_={k: v for k, v in record.items()
                      if k not in ("code", "source", "report_period")},
            )
        )
        self._session.execute(stmt)

    @staticmethod
    def _to_dict(snapshot: StockSnapshot) -> dict[str, Any]:
        """将 ORM 对象转为 dict，排除 None 值。"""
        return {
            col: getattr(snapshot, col)
            for col in StockSnapshot.__table__.columns.keys()
            if getattr(snapshot, col) is not None and col != "id"
        }

    @staticmethod
    def _infer_report_period(data: dict) -> str:
        """从 data 推断 report_period 字符串。"""
        rd = data.get("fundamental_report_date")
        if isinstance(rd, date):
            return rd.strftime("%Y%m%d")
        if isinstance(rd, str) and rd:
            return rd.replace("-", "")
        return datetime.now(timezone.utc).strftime("%Y%m%d")
