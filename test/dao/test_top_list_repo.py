"""StockTopListRepo / StockTopInstRepo / TopListSyncMarkerRepo SQLite 行为测试。"""

from __future__ import annotations

from dao.engine import Base, create_db_engine, make_session_factory
from dao.models import StockTopInst, StockTopList, TopListSyncMarker  # noqa: F401
from dao.top_list_repo import (
    StockTopInstRepo,
    StockTopListRepo,
    TopListSyncMarkerRepo,
)


def _make_session():
    engine = create_db_engine({"db": {"url": "sqlite:///:memory:"}})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def _top_list_record(
    code: str, trade_date: str, reason: str, net_amount: float
) -> dict:
    return {
        "code": code,
        "trade_date": trade_date,
        "reason": reason,
        "name": "测试股",
        "close": 10.0,
        "pct_change": 10.0,
        "turnover_rate": 8.0,
        "amount": 1.0e9,
        "l_sell": 2.0e8,
        "l_buy": 3.0e8,
        "l_amount": 5.0e8,
        "net_amount": net_amount,
        "net_rate": 10.0,
        "amount_rate": 50.0,
        "float_values": 5.0e9,
    }


def _top_inst_record(code: str, trade_date: str, exalter: str, side: str) -> dict:
    return {
        "code": code,
        "trade_date": trade_date,
        "side": side,
        "exalter": exalter,
        "buy": 1.0e8,
        "buy_rate": 3.0,
        "sell": 4.0e7,
        "sell_rate": 1.5,
        "net_buy": 6.0e7,
        "reason": "日涨幅偏离值达到7%的前5只证券",
    }


def test_top_list_multiple_reasons_same_day() -> None:
    """同股同日多条理由 → 多行（每次上榜事件一行）。"""
    session = _make_session()
    try:
        repo = StockTopListRepo(session)
        repo.replace_day(
            "2026-10-08",
            [
                _top_list_record("000678", "2026-10-08", "日振幅值达到15%的前5只证券", -8.5e7),
                _top_list_record("000678", "2026-10-08", "日换手率达到20%的前5只证券", -8.5e7),
                _top_list_record("300530", "2026-10-08", "日涨幅达到15%的前5只证券", 7.6e7),
            ],
        )
        session.commit()

        records = repo.query_range("000678", "2026-07-10")
        assert len(records) == 2
        assert {r["reason"] for r in records} == {
            "日振幅值达到15%的前5只证券",
            "日换手率达到20%的前5只证券",
        }
        assert repo.count_day_rows("2026-10-08") == 3
        assert repo.count_distinct_trade_dates("000678", "2026-07-10") == 1
    finally:
        session.close()


def test_top_list_replace_day_is_idempotent() -> None:
    """重复同步同一交易日不增加行（整日替换）。"""
    session = _make_session()
    try:
        repo = StockTopListRepo(session)
        day = [_top_list_record("600519", "2026-10-09", "日涨幅偏离值达到7%的前5只证券", 1.0e8)]
        repo.replace_day("2026-10-09", day)
        repo.replace_day("2026-10-09", day)
        session.commit()
        assert repo.count_day_rows("2026-10-09") == 1
    finally:
        session.close()


def test_top_list_query_range_filters_window() -> None:
    session = _make_session()
    try:
        repo = StockTopListRepo(session)
        repo.replace_day(
            "2026-01-05",
            [_top_list_record("600519", "2026-01-05", "日涨幅偏离值达到7%的前5只证券", 1.0)],
        )
        repo.replace_day(
            "2026-10-09",
            [_top_list_record("600519", "2026-10-09", "日涨幅偏离值达到7%的前5只证券", 2.0)],
        )
        session.commit()

        assert len(repo.query_range("600519", "2026-07-10")) == 1
        assert len(repo.query_range("600519", "2025-01-01")) == 2
    finally:
        session.close()


def test_absent_stock_with_watermark_is_not_confused_with_not_fetched() -> None:
    """未上榜 ≠ 未拉取：无记录但水位存在时，覆盖水位可查询、行数为 0。"""
    session = _make_session()
    try:
        list_repo = StockTopListRepo(session)
        marker_repo = TopListSyncMarkerRepo(session)

        list_repo.replace_day(
            "2026-10-09",
            [_top_list_record("000001", "2026-10-09", "日涨幅偏离值达到7%的前5只证券", 1.0)],
        )
        marker_repo.mark("2026-10-09")
        session.commit()

        # 600519 当日未上榜：无记录，但水位已覆盖该日
        assert list_repo.query_range("600519", "2026-07-10") == []
        assert marker_repo.has("2026-10-09") is True
        assert marker_repo.covered_dates("2026-07-10") == ["2026-10-09"]

        # 未拉取的交易日：无水位
        assert marker_repo.has("2026-10-08") is False
    finally:
        session.close()


def test_top_inst_keeps_duplicate_seat_rows() -> None:
    """席位无天然唯一键：同一「机构专用」多席位、同一席位跨买卖两侧均保留。"""
    session = _make_session()
    try:
        repo = StockTopInstRepo(session)
        repo.replace_day(
            "2026-10-08",
            [
                _top_inst_record("000513", "2026-10-08", "机构专用", "0"),
                _top_inst_record("000513", "2026-10-08", "机构专用", "0"),
                _top_inst_record("000513", "2026-10-08", "机构专用", "1"),
                _top_inst_record("000513", "2026-10-08", "深股通专用", "0"),
            ],
        )
        session.commit()

        assert repo.count_day_rows("2026-10-08") == 4
        records = repo.query_range("000513", "2026-07-10")
        assert len(records) == 4

        # 整日替换幂等
        repo.replace_day(
            "2026-10-08",
            [_top_inst_record("000513", "2026-10-08", "机构专用", "0")],
        )
        session.commit()
        assert repo.count_day_rows("2026-10-08") == 1
    finally:
        session.close()


def test_marker_mark_is_idempotent() -> None:
    session = _make_session()
    try:
        repo = TopListSyncMarkerRepo(session)
        repo.mark("2026-10-08")
        repo.mark("2026-10-08", source="tushare")
        session.commit()
        assert repo.count() == 1
        assert repo.covered_dates("2026-10-01") == ["2026-10-08"]
    finally:
        session.close()
