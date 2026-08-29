"""ConfrontationRepo 单元测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.confrontation_repo import NARRATE_OK, NARRATE_SKIPPED, ConfrontationRepo
from dao.engine import Base, ensure_sqlite_schema
from dao.models import ConfrontationRecord  # noqa: F401


def test_save_get_and_list_by_code():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    repo = ConfrontationRepo(session)

    evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "低估"}],
        "bear_evidence": [{"index": 1, "text": "风险"}],
    }
    narrative = {"bull_thesis": "多方观点", "confidence": 0.9}

    saved = repo.save(
        code="600519",
        evidence=evidence,
        narrate_status=NARRATE_OK,
        narrative=narrative,
    )
    session.commit()

    loaded = repo.get(saved.id)
    assert loaded is not None
    assert loaded.code == "600519"
    assert loaded.narrate_status == NARRATE_OK
    assert loaded.evidence["bull_evidence"][0]["text"] == "低估"
    assert loaded.narrative["bull_thesis"] == "多方观点"

    repo.save(code="600519", evidence=evidence, narrate_status=NARRATE_SKIPPED)
    session.commit()
    listed = repo.list_by_code("600519")
    assert len(listed) == 2
    session.close()


def test_update_persona_stress_on_existing_record():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    repo = ConfrontationRepo(session)

    evidence = {
        "code": "600519",
        "bull_evidence": [{"index": 1, "text": "低估"}],
        "bear_evidence": [{"index": 1, "text": "风险"}],
    }
    saved = repo.save(code="600519", evidence=evidence, narrate_status=NARRATE_SKIPPED)
    session.commit()

    payload = {
        "personas": [
            {"id": "value_quality", "status": "pending", "output": None, "error": None}
        ]
    }
    updated = repo.update_persona_stress(saved.id, payload)
    session.commit()
    assert updated.persona_stress["personas"][0]["id"] == "value_quality"

    loaded = repo.get(saved.id)
    assert loaded is not None
    assert loaded.persona_stress["personas"][0]["status"] == "pending"
    session.close()
