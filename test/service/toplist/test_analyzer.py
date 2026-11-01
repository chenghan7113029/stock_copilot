"""TopListAnalyzer 单元测试（fake provider，不联网）。"""

from __future__ import annotations

from datetime import date, timedelta

from data_provider.toplist.provider import TopListData
from service.toplist.analyzer import TopListAnalyzer
from service.toplist.models.top_list_result import ActiveLevel, InstParticipation


class _FakeProvider:
    def __init__(self, data: TopListData | None, sync_warnings: list[str] | None = None) -> None:
        self._data = data
        self._sync_warnings = list(sync_warnings or [])
        self.sync_calls = 0

    def sync_latest(self, on_progress=None) -> tuple[str | None, list[str]]:
        self.sync_calls += 1
        return None, list(self._sync_warnings)

    def get_offline(self, code: str, window_days: int) -> TopListData | None:
        return self._data


def _full_coverage(days: list[str]) -> list[str]:
    """水位覆盖到窗口起点（避免覆盖告警干扰断言）。"""
    today = date.today()
    start = (today - timedelta(days=90)).isoformat()
    return sorted({start, *days})


def _event(trade_date: str, reason: str, l_amount: float, net_amount: float | None) -> dict:
    return {
        "trade_date": trade_date,
        "reason": reason,
        "l_amount": l_amount,
        "net_amount": net_amount,
        "fetched_at": None,
    }


def _inst(trade_date: str, exalter: str, net_buy: float) -> dict:
    return {
        "trade_date": trade_date,
        "exalter": exalter,
        "buy": abs(net_buy) + 1.0,
        "sell": 1.0,
        "net_buy": net_buy,
        "reason": "日涨幅偏离值达到7%的前5只证券",
        "fetched_at": None,
    }


def test_offline_analysis_builds_deterministic_result() -> None:
    today = date.today()
    d1 = (today - timedelta(days=2)).isoformat()
    d2 = (today - timedelta(days=1)).isoformat()
    data = TopListData(
        code="300530",
        list_records=[
            _event(d1, "日涨幅达到15%的前5只证券", 1.3e8, 7.6e7),
            _event(d2, "日换手率达到20%的前5只证券", 5.5e8, -8.5e7),
        ],
        inst_records=[_inst(d2, "机构专用", 1.4e7)],
        covered_dates=_full_coverage([d1, d2]),
    )
    analyzer = TopListAnalyzer(_FakeProvider(data))

    result = analyzer.analyze_offline("300530")

    assert result is not None
    assert result.appearance_count == 2
    assert result.active_level is ActiveLevel.OCCASIONAL
    assert result.latest_trade_date == d2
    assert result.latest_net_amount == -8.5e7
    assert result.inst_net_buy == 1.4e7
    assert result.inst_participation is InstParticipation.INST_BUY
    assert "换手率" in result.reason_categories
    assert result.coverage_trade_days == 3
    assert result.reasons


def test_offline_returns_none_without_cache() -> None:
    analyzer = TopListAnalyzer(_FakeProvider(None))
    assert analyzer.analyze_offline("600519") is None


def test_inst_missing_degrades_without_institution_claims() -> None:
    today = date.today()
    d1 = (today - timedelta(days=1)).isoformat()
    data = TopListData(
        code="600519",
        list_records=[_event(d1, "日涨幅偏离值达到7%的前5只证券", 3.0e8, 6.8e7)],
        inst_records=[],
        covered_dates=_full_coverage([d1]),
    )
    result = TopListAnalyzer(_FakeProvider(data)).analyze_offline("600519")

    assert result is not None
    assert result.inst_net_buy is None
    assert result.inst_participation is None
    assert any("机构席位数据缺失" in w for w in result.warnings)
    assert not any("机构席位净买" in r for r in result.reasons)


def test_coverage_insufficient_emits_warning() -> None:
    today = date.today()
    d1 = (today - timedelta(days=1)).isoformat()
    data = TopListData(
        code="600519",
        list_records=[_event(d1, "日涨幅偏离值达到7%的前5只证券", 3.0e8, 6.8e7)],
        inst_records=[],
        covered_dates=[d1],
    )
    result = TopListAnalyzer(_FakeProvider(data)).analyze_offline("600519")

    assert result is not None
    assert any("可能偏低" in w for w in result.warnings)


def test_not_listed_stock_reports_zero_with_coverage() -> None:
    """有覆盖水位但未上榜 → 0 次上榜 + 未上榜分档（不是 None）。"""
    today = date.today()
    data = TopListData(
        code="600519",
        list_records=[],
        inst_records=[],
        covered_dates=_full_coverage([]),
    )
    result = TopListAnalyzer(_FakeProvider(data)).analyze_offline("600519")

    assert result is not None
    assert result.appearance_count == 0
    assert result.active_level is ActiveLevel.NOT_LISTED
    assert any("未上榜" in r for r in result.reasons)


def test_analyze_online_syncs_and_carries_warnings() -> None:
    today = date.today()
    d1 = (today - timedelta(days=1)).isoformat()
    data = TopListData(
        code="600519",
        list_records=[_event(d1, "日涨幅偏离值达到7%的前5只证券", 3.0e8, 6.8e7)],
        inst_records=[],
        covered_dates=_full_coverage([d1]),
    )
    provider = _FakeProvider(data, sync_warnings=["同步告警"])
    result = TopListAnalyzer(provider).analyze("600519")

    assert provider.sync_calls == 1
    assert any("同步告警" in w for w in result.warnings)


def test_analyze_online_without_data_returns_warnings_only() -> None:
    result = TopListAnalyzer(_FakeProvider(None)).analyze("600519")
    assert result.appearance_count == 0
    assert any("数据不可用" in w for w in result.warnings)
