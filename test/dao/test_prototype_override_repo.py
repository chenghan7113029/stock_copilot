"""PrototypeOverrideRepo 单元测试。"""

from __future__ import annotations

from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base, ensure_sqlite_schema
from dao.models import PrototypeOverrideRecord
from dao.prototype_override_repo import PrototypeOverrideRepo


def _repo() -> tuple[PrototypeOverrideRepo, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    return PrototypeOverrideRepo(session), session


def test_upsert_inserts_new_override_with_matching_timestamps():
    repo, session = _repo()

    repo.upsert("600519", "high_dividend", "管理层转向稳定分红策略")
    session.commit()

    record = repo.get_by_code("600519")
    assert record is not None
    assert record.prototype == "high_dividend"
    assert record.reason == "管理层转向稳定分红策略"
    assert record.created_at == record.updated_at
    session.close()


def test_upsert_updates_existing_override_without_changing_created_at():
    repo, session = _repo()
    repo.upsert("600519", "high_dividend", "初始原因")
    session.commit()
    first = repo.get_by_code("600519")
    assert first is not None
    created_at = first.created_at

    sleep(0.001)
    repo.upsert("600519", "value_growth", "策略反转")
    session.commit()

    record = repo.get_by_code("600519")
    assert record is not None
    assert record.prototype == "value_growth"
    assert record.reason == "策略反转"
    assert record.created_at == created_at
    assert record.updated_at > created_at
    assert session.query(PrototypeOverrideRecord).count() == 1
    session.close()


def test_get_by_code_returns_none_for_unknown_code():
    repo, session = _repo()

    assert repo.get_by_code("999999") is None
    session.close()
