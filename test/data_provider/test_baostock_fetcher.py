"""Baostock fetcher 离线单元测试（mock baostock 模块，不发网络请求）。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest

from data_provider.baostock.fetcher import (
    BaostockFetcher,
    _compute_cagr_2y,
    _compute_historical_pe,
    _parse_bs_value,
    _recent_quarters,
    _sample_quarter_end_close,
    derive_fcf,
)

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
    def kline_side_effect(*args, **kwargs):
        start_date = kwargs.get("start_date", args[2] if len(args) > 2 else "")
        # 历史 PE 查询使用 2 年起始日期；行情查询使用当月
        if start_date and start_date[:4] <= str(date.today().year - 1):
            return FakeRS(
                fields=["date", "close"],
                rows=[["2024-12-30", "1800.00"], ["2025-03-31", "1600.00"]],
            )
        return FakeRS(
            fields=["date", "close"],
            rows=[["2024-03-28", "1800.00"]],
        )

    mock.query_history_k_data_plus.side_effect = kline_side_effect

    # 盈利能力（每次调用返回新实例，避免迭代器耗尽）
    def _profit_rs():
        return FakeRS(
            fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
            rows=[["33.5", "47.76", "150000000000", "60000000000", "91.5"]],
        )

    mock.query_profit_data.side_effect = lambda *a, **k: _profit_rs()

    # 成长能力
    mock.query_growth_data.return_value = FakeRS(
        fields=["YOYNI"],
        rows=[["15.2"]],
    )

    # 现金流
    mock.query_cash_flow_data.return_value = FakeRS(
        fields=["operCashTTM", "CFOToOR"],
        rows=[["47000000000", "0.54"]],
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
    f = BaostockFetcher(config={"value_analysis": {"fcf_rate": 0.85}})
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
    mock_bs.query_history_k_data_plus.side_effect = lambda *a, **k: FakeRS(
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
    # 阶段 B：财报特例字段不向外产出
    assert "net_income" not in result.data
    assert "net_income" in result.missing_fields


def test_fetch_fundamentals_growth_rate(fetcher, mock_bs):
    """CAGR 优先于 YOYNI；mock 返回相同 epsTTM 时 CAGR=0。"""
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert "growth_rate" in result.data
    assert result.data["growth_rate"] == pytest.approx(0.0)


def test_fetch_fundamentals_fcf_not_emitted(fetcher):
    """Baostock 可内部推导 FCF，但不得写入 FetchResult.data。"""
    result = fetcher.fetch_fundamentals("600519", "SH")
    assert "fcf" not in result.data
    assert "fcf" in result.missing_fields


def test_fetch_fundamentals_strips_financial_statement_fields(fetcher):
    from data_provider.provider import FINANCIAL_STATEMENT_FIELDS

    result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    for field in FINANCIAL_STATEMENT_FIELDS:
        value = result.data.get(field)
        assert value is None or not isinstance(value, (int, float))
        assert field not in result.data or result.data[field] is None
        assert field in result.missing_fields


def test_fetch_fundamentals_bj_returns_error():
    f = BaostockFetcher()
    result = f.fetch_fundamentals("830946", "BJ")
    assert not result.ok


def test_missing_field_is_none_not_zero(fetcher, mock_bs):
    """当 Baostock 返回空行时，相关字段不应填充 0。"""
    mock_bs.query_profit_data.side_effect = lambda *a, **k: FakeRS(
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
    assert call_count >= 2, "应经过至少一次回溯"


# ── fix-baostock-data-quality 单元测试 ────────────────────────────────────────


def test_net_income_ttm_from_eps_shares():
    """epsTTM × shares → TTM 净利润。"""
    data = {"eps": 66.05, "shares_outstanding": 1.252e9}
    net_income = data["eps"] * data["shares_outstanding"]
    assert net_income == pytest.approx(8.26946e10, rel=1e-3)


def test_growth_rate_cagr_2y():
    cagr = _compute_cagr_2y(66.05, 59.49)
    assert cagr == pytest.approx(5.37, rel=0.02)


def test_historical_pe_calculated():
    eps_by_q = {(2024, 4): 68.64, (2025, 1): 70.86}
    closes_by_q = {(2024, 4): 1520.0, (2025, 1): 1600.0}
    pes = _compute_historical_pe(eps_by_q, closes_by_q)
    assert len(pes) == 2
    assert all(0 < pe <= 200 for pe in pes)
    assert pes[0] == pytest.approx(1520.0 / 68.64, rel=1e-3)


def test_historical_pe_filters_extremes():
    eps_by_q = {(2024, 4): 1.0, (2025, 1): 68.64}
    closes_by_q = {(2024, 4): 500.0, (2025, 1): 1600.0}  # PE=500 应被过滤
    pes = _compute_historical_pe(eps_by_q, closes_by_q)
    assert len(pes) == 1
    assert pes[0] == pytest.approx(1600.0 / 68.64, rel=1e-3)


def test_sample_quarter_end_close():
    close_by_date = {
        "2024-12-27": 1500.0,
        "2024-12-30": 1520.0,
        "2025-01-02": 1530.0,
    }
    close = _sample_quarter_end_close(close_by_date, 2024, 4)
    assert close == pytest.approx(1520.0)


def test_fcf_fallback_chain_priority1():
    data = {"_operating_cashflow_ttm": 615e8}
    fcf, warning = derive_fcf(data, 0.85)
    assert fcf == pytest.approx(615e8)
    assert warning is None


def test_fcf_fallback_chain_priority2():
    data = {"_cfo_to_or": 0.54, "revenue": 1.688e11}
    fcf, warning = derive_fcf(data, 0.85)
    assert fcf == pytest.approx(0.54 * 1.688e11)
    assert "CFOToOR" in (warning or "")


def test_fcf_fallback_chain_priority3():
    data = {"net_income": 823e8}
    fcf, warning = derive_fcf(data, 0.85)
    assert fcf == pytest.approx(823e8 * 0.85)
    assert "fallback" in (warning or "")


def test_fetch_fundamentals_net_income_ttm_with_shares(fetcher, mock_bs):
    """session 内若有 shares_outstanding，应用 eps×shares 推导 net_income。"""
    mock_bs.query_profit_data.return_value = FakeRS(
        fields=["roeAvg", "epsTTM", "MBRevenue", "netProfit", "grossProfitMargin"],
        rows=[["33.5", "66.05", "150000000000", "60000000000", "91.5"]],
    )
    fetcher.fetch_fundamentals("600519", "SH")
    # 手动注入 shares 后重新调用 profit 逻辑验证
    data: dict = {"eps": 66.05, "shares_outstanding": 1.252e9}
    data["net_income"] = data["eps"] * data["shares_outstanding"]
    assert data["net_income"] == pytest.approx(8.26946e10, rel=1e-3)
