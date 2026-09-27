"""FundFlowAnalyzer 单元测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from data_provider.fundflow.provider import FundFlowData
from service.fundflow.analyzer import FundFlowAnalyzer
from service.fundflow.models.fund_flow_result import LeverageDirection


def _data() -> FundFlowData:
    return FundFlowData(
        code="600519",
        margin_records=[
            {"trade_date": "2026-09-18", "rzrqye": 1.0e8, "rqye": 1.0e6},
            {"trade_date": "2026-09-19", "rzrqye": 1.1e8, "rqye": 1.1e6},
        ],
        moneyflow_records=[
            {"trade_date": "2026-09-18", "net_mf_amount": 1000.0},
            {"trade_date": "2026-09-19", "net_mf_amount": -200.0},
        ],
        data_timestamp=datetime(2026, 9, 24, 12, 0, 0),
    )


def test_analyze_offline_success() -> None:
    provider = MagicMock()
    provider.get_latest_offline.return_value = _data()
    analyzer = FundFlowAnalyzer(provider)

    result = analyzer.analyze_offline("600519")

    assert result is not None
    assert result.code == "600519"
    assert result.margin_balance_change_pct == pytest.approx(10.0)
    assert result.main_net_inflow_5d == 800.0
    assert result.leverage_direction == LeverageDirection.ADD_LEVERAGE
    assert any("两融余额" in r for r in result.reasons)
    assert result.data_timestamp is not None
    provider.get_latest_offline.assert_called_once_with("600519")
    provider.get_latest.assert_not_called()


def test_analyze_offline_no_cache_returns_none() -> None:
    provider = MagicMock()
    provider.get_latest_offline.return_value = None
    analyzer = FundFlowAnalyzer(provider)

    assert analyzer.analyze_offline("600519") is None


def test_analyze_online_no_data_returns_warning_result() -> None:
    provider = MagicMock()
    provider.get_latest.return_value = (None, ["无资金面缓存"])
    analyzer = FundFlowAnalyzer(provider)

    result = analyzer.analyze("600519")

    assert result.code == "600519"
    assert result.margin_balance_change_pct is None
    assert any("资金面数据不可用" in w for w in result.warnings)
