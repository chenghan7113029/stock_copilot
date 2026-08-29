"""ConfrontationRepo declare 扩展测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.confrontation_repo import DECLARE_OK, NARRATE_SKIPPED, ConfrontationRepo
from dao.engine import Base, ensure_sqlite_schema
from dao.models import ConfrontationRecord  # noqa: F401


def test_update_declare_persists_and_rejects_overwrite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    repo = ConfrontationRepo(session)

    evidence = {
        "bull_evidence": [{"index": 1, "text": "低估"}],
        "bear_evidence": [{"index": 1, "text": "风险"}],
    }
    saved = repo.save(code="600519", evidence=evidence, narrate_status=NARRATE_SKIPPED)
    session.commit()

    declaration = {
        "stance": "adopt_bull",
        "adopted_side": "bull",
        "rejected_side": "bear",
        "adopted_evidence_refs": {"bull": [1], "bear": []},
        "rejected_evidence_refs": {"bull": [], "bear": [1]},
        "rejection_rationale": "拒绝空方[1]",
        "confidence": 0.6,
    }
    updated = repo.update_declare(saved.id, declaration, declare_status=DECLARE_OK)
    session.commit()
    assert updated.declare_status == DECLARE_OK
    assert updated.declaration["stance"] == "adopt_bull"
    assert updated.declared_at is not None

    with pytest.raises(ValueError, match="不允许覆盖"):
        repo.update_declare(saved.id, declaration, declare_status=DECLARE_OK)

    session.close()
