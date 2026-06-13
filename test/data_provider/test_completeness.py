"""数据完备性校验测试。

离线版本使用手工构造的 StockData（fixture）；
网络版本（@pytest.mark.network）对真实样本股票运行完备性检查。

样本股票（MRD §7 D7 指定）：
- 工商银行 601398 / 招商银行 600036 → 银行原型
- 长江电力 600900                     → 高股息原型
- 贵州茅台 600519                     → 价值成长原型
"""

from __future__ import annotations

import pytest

from common.models.stock_data import StockData
from data_provider.validation.completeness import batch_check, check_completeness
from data_provider.validation.field_requirements import get_required_fields

# ── 离线单元测试 ──────────────────────────────────────────────────────────────

def _full_bank_stock() -> StockData:
    """构造满足银行原型所有必需字段的 StockData。"""
    s = StockData(code="601398", name="工商银行")
    s.current_price = 5.5
    s.shares_outstanding = 3.56e11
    s.market_cap = 1.96e12
    s.eps = 0.95
    s.bvps = 7.8
    s.dividend_per_share = 0.31
    s.revenue = 8.7e11
    s.net_income = 3.6e11
    s.roe = 11.5
    s.total_assets = 4.2e13
    s.total_liabilities = 3.9e13
    s.shareholder_equity = 3.0e12
    s.dividend_yield = 5.6
    s.dividend_payout_ratio = 30.0
    return s


def _full_dividend_stock() -> StockData:
    """构造满足高股息原型所有必需字段的 StockData。"""
    s = StockData(code="600900", name="长江电力")
    s.current_price = 28.0
    s.shares_outstanding = 2.2e10
    s.market_cap = 6.16e11
    s.eps = 1.2
    s.bvps = 9.5
    s.dividend_per_share = 0.88
    s.revenue = 6e10
    s.net_income = 2.5e10
    s.roe = 12.0
    s.fcf = 1.8e10
    s.total_assets = 5e11
    s.total_liabilities = 3e11
    s.shareholder_equity = 2e11
    s.dividend_yield = 3.1
    s.dividend_payout_ratio = 73.0
    return s


def _full_growth_stock() -> StockData:
    """构造满足价值成长原型所有必需字段的 StockData。"""
    s = StockData(code="600519", name="贵州茅台")
    s.current_price = 1800.0
    s.shares_outstanding = 1.26e9
    s.market_cap = 2.27e12
    s.eps = 47.76
    s.bvps = 95.0
    s.dividend_per_share = 31.9
    s.revenue = 1.5e11
    s.net_income = 6e10
    s.roe = 33.5
    s.roic = 30.0
    s.operating_margin = 52.0
    s.ebit = 7.8e10
    s.fcf = 4.7e10
    s.total_assets = 2e11
    s.total_liabilities = 8e10
    s.shareholder_equity = 1.2e11
    return s


def test_bank_full_pass():
    stock = _full_bank_stock()
    report = check_completeness(stock, "bank")
    assert report.passed, report.summary()


def test_high_dividend_full_pass():
    stock = _full_dividend_stock()
    report = check_completeness(stock, "high_dividend")
    assert report.passed, report.summary()


def test_value_growth_full_pass():
    stock = _full_growth_stock()
    report = check_completeness(stock, "value_growth")
    assert report.passed, report.summary()


def test_missing_required_field_fails():
    stock = _full_bank_stock()
    stock.current_price = None
    report = check_completeness(stock, "bank")
    assert not report.passed
    assert "current_price" in report.missing_required


def test_coverage_ratio():
    stock = StockData(code="000001")
    report = check_completeness(stock, "bank")
    assert report.coverage_ratio == pytest.approx(0.0)


def test_unknown_prototype_raises():
    stock = StockData(code="000001")
    with pytest.raises(ValueError, match="未知原型"):
        check_completeness(stock, "unknown_type")


def test_batch_check():
    stocks = [
        (_full_bank_stock(), "bank"),
        (_full_dividend_stock(), "high_dividend"),
        (_full_growth_stock(), "value_growth"),
    ]
    reports = batch_check(stocks)
    assert len(reports) == 3
    assert all(r.passed for r in reports)


def test_get_required_fields_bank():
    fields = get_required_fields("bank")
    assert "current_price" in fields
    assert "roe" in fields
    assert "shareholder_equity" in fields


# ── 网络测试（标记 network，交付前运行）────────────────────────────────────────

@pytest.mark.network
def test_network_bank_completeness():
    """网络版：对工行 601398 做银行原型完备性检查（需安装 akshare）。"""
    from data_provider.akshare.fetcher import AKShareFetcher
    from data_provider.manager import SourceManager
    from data_provider.provider import StockDataProvider

    mgr = SourceManager([AKShareFetcher()])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("601398")
    report = check_completeness(stock, "bank")
    print("\n", report.summary())
    # 完备性检查：若有缺失字段，打印但不强制 fail（网络数据有时不稳定）
    # 真正的门槛通过 test_completeness_acceptance.py 把关
    assert report.coverage_ratio > 0.6, f"覆盖率过低: {report.coverage_ratio:.1%}"


@pytest.mark.network
def test_network_dividend_completeness():
    """网络版：对长江电力 600900 做高股息原型完备性检查。"""
    from data_provider.akshare.fetcher import AKShareFetcher
    from data_provider.manager import SourceManager
    from data_provider.provider import StockDataProvider

    mgr = SourceManager([AKShareFetcher()])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600900")
    report = check_completeness(stock, "high_dividend")
    print("\n", report.summary())
    assert report.coverage_ratio > 0.6, f"覆盖率过低: {report.coverage_ratio:.1%}"


@pytest.mark.network
def test_network_growth_completeness():
    """网络版：对贵州茅台 600519 做价值成长原型完备性检查。"""
    from data_provider.akshare.fetcher import AKShareFetcher
    from data_provider.manager import SourceManager
    from data_provider.provider import StockDataProvider

    mgr = SourceManager([AKShareFetcher()])
    provider = StockDataProvider(mgr)
    stock = provider.get_stock_data("600519")
    report = check_completeness(stock, "value_growth")
    print("\n", report.summary())
    assert report.coverage_ratio > 0.6, f"覆盖率过低: {report.coverage_ratio:.1%}"
