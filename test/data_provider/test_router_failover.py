"""DataFetcherRouter / FailoverStrategy 单测。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from data_provider.router import DataFetcherRouter
from data_provider.strategies import FailoverStrategy


def test_router_sorts_by_priority(monkeypatch):
    created: list[tuple[str, int]] = []

    def fake_build(name, priority_override, src=None, config=None):
        f = MagicMock()
        f.source_name = name
        f.priority = priority_override if priority_override is not None else 99
        created.append((name, f.priority))
        return f

    monkeypatch.setattr(DataFetcherRouter, "build_fetcher", staticmethod(fake_build))
    router = DataFetcherRouter.from_config(
        {
            "data_sources": {
                "enabled": [
                    {"name": "baostock", "priority": 2},
                    {"name": "tushare", "priority": 1, "token": "x"},
                ]
            }
        }
    )
    names = [f.source_name for f in router.fetchers]
    assert names == ["tushare", "baostock"]


def test_router_skips_disabled_akshare(monkeypatch):
    def fake_build(name, priority_override, src=None, config=None):
        assert name != "akshare"
        f = MagicMock()
        f.source_name = name
        f.priority = priority_override or 1
        f.fetch_kline = MagicMock()
        return f

    monkeypatch.setattr(DataFetcherRouter, "build_fetcher", staticmethod(fake_build))
    router = DataFetcherRouter.from_config(
        {"data_sources": {"enabled": [{"name": "baostock", "priority": 1}]}}
    )
    assert [f.source_name for f in router.fetchers] == ["baostock"]
    assert router.fetchers_with_method("fetch_kline")


def test_failover_order_and_success():
    calls: list[str] = []
    a = MagicMock()
    a.source_name = "a"

    def fail(_f=a):
        calls.append("a")
        raise RuntimeError("a fail")

    b = MagicMock()
    b.source_name = "b"

    def ok(_f=b):
        calls.append("b")
        return "ok"

    # wrap as callables on objects
    a_fn = MagicMock(side_effect=fail)
    b_fn = MagicMock(side_effect=ok)
    fa = MagicMock(source_name="a")
    fb = MagicMock(source_name="b")

    result = FailoverStrategy.try_each(
        [fa, fb],
        lambda f: (_ for _ in ()).throw(RuntimeError("x"))
        if f is fa
        else "ok",
    )
    assert result.value == "ok"
    assert result.source_name == "b"


def test_failover_all_fail():
    with pytest.raises(RuntimeError, match="a:"):
        FailoverStrategy.try_each(
            [MagicMock(source_name="a")],
            lambda f: (_ for _ in ()).throw(RuntimeError("boom")),
        )
