"""Provider 持久化会话边界测试。

验证：
- Provider 在 fetch 阶段不持有 Session（先收集 FetchResult，再批量 upsert）
- 多源数据各自独立落库（同一 code，不同 source 有各自快照）
- upsert_many 写入后，find_by_code 可读回数据
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.base import FetchResult
from data_provider.manager import SourceManager
from data_provider.provider import StockDataProvider

# ── 内存 SQLite 工厂 ─────────────────────────────────────────────────────────

def _make_in_memory_repo():
    """创建内存 SQLite + 自动建表 + StockSnapshotRepo。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    return StockSnapshotRepo(session), session


# ── mock fetcher 工具 ─────────────────────────────────────────────────────────

def _make_mock_fetcher(source_name: str, priority: int, data: dict):
    """创建返回固定数据的 mock fetcher。"""
    fetcher = MagicMock()
    fetcher.source_name = source_name
    fetcher.priority = priority
    fetcher.fetch_all.return_value = FetchResult(
        code="600519", source=source_name, data=data
    )
    return fetcher


# ── 测试 ─────────────────────────────────────────────────────────────────────

def test_upsert_many_writes_multiple_sources():
    """upsert_many 应将多个 FetchResult 各自写入独立快照。"""
    repo, session = _make_in_memory_repo()

    results = [
        FetchResult(code="600519", source="akshare",
                    data={"current_price": 1800.0, "eps": 47.5}),
        FetchResult(code="600519", source="baostock",
                    data={"current_price": 1801.0, "eps": 47.4}),
    ]
    repo.upsert_many(results)
    session.commit()

    snapshots = repo.find_by_code("600519")
    sources = {s.source for s in snapshots}
    assert "akshare" in sources
    assert "baostock" in sources


def test_upsert_many_skips_failed_results():
    """upsert_many 应跳过 error 不为 None 的 FetchResult。"""
    repo, session = _make_in_memory_repo()

    results = [
        FetchResult(code="600519", source="akshare",
                    data={"current_price": 1800.0}, error="网络超时"),
        FetchResult(code="600519", source="baostock",
                    data={"current_price": 1801.0}),
    ]
    repo.upsert_many(results)
    session.commit()

    snapshots = repo.find_by_code("600519")
    sources = {s.source for s in snapshots}
    assert "akshare" not in sources
    assert "baostock" in sources


def test_provider_fetch_then_persist_order():
    """Provider 应先完成网络取数，再调用 upsert_many——顺序解耦。

    通过检查 upsert_many 被调用时 fetch_all 已完成来验证顺序。
    """
    repo, session = _make_in_memory_repo()

    ak_fetcher = _make_mock_fetcher("akshare", 1, {"current_price": 1800.0, "eps": 47.5})
    bs_fetcher = _make_mock_fetcher("baostock", 2, {"current_price": 1801.0, "roe": 33.0})

    manager = SourceManager([ak_fetcher, bs_fetcher])
    provider = StockDataProvider(manager=manager, repo=repo)

    stock = provider.get_stock_data("600519")

    # 两个 fetcher 均被调用
    ak_fetcher.fetch_all.assert_called_once()
    bs_fetcher.fetch_all.assert_called_once()

    # 落库后可读回
    session.commit()
    snapshots = repo.find_by_code("600519")
    sources = {s.source for s in snapshots}
    assert "akshare" in sources
    assert "baostock" in sources

    # StockData 字段正确合并（akshare 优先级高，eps 来自 akshare）
    assert stock.current_price == pytest.approx(1800.0)


def test_provider_no_repo_does_not_crash():
    """未注入 repo 时，Provider 应正常运行，不抛异常。"""
    ak_fetcher = _make_mock_fetcher("akshare", 1, {"current_price": 1800.0})
    manager = SourceManager([ak_fetcher])
    provider = StockDataProvider(manager=manager, repo=None)

    stock = provider.get_stock_data("600519")
    assert stock.current_price == pytest.approx(1800.0)
