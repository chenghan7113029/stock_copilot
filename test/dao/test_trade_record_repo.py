"""TradeRecordRepo 单元测试。"""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.models import TradeRecord
from dao.trade_record_repo import TradeRecordRepo


def _record(code: str, action: str, quantity: int, price: float, date: str) -> TradeRecord:
    return TradeRecord(
        code=code,
        action=action,
        quantity=quantity,
        price=price,
        trade_date=datetime.fromisoformat(date),
    )


def test_add_and_find_by_code_returns_records_in_trade_order():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = TradeRecordRepo(session)

    repo.add(_record("600519", "BUY", 100, 1500.0, "2026-08-01"))
    repo.add(_record("600519", "SELL", 100, 1600.0, "2026-08-02"))
    session.commit()

    records = repo.find_by_code("600519")

    assert [record.action for record in records] == ["BUY", "SELL"]
    assert records[0].checklist_id is None


def test_find_open_positions_returns_fifo_remaining_buy_quantities():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = TradeRecordRepo(session)

    repo.add(_record("600519", "BUY", 100, 1500.0, "2026-08-01"))
    repo.add(_record("600519", "BUY", 100, 1550.0, "2026-08-02"))
    repo.add(_record("600519", "SELL", 150, 1600.0, "2026-08-03"))
    session.commit()

    open_positions = repo.find_open_positions("600519")

    assert len(open_positions) == 1
    assert open_positions[0].code == "600519"
    assert open_positions[0].quantity == 50
