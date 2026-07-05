"""银行原型 E2E（offline mock）：路由、估值聚合、指标缺失降级。"""

from __future__ import annotations

from unittest.mock import MagicMock

from common.models.stock_data import StockData
from service.value.analyzer import ValueAnalyzer
from service.value.valuation.engine import default_engine


def _bank_stock(**overrides) -> StockData:
    base = dict(
        code="601398",
        name="工商银行",
        industry="银行",
        current_price=5.5,
        bvps=8.0,
        roe=12.0,
        eps=1.0,
        pe_ratio=5.5,
        pb_ratio=0.68,
        shares_outstanding=350e9,
        net_income=300e9,
        total_assets=40e12,
        total_liabilities=37e12,
        shareholder_equity=3e12,
        net_interest_margin=2.05,
        provision_coverage=215.0,
        npl_ratio=1.35,
        dividend_per_share=0.3,
        dividend_yield=5.5,
        historical_pb=[0.55, 0.62, 0.68, 0.71, 0.65],
    )
    base.update(overrides)
    return StockData(**base)


def test_bank_e2e_offline_full_fields():
    provider = MagicMock()
    provider.get_stock_data_offline.return_value = _bank_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze_offline("601398")

    assert result is not None
    assert result.prototype == "bank"
    assert result.method_results
    assert "pb" in result.method_results
    assert "dcf" not in result.method_keys_used
    assert result.fair_value_range is not None
    assert result.fair_value_range.base > 0


def test_bank_e2e_graceful_when_nim_npl_missing():
    provider = MagicMock()
    provider.get_stock_data_offline.return_value = _bank_stock(
        net_interest_margin=None,
        npl_ratio=None,
        provision_coverage=None,
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze_offline("601398")

    assert result is not None
    assert result.prototype == "bank"
    assert result.method_results
    assert result.fair_value_range is not None
    assert result.fair_value_range.base > 0
