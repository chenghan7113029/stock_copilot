"""ChecklistRepo 单元测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.checklist_repo import ChecklistRepo
from dao.engine import Base, ensure_sqlite_schema
from dao.models import ChecklistRecord  # noqa: F401
from service.guard.models.checklist import ChecklistSubmission, ChecklistValidationResult


def test_save_and_list_by_code_round_trips_json_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    repo = ChecklistRepo(session)
    submission = ChecklistSubmission(
        code="600519",
        action="buy",
        value_reasons=["PE 历史低分位，安全边际充足。", "现金流稳健，ROE 高于行业均值。"],
        tech_alignment="站上 MA20",
        sentiment_position="偏谨慎",
        stop_loss_price=1400.0,
        take_profit_price=1800.0,
    )
    result = ChecklistValidationResult(passed=False, rejection_reasons=["价值理由不足 2 条"])

    repo.save(submission, result)
    session.commit()

    records = repo.list_by_code("600519")
    assert len(records) == 1
    record = records[0]
    assert record.code == "600519"
    assert record.action == "buy"
    assert record.value_reasons == submission.value_reasons
    assert record.rejection_reasons == result.rejection_reasons
    assert record.passed is False
    session.close()
