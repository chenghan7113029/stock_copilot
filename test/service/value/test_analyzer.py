"""ValueAnalyzer 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from common.exceptions import UnsupportedMarketError
from common.models.stock_data import StockData
from service.value.aggregator import AggregateResult, ValuationAggregator
from service.value.analyzer import ValueAnalyzer
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.engine import default_engine


def _rich_value_growth_stock() -> StockData:
    return StockData(
        code="600519",
        name="贵州茅台",
        current_price=1500.0,
        eps=50.0,
        bvps=200.0,
        shares_outstanding=1.25e9,
        revenue=120e9,
        net_income=60e9,
        ebit=80e9,
        ebitda=85e9,
        fcf=55e9,
        total_assets=200e9,
        total_liabilities=50e9,
        shareholder_equity=150e9,
        growth_rate=15.0,
        roe=30.0,
        tax_rate=25.0,
        dividend_per_share=20.0,
        dividend_yield=1.3,
    )


def _bank_stock() -> StockData:
    return StockData(
        code="601398",
        name="工商银行",
        current_price=5.0,
        bvps=8.0,
        shares_outstanding=350e9,
        net_income=300e9,
        total_assets=40e12,
        total_liabilities=37e12,
        shareholder_equity=3e12,
    )


def _empty_stock() -> StockData:
    return StockData(code="999999", name="Unknown")


def test_analyze_value_growth_prototype():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("600519")

    assert isinstance(result, ValueAnalysisResult)
    assert result.prototype == "value_growth"
    assert result.fair_value_range is not None
    assert "dcf" in result.method_keys_used
    assert "epv" in result.method_keys_used
    assert result.warnings is not None
    assert result.method_results is not None


def test_analyze_bank_prototype():
    provider = MagicMock()
    provider.get_stock_data.return_value = _bank_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("601398")

    assert result.prototype == "bank"
    assert "pb" in result.method_keys_used
    assert "residual_income" in result.method_keys_used
    assert "dcf" not in result.method_keys_used


def test_non_a_share_rejected():
    provider = MagicMock()
    provider.get_stock_data.side_effect = UnsupportedMarketError("不支持")
    analyzer = ValueAnalyzer(provider=provider)

    with pytest.raises(UnsupportedMarketError):
        analyzer.analyze("AAPL")


def test_unknown_prototype_warning():
    provider = MagicMock()
    provider.get_stock_data.return_value = _empty_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("999999")

    assert result.prototype == "unknown"
    assert "graham_number" in result.method_keys_used
    assert any("原型未识别" in w for w in result.warnings)


def test_known_insurance_industry_uses_specific_methodology_gap_warning():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="601318",
        name="中国平安",
        industry="保险",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("601318")

    assert result.prototype == "unknown"
    assert any("保险" in warning and "EV/NBV" in warning for warning in result.warnings)
    assert not any("原型未识别" in warning for warning in result.warnings)


def test_unknown_prototype_with_blank_industry_keeps_generic_warning():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="999999",
        name="Unknown",
        industry="",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("999999")

    assert result.prototype == "unknown"
    assert any("原型未识别" in warning for warning in result.warnings)


def test_output_fields_complete():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("600519")

    assert result.code == "600519"
    assert result.name == "贵州茅台"
    assert result.current_price == 1500.0
    assert isinstance(result.method_keys_used, list)
    assert isinstance(result.method_results, dict)
    assert isinstance(result.warnings, list)
    assert result.value_score is None


def test_analyze_propagates_value_trap_alert():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    aggregator = MagicMock(spec=ValuationAggregator)
    aggregator.aggregate.return_value = AggregateResult(
        assessment="合理",
        confidence="Medium",
        value_trap_alert="🚨 疑似价值陷阱（High Risk）：财务健康。",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine(), aggregator=aggregator)

    result = analyzer.analyze("600519")

    assert result.value_trap_alert == "🚨 疑似价值陷阱（High Risk）：财务健康。"


def test_analyze_offline_propagates_value_trap_alert():
    provider = MagicMock()
    provider.get_stock_data_offline.return_value = _rich_value_growth_stock()
    aggregator = MagicMock(spec=ValuationAggregator)
    aggregator.aggregate.return_value = AggregateResult(
        assessment="合理",
        confidence="Medium",
        value_trap_alert="🚨 疑似价值陷阱（High Risk）：业务恶化。",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine(), aggregator=aggregator)

    result = analyzer.analyze_offline("600519")

    assert result is not None
    assert result.value_trap_alert == "🚨 疑似价值陷阱（High Risk）：业务恶化。"


def test_analyze_applies_persisted_prototype_override_and_warns():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    override_repo = MagicMock()
    override_repo.get_by_code.return_value = MagicMock(
        prototype="high_dividend",
        reason="管理层转向稳定分红策略",
    )
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        override_repo=override_repo,
    )

    result = analyzer.analyze("600519")

    override_repo.get_by_code.assert_called_once_with("600519")
    assert result.prototype == "high_dividend"
    assert "ddm" in result.method_keys_used
    assert any(
        "high_dividend" in warning and "管理层转向稳定分红策略" in warning
        for warning in result.warnings
    )


def test_analyze_without_override_record_preserves_existing_behavior():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    override_repo = MagicMock()
    override_repo.get_by_code.return_value = None
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        override_repo=override_repo,
    )

    result = analyzer.analyze("600519")

    override_repo.get_by_code.assert_called_once_with("600519")
    assert result.prototype == "value_growth"
    assert not any("原型已人工覆盖" in warning for warning in result.warnings)
