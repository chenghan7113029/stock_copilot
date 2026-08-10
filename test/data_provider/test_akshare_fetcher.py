"""AKShare fetcher 离线单元测试（使用 fixture mock，不发网络请求）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

pytestmark = pytest.mark.akshare_legacy

from common.exceptions import DataProviderError
from data_provider.akshare.fetcher import AKShareFetcher, _parse_value

# ── _parse_value 工具测试 ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("--", None),
    ("-", None),
    ("", None),
    ("nan", None),
    ("N/A", None),
    (0.0, 0.0),         # 真实零值不是 None
    ("123.45", 123.45),
    ("1,234.56", 1234.56),
    (55.0, 55.0),
])
def test_parse_value(raw, expected):
    assert _parse_value(raw) == expected


# ── fixture: mock akshare ─────────────────────────────────────────────────────

def _make_quote_df() -> pd.DataFrame:
    """模拟 stock_individual_info_em 返回。"""
    return pd.DataFrame({
        "item": ["股票简称", "最新", "总股本", "总市值"],
        "value": ["贵州茅台", "1800.00", "1256.98万股", "22617亿"],
    })


def _make_balance_df() -> pd.DataFrame:
    return pd.DataFrame({
        "报告日": ["20231231"],
        "流动资产合计": [1e11],
        "流动负债合计": [5e10],
        "负债合计": [8e10],
        "资产总计": [2e11],
        "归属于母公司股东权益合计": [1.2e11],
        "短期借款": [1e9],
        "长期借款": [2e9],
        "应收账款": [3e9],
        "存货": [4e9],
        "应付账款": [5e9],
        "固定资产净额": [6e9],
    })


def _make_income_df() -> pd.DataFrame:
    return pd.DataFrame({
        "营业收入": [1.5e11],
        "归属于母公司所有者的净利润": [6e10],
        "基本每股收益": [47.76],
        "营业利润": [7.8e10],
        "利润总额": [8e10],
        "所得税费用": [2e10],
    })


def _make_cashflow_df() -> pd.DataFrame:
    return pd.DataFrame({
        "经营活动产生的现金流量净额": [5e10],
        "购建固定资产、无形资产和其他长期资产支付的现金": [3e9],
        "固定资产折旧": [1e9],
    })


def _make_dividend_df() -> pd.DataFrame:
    return pd.DataFrame({
        "分红金额": [319.0, 270.0, 205.3],
    })


def _make_indicator_df() -> pd.DataFrame:
    return pd.DataFrame({
        "净资产收益率": [33.5],
        "每股净资产": [95.2],
        "每股收益": [47.8],
    })


@pytest.fixture
def mock_ak():
    m = MagicMock()
    m.stock_individual_info_em.return_value = _make_quote_df()
    m.stock_financial_report_sina.side_effect = lambda stock, symbol: {
        "资产负债表": _make_balance_df(),
        "利润表": _make_income_df(),
        "现金流量表": _make_cashflow_df(),
    }.get(symbol, pd.DataFrame())
    m.stock_dividend_cn.return_value = _make_dividend_df()
    m.stock_financial_analysis_indicator.return_value = _make_indicator_df()
    return m


# ── 测试 fetch_quote ──────────────────────────────────────────────────────────

def test_fetch_quote_returns_price(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert result.data["name"] == "贵州茅台"


def test_fetch_quote_missing_field_is_none(mock_ak):
    """quote 中缺失的数字字段应在 missing_fields 中列出（不填 0）。"""
    quote_df = pd.DataFrame({
        "item": ["股票简称", "最新", "总股本", "总市值"],
        "value": ["贵州茅台", "--", None, "22617亿"],
    })
    mock_ak.stock_individual_info_em.return_value = quote_df
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_quote("600519", "SH")
    assert "current_price" in result.missing_fields
    assert result.data.get("current_price") is None


# ── 测试 fetch_fundamentals ───────────────────────────────────────────────────

def test_fetch_fundamentals_eps(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    assert result.ok
    assert result.data["eps"] == pytest.approx(47.76)


def test_fetch_fundamentals_net_working_capital(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    # NWC = 流动资产 1e11 - 流动负债 5e10 = 5e10
    assert result.data["net_working_capital"] == pytest.approx(5e10)


def test_fetch_fundamentals_tax_rate(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    # 税率 = 2e10 / 8e10 * 100 = 25%
    assert result.data["tax_rate"] == pytest.approx(25.0)


def test_fetch_fundamentals_fcf(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    # FCF = 5e10 - 3e9 = 4.7e10
    assert result.data["fcf"] == pytest.approx(4.7e10)


def test_fetch_fundamentals_dividend_per_share(mock_ak):
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    # 分红 319 每10股 → 31.9 每股
    assert result.data["dividend_per_share"] == pytest.approx(31.9)


def test_missing_report_marked(mock_ak):
    """财报接口返回空 DataFrame 时，对应来源应加入 missing_fields。"""
    mock_ak.stock_financial_report_sina.side_effect = lambda stock, symbol: pd.DataFrame()
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_fundamentals("600519", "SH")
    assert "balance_sheet" in result.missing_fields
    assert "income_stmt" in result.missing_fields
    assert "cashflow" in result.missing_fields


def test_fetch_all_merges(mock_ak):
    """fetch_all 应合并行情与基本面。"""
    fetcher = AKShareFetcher()
    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        result = fetcher.fetch_all("600519", "SH")
    assert result.ok
    assert "current_price" in result.data or "current_price" in result.missing_fields
    assert "eps" in result.data


def test_fetch_chip_distribution_normalizes_columns(mock_ak):
    mock_ak.stock_cyq_em.return_value = pd.DataFrame(
        {
            "日期": ["2026-07-31"],
            "获利比例": ["42.5"],
            "平均成本": ["12.34"],
            "90集中度": ["8.2"],
            "70集中度": ["4.1"],
            "90成本-低": ["10.0"],
            "90成本-高": ["14.0"],
            "70成本-低": ["11.0"],
            "70成本-高": ["13.0"],
        }
    )
    fetcher = AKShareFetcher()

    with patch.object(fetcher, "_get_ak", return_value=mock_ak):
        df = fetcher.fetch_chip_distribution("600519")

    assert list(df.columns) == [
        "trade_date",
        "winner_ratio",
        "avg_cost",
        "concentration_90",
        "concentration_70",
        "cost_90_low",
        "cost_90_high",
        "cost_70_low",
        "cost_70_high",
    ]
    assert df.iloc[0]["winner_ratio"] == pytest.approx(42.5)
    mock_ak.stock_cyq_em.assert_called_once_with(symbol="600519", adjust="qfq")


def test_fetch_chip_distribution_rejects_empty_data(mock_ak):
    mock_ak.stock_cyq_em.return_value = pd.DataFrame()
    fetcher = AKShareFetcher()

    with patch.object(fetcher, "_get_ak", return_value=mock_ak), pytest.raises(DataProviderError):
        fetcher.fetch_chip_distribution("600519")
