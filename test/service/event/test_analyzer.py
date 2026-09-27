"""EventAnalyzer 单元测试。"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

from data_provider.event.provider import EventData
from service.event.analyzer import EventAnalyzer


def _data() -> EventData:
    return EventData(
        code="600519",
        holder_trade_records=[],
        repurchase_records=[],
        share_float_records=[],
        pledge_records=[
            {
                "end_date": date.today().isoformat(),
                "pledge_ratio": 52.0,
                "unrest_pledge": 75.0,
                "total_share": 125008.0,
            }
        ],
        block_trade_records=[],
        northbound_records=[],
        data_timestamp=datetime(2026, 9, 24, 12, 0, 0),
    )


def test_analyze_offline_success() -> None:
    provider = MagicMock()
    provider.get_latest_offline.return_value = _data()
    analyzer = EventAnalyzer(provider)

    result = analyzer.analyze_offline("600519")

    assert result is not None
    assert result.code == "600519"
    assert result.pledge_ratio == 52.0
    assert any("质押比例 52%" in r for r in result.reasons)
    provider.get_latest_offline.assert_called_once_with("600519")
    provider.get_latest.assert_not_called()


def test_analyze_offline_no_cache_returns_none() -> None:
    provider = MagicMock()
    provider.get_latest_offline.return_value = None
    analyzer = EventAnalyzer(provider)

    assert analyzer.analyze_offline("600519") is None


def test_analyze_online_no_data_returns_warning_result() -> None:
    provider = MagicMock()
    provider.get_latest.return_value = (None, ["无治理事件缓存"])
    analyzer = EventAnalyzer(provider)

    result = analyzer.analyze("600519")

    assert result.code == "600519"
    assert any("治理事件数据不可用" in w for w in result.warnings)
