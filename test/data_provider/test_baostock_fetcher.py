"""Baostock fetcher 离线单元测试（mock baostock 模块，不发网络请求）。"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from data_provider.baostock.fetcher import BaostockFetcher, _parse_bs_value, _recent_quarters

# ── _parse_bs_value 工具测试 ──────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", None),
    ("--", None),
    ("nan", None),
    ("0", 0.0),
    ("0.0", 0.0),       # 真实零值不是 None
    ("33.5", 33.5),
    (55.0, 55.0),
])
def test_parse_bs_value(raw, expected):
    assert _parse_bs_value(raw) == expected


# ── fixture ────────────────────────────────────────────────────────────────────

class FakeRS:
    """模拟 Baostock 的 ResultData 对象。"""
    def __init__(self, fields: list[str], rows: list[list[str]], error_code: str = "0"):
        self.fields = fields
        self._rows = iter(rows)
        self.error_code = error_code
        self.error_msg = ""
        self._current: list[str] | None = None

    def next(self) -> bool:
        try:
            self._current = next(self._rows)
            return True
        except StopIteration:
            return False

    def get_row_data(self) -> list[str]:
        return self._current or []


class FakeLogin:
    error_code = "0"
    error_msg = ""


def _make_mock_bs():
    mock = MagicMock()
    mock.login.return_value = FakeLogin()
    mock.logout.return_value = FakeLogin()

    # 行情
    mock.query_history_k_data_plus.return_value = FakeRS(
        fields=["date", "close"],
        rows=[["2024-03-28", "1800.00"]],
    )

    # 盈利能力
    mock.query_profit_data.return_value = FakeRS(
        fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
        rows=[["33.5", "47.76", "150000000000", "60000000000", "91.5"]],
    )

    # 成长能力
    mock.query_growth_data.return_value = FakeRS(
        fields=["YOYNI"],
        rows=[["15.2"]],
    )

    # 现金流
    mock.query_cash_flow_data.return_value = FakeRS(
        fields=["operCashTTM"],
        rows=[["47000000000"]],
    )

    # 偿债能力
    mock.query_balance_data.return_value = FakeRS(
        fields=["liabilityToAsset"],
        rows=[["0.35"]],
    )

    return mock


@pytest.fixture
def mock_bs():
    return _make_mock_bs()


@pytest.fixture
def fetcher(mock_bs):
    f = BaostockFetcher()
    f._bs = mock_bs
    # 修补 _session 上下文管理器直接 yield mock_bs
    @contextmanager
    def fake_session():
        yield mock_bs
    f._session = fake_session
    return f


# ── 测试 fetch_quote ──────────────────────────────────────────────────────────

def test_fetch_quote_success(fetcher):
    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert result.data["current_price"] == pytest.approx(1800.0)


def test_fetch_quote_bj_returns_error():
    """北交所代码应返回不支持的错误，不 crash。"""
    f = BaostockFetcher()
    result = f.fetch_quote("830946", "BJ")
    assert not result.ok
    assert "北交所" in (result.error or "")


def test_fetch_quote_empty_data_marks_missing(fetcher, mock_bs):
    mock_bs.query_history_k_data_plus.return_value = FakeRS(
        fields=["date", "close"], rows=[]
    )
    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert "current_price" in result.missing_fields


# ── 测试 fetch_fundamentals ───────────────────────────────────────────────────

def test_fetch_fundamentals_profit(fetcher):
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data["roe"] == pytest.approx(33.5)
    assert result.data["eps"] == pytest.approx(47.76)
    assert result.data["net_income"] == pytest.approx(6e10)


def test_fetch_fundamentals_growth_rate(fetcher):
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.data["growth_rate"] == pytest.approx(15.2)


def test_fetch_fundamentals_fcf(fetcher):
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.data["fcf"] == pytest.approx(4.7e10)


def test_fetch_fundamentals_bj_returns_error():
    f = BaostockFetcher()
    result = f.fetch_fundamentals("830946", "BJ")
    assert not result.ok


def test_missing_field_is_none_not_zero(fetcher, mock_bs):
    """当 Baostock 返回空行时，相关字段不应填充 0。"""
    mock_bs.query_profit_data.return_value = FakeRS(
        fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
        rows=[["", "", "", "", ""]],
    )
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.data.get("roe") is None
    assert result.data.get("eps") is None


# ── 季频参数修复测试 ──────────────────────────────────────────────────────────

def test_recent_quarters_never_zero():
    """_recent_quarters 返回的 quarter 值必须在 1–4 范围内，绝不为 0。"""
    quarters = _recent_quarters(8)
    for year, quarter in quarters:
        assert 1 <= quarter <= 4, f"quarter={quarter} 超出范围"
        assert year >= 2000


def test_recent_quarters_length():
    assert len(_recent_quarters(5)) == 5


def test_fetch_fundamentals_quarter_not_zero(fetcher, mock_bs):
    """fetch_fundamentals 调用 query_profit_data 时 quarter 参数不应为 0。"""
    fetcher.fetch_fundamentals("600519", "SH")
    # 检查所有调用，确认没有 quarter=0
    for actual_call in mock_bs.query_profit_data.call_args_list:
        _, kwargs = actual_call
        assert kwargs.get("quarter", -1) != 0, "不应使用 quarter=0"
        assert kwargs.get("year", -1) != 0, "不应使用 year=0"


def test_fetch_fundamentals_fallback_to_previous_quarter(fetcher, mock_bs):
    """当最近季度无数据时，应回溯到上一季度。"""
    call_count = 0

    def profit_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeRS(fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
                          rows=[])  # 第一次返回空
        return FakeRS(
            fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
            rows=[["20.0", "5.0", "1000000", "500000", "60.0"]],
        )

    mock_bs.query_profit_data.side_effect = profit_side_effect
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data.get("roe") == pytest.approx(20.0)
    assert call_count == 2, "应经过一次回溯"
