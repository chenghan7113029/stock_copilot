"""常看列表 watchlist 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from common.watchlist import (
    add_to_watchlist,
    load_watchlist,
    remove_from_watchlist,
    save_watchlist,
    watchlist_codes,
)


@pytest.fixture()
def wl_path(tmp_path: Path) -> Path:
    return tmp_path / "watchlist.yaml"


def test_load_missing_returns_empty(wl_path: Path):
    assert load_watchlist(path=wl_path) == []


def test_add_and_list(wl_path: Path):
    stocks, created = add_to_watchlist("600519", name="贵州茅台", path=wl_path)
    assert created is True
    assert stocks == [{"code": "600519", "name": "贵州茅台"}]
    assert watchlist_codes(path=wl_path) == ["600519"]

    stocks2, created2 = add_to_watchlist("600519", path=wl_path)
    assert created2 is False
    assert len(stocks2) == 1


def test_add_updates_name(wl_path: Path):
    add_to_watchlist("601398", name="工行", path=wl_path)
    stocks, created = add_to_watchlist("601398", name="工商银行", path=wl_path)
    assert created is False
    assert stocks[0]["name"] == "工商银行"


def test_remove(wl_path: Path):
    save_watchlist(
        [{"code": "600519", "name": "茅台"}, {"code": "601398"}],
        path=wl_path,
    )
    stocks, removed = remove_from_watchlist("600519", path=wl_path)
    assert removed is True
    assert [s["code"] for s in stocks] == ["601398"]
    _, removed2 = remove_from_watchlist("600519", path=wl_path)
    assert removed2 is False


def test_save_roundtrip_preserves_order(wl_path: Path):
    save_watchlist(
        [{"code": "000001", "name": "平安银行"}, {"code": "600519"}],
        path=wl_path,
    )
    loaded = load_watchlist(path=wl_path)
    assert loaded[0]["code"] == "000001"
    assert loaded[1]["code"] == "600519"
    assert "常看" in wl_path.read_text(encoding="utf-8")
