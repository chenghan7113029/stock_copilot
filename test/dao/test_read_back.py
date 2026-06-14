"""DAO 读回测试：写入后字段一致性验证。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.base import FetchResult


@pytest.fixture
def repo_and_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    return StockSnapshotRepo(session), session


def _write_and_commit(repo, session, result: FetchResult) -> None:
    repo.upsert_from_fetch_result(result)
    session.commit()


def test_find_by_code_returns_written_record(repo_and_session):
    repo, session = repo_and_session
    result = FetchResult(
        code="600519", source="akshare",
        data={"current_price": 1800.5, "eps": 47.76, "roe": 33.5}
    )
    _write_and_commit(repo, session, result)

    snapshots = repo.find_by_code("600519")
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.code == "600519"
    assert snap.source == "akshare"
    assert snap.current_price == pytest.approx(1800.5)
    assert snap.eps == pytest.approx(47.76)
    assert snap.roe == pytest.approx(33.5)


def test_list_recent_respects_limit(repo_and_session):
    repo, session = repo_and_session
    for i in range(5):
        repo.upsert_from_fetch_result(FetchResult(
            code=f"60000{i}", source="akshare",
            data={"current_price": float(100 + i)}
        ))
    session.commit()

    recent = repo.list_recent(limit=3)
    assert len(recent) == 3


def test_list_by_code_alias(repo_and_session):
    repo, session = repo_and_session
    _write_and_commit(repo, session, FetchResult(
        code="601398", source="baostock",
        data={"current_price": 5.5, "roe": 12.0}
    ))
    result = repo.list_by_code("601398")
    assert len(result) == 1
    assert result[0].roe == pytest.approx(12.0)


def test_upsert_idempotent_on_same_key(repo_and_session):
    """相同 (code, source, report_period) 多次写入，只保留一条最新记录。"""
    repo, session = repo_and_session
    _write_and_commit(repo, session, FetchResult(
        code="600519", source="akshare",
        data={"current_price": 1800.0}
    ))
    _write_and_commit(repo, session, FetchResult(
        code="600519", source="akshare",
        data={"current_price": 1850.0}  # 更新价格
    ))

    snapshots = repo.find_by_code("600519")
    assert len(snapshots) == 1
    assert snapshots[0].current_price == pytest.approx(1850.0)


def test_multi_source_stored_independently(repo_and_session):
    """不同数据源同一 code 应独立存储。"""
    repo, session = repo_and_session
    _write_and_commit(repo, session, FetchResult(
        code="600519", source="akshare", data={"current_price": 1800.0}
    ))
    _write_and_commit(repo, session, FetchResult(
        code="600519", source="baostock", data={"current_price": 1801.0}
    ))

    snapshots = repo.find_by_code("600519")
    sources = {s.source for s in snapshots}
    assert sources == {"akshare", "baostock"}


def test_none_fields_not_stored(repo_and_session):
    """data 中缺失的字段不应被写入为 0，而应保持 None（DB NULL）。"""
    repo, session = repo_and_session
    _write_and_commit(repo, session, FetchResult(
        code="600519", source="akshare",
        data={"current_price": 1800.0}  # eps 未提供
    ))

    snap = repo.find_by_code_and_source("600519", "akshare")
    assert snap is not None
    assert snap.eps is None  # 不应填充 0
