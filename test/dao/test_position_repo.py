"""PositionRepo 单元测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base, ensure_sqlite_schema
from dao.models import PositionRecord  # noqa: F401
from dao.position_repo import PositionRepo


def test_upsert_inserts_then_updates_without_changing_opened_at():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    repo = PositionRepo(session)

    repo.upsert("600519", cost_price=1500.0, shares=100)
    session.commit()
    original = repo.get_by_code("600519")

    assert original is not None
    assert original.cost_price == 1500.0
    assert original.shares == 100
    opened_at = original.opened_at

    repo.upsert("600519", cost_price=1600.0, shares=200)
    session.commit()
    updated = repo.get_by_code("600519")

    assert updated is not None
    assert updated.cost_price == 1600.0
    assert updated.shares == 200
    assert updated.opened_at == opened_at
    session.close()
