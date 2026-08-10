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
        code="601601",
        name="中国太保",
        industry="保险",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("601601")

    assert result.prototype == "unknown"
    assert result.methodology_applicable is False
    assert result.assessment == "方法暂不适用"
    assert result.confidence == "Low"
    assert any("保险" in warning and "EV/NBV" in warning for warning in result.warnings)
    assert any("不应用于买卖决策" in warning or "不能作为买卖依据" in warning for warning in result.warnings)
    assert not any("原型未识别" in warning for warning in result.warnings)


def test_ping_an_keeps_honesty_without_ev_inputs():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="601318",
        name="中国平安",
        industry="保险",
        current_price=50.0,
        shares_outstanding=18e9,
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("601318")

    assert result.prototype == "insurance"
    assert result.methodology_applicable is False
    assert result.assessment == "方法暂不适用"
    assert any("EV" in w or "NBV" in w or "保险" in w for w in result.warnings)
    assert any("不能作为买卖依据" in w for w in result.warnings)


def test_ping_an_graduates_with_ev_inputs():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="601318",
        name="中国平安",
        industry="保险",
        current_price=50.0,
        shares_outstanding=18e9,
    )
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        config={
            "value_analysis": {
                "insurance": {
                    "by_code": {
                        "601318": {
                            "embedded_value": 1200e9,
                            "nbv": 50e9,
                            "p_ev_fair": 1.0,
                        }
                    }
                }
            }
        },
    )

    result = analyzer.analyze("601318")

    assert result.prototype == "insurance"
    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"
    assert "P/EV" in result.assessment
    assert result.method_results["insurance_ev"].details.get("output_type") == "insurance_ev"


def test_byd_graduates_with_scenario_dcf_when_fcf_available():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="002594",
        name="比亚迪",
        industry="汽车整车",
        current_price=100.0,
        eps=5.0,
        bvps=40.0,
        growth_rate=20.0,
        total_assets=1e11,
        total_liabilities=4e10,
        net_income=1e10,
        fcf=5e9,
        shares_outstanding=1e9,
        proto="growth_manufacturing",
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("002594")

    assert result.prototype == "growth_manufacturing"
    assert "scenario_dcf" in result.method_keys_used
    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"
    assert "情景" in result.assessment or "介于" in result.assessment or "高于" in result.assessment or "低于" in result.assessment
    scenario = result.method_results["scenario_dcf"]
    assert scenario.details.get("output_type") == "scenario"
    assert set(scenario.details["scenarios"]) == {"bear", "base", "bull"}


def test_byd_keeps_honesty_when_scenario_dcf_cannot_run():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="002594",
        name="比亚迪",
        industry="汽车整车",
        current_price=100.0,
        growth_rate=20.0,
        total_assets=1e11,
        total_liabilities=4e10,
        # 无 fcf / shares → 情景 DCF 失败
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("002594")

    assert result.prototype == "growth_manufacturing"
    assert result.methodology_applicable is False
    assert result.assessment == "方法暂不适用"
    assert any("浅情景 DCF" in w for w in result.warnings)
    assert any("不能作为买卖依据" in w for w in result.warnings)


def test_focus_media_keeps_honesty_without_cycle_position():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="002027",
        name="分众传媒",
        industry="广告营销",
        current_price=10.0,
        growth_rate=8.0,
        total_assets=1e10,
        fcf=3e9,
        shares_outstanding=1e9,
        # 无 cycle_position / historical_pe → 不毕业
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("002027")

    assert result.prototype == "cashflow_ad_cycle"
    assert result.methodology_applicable is False
    assert result.assessment == "方法暂不适用"
    assert any("广告周期" in w or "周期位置" in w for w in result.warnings)
    assert any("不能作为买卖依据" in w for w in result.warnings)


def test_focus_media_graduates_with_cycle_inputs():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="002027",
        name="分众传媒",
        industry="广告营销",
        current_price=10.0,
        growth_rate=8.0,
        total_assets=1e10,
        fcf=5e9,
        shares_outstanding=1e9,
        eps=0.5,
        bvps=2.0,
        historical_roe=[18.0, 20.0, 22.0, 19.0],
    )
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        config={
            "value_analysis": {
                "cyclical": {"by_code": {"002027": {"cycle_position": "mid"}}}
            }
        },
    )

    result = analyzer.analyze("002027")

    assert result.prototype == "cashflow_ad_cycle"
    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"
    assert "周期位置" in result.assessment
    assert "cyclical_fcf" in result.method_keys_used
    assert result.method_results["cyclical_fcf"].details.get("output_type") == "cyclical"


def test_cssc_keeps_honesty_without_order_inputs():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="600072",
        name="中船科技",
        industry="国防军工",
        current_price=20.0,
        shares_outstanding=1e9,
        total_assets=1e11,
        total_liabilities=9e10,
    )
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("600072")

    assert result.prototype == "defense_orders"
    assert result.methodology_applicable is False
    assert result.assessment == "方法暂不适用"
    assert any("订单" in w for w in result.warnings)
    assert any("不能作为买卖依据" in w for w in result.warnings)


def test_cssc_graduates_with_order_inputs():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="600072",
        name="中船科技",
        industry="国防军工",
        current_price=20.0,
        shares_outstanding=1e9,
        tax_rate=25.0,
        net_debt=0.0,
    )
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        config={
            "value_analysis": {
                "defense_orders": {
                    "by_code": {
                        "600072": {
                            "order_backlog": 12e9,
                            "order_execution_years": 3.0,
                            "order_margin": 12.0,
                        }
                    }
                }
            }
        },
    )

    result = analyzer.analyze("600072")

    assert result.prototype == "defense_orders"
    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"
    assert "在手订单" in result.assessment
    assert result.method_results["defense_orders"].details.get("output_type") == "defense_orders"


def test_moutai_methodology_still_applicable():
    provider = MagicMock()
    provider.get_stock_data.return_value = _rich_value_growth_stock()
    analyzer = ValueAnalyzer(provider=provider, engine=default_engine())

    result = analyzer.analyze("600519")

    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"


def test_byd_override_to_value_growth_exempts_honesty_suppress():
    provider = MagicMock()
    provider.get_stock_data.return_value = StockData(
        code="002594",
        name="比亚迪",
        industry="汽车整车",
        current_price=100.0,
        eps=5.0,
        bvps=40.0,
        growth_rate=20.0,
        total_assets=1e11,
        total_liabilities=4e10,
        net_income=1e10,
        fcf=5e9,
        shares_outstanding=1e9,
        revenue=50e9,
        ebit=8e9,
        ebitda=10e9,
        shareholder_equity=6e10,
        roe=15.0,
        tax_rate=25.0,
    )
    override_repo = MagicMock()
    override_repo.get_by_code.return_value = MagicMock(
        prototype="value_growth",
        reason="人工验证情景假设",
    )
    analyzer = ValueAnalyzer(
        provider=provider,
        engine=default_engine(),
        override_repo=override_repo,
    )

    result = analyzer.analyze("002594")

    assert result.prototype == "value_growth"
    assert result.methodology_applicable is True
    assert result.assessment != "方法暂不适用"


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
