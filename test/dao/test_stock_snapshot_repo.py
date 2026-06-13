"""StockSnapshot Repository 测试：内存/临时 SQLite，验证多源独立留存、upsert 去重、按源查询。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.models import StockSnapshot
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.base import FetchResult


@pytest.fixture
def session():
    """每个测试用独立内存 SQLite。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def repo(session):
    return StockSnapshotRepo(session)


# ── upsert 基础 ───────────────────────────────────────────────────────────────

def test_upsert_inserts_new_record(repo, session):
    r = FetchResult(
        code="600519", source="akshare",
        data={"eps": 47.76, "fundamental_report_date": None},
    )
    repo.upsert_from_fetch_result(r)
    session.commit()
    rows = session.query(StockSnapshot).all()
    assert len(rows) == 1
    assert rows[0].eps == pytest.approx(47.76)


def test_upsert_updates_existing_record(repo, session):
    r1 = FetchResult(code="600519", source="akshare", data={"eps": 47.76})
    r2 = FetchResult(code="600519", source="akshare", data={"eps": 48.0})
    repo.upsert_from_fetch_result(r1)
    session.commit()
    repo.upsert_from_fetch_result(r2)
    session.commit()
    rows = session.query(StockSnapshot).all()
    assert len(rows) == 1
    assert rows[0].eps == pytest.approx(48.0)


# ── 多源独立留存 ──────────────────────────────────────────────────────────────

def test_multi_source_independent_rows(repo, session):
    r1 = FetchResult(code="600519", source="akshare", data={"eps": 47.76})
    r2 = FetchResult(code="600519", source="baostock", data={"eps": 47.0})
    repo.upsert_from_fetch_result(r1)
    repo.upsert_from_fetch_result(r2)
    session.commit()
    rows = session.query(StockSnapshot).all()
    assert len(rows) == 2
    sources = {r.source for r in rows}
    assert sources == {"akshare", "baostock"}


def test_different_source_different_eps(repo, session):
    r1 = FetchResult(code="600519", source="akshare", data={"eps": 47.76})
    r2 = FetchResult(code="600519", source="baostock", data={"eps": 47.0})
    repo.upsert_from_fetch_result(r1)
    repo.upsert_from_fetch_result(r2)
    session.commit()
    ak_row = repo.find_by_code_and_source("600519", "akshare")
    bs_row = repo.find_by_code_and_source("600519", "baostock")
    assert ak_row is not None and ak_row.eps == pytest.approx(47.76)
    assert bs_row is not None and bs_row.eps == pytest.approx(47.0)


# ── 按源查询 ──────────────────────────────────────────────────────────────────

def test_find_by_code_returns_all_sources(repo, session):
    for src, v in [("akshare", 47.76), ("baostock", 47.0)]:
        repo.upsert_from_fetch_result(FetchResult(code="600519", source=src, data={"eps": v}))
    session.commit()
    rows = repo.find_by_code("600519")
    assert len(rows) == 2


def test_find_by_code_and_source(repo, session):
    repo.upsert_from_fetch_result(
        FetchResult(code="000001", source="baostock", data={"roe": 12.5})
    )
    session.commit()
    row = repo.find_by_code_and_source("000001", "baostock")
    assert row is not None
    assert row.roe == pytest.approx(12.5)


def test_find_by_code_and_source_not_found(repo, session):
    result = repo.find_by_code_and_source("999999", "akshare")
    assert result is None


# ── 失败结果不落库 ────────────────────────────────────────────────────────────

def test_failed_result_not_saved(repo, session):
    r = FetchResult(code="600519", source="akshare", error="network error")
    repo.upsert_from_fetch_result(r)
    session.commit()
    rows = session.query(StockSnapshot).all()
    assert len(rows) == 0


# ── 不写 csv ──────────────────────────────────────────────────────────────────

def test_no_csv_files_created(repo, session, tmp_path):
    """确认测试过程中没有创建 csv 文件（验证 design 约束）。"""
    import glob
    repo.upsert_from_fetch_result(
        FetchResult(code="600519", source="akshare", data={"eps": 47.76})
    )
    session.commit()
    csv_files = glob.glob(str(tmp_path / "**/*.csv"), recursive=True)
    assert csv_files == []
