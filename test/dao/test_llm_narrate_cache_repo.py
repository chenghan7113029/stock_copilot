"""LLMNarrateCacheRepo 单元测试。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base, ensure_sqlite_schema
from dao.llm_narrate_cache_repo import LLMNarrateCacheRepo
from dao.models import LLMNarrateCache  # noqa: F401


def test_cache_repo_get_set():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repo = LLMNarrateCacheRepo(session)

    assert repo.get("abc") is None
    repo.set("abc", {"ok": True, "data": {"x": 1}})
    session.commit()

    got = repo.get("abc")
    assert got == {"ok": True, "data": {"x": 1}}

    repo.set("abc", {"ok": True, "data": {"x": 2}})
    session.commit()
    assert repo.get("abc")["data"]["x"] == 2
    session.close()
