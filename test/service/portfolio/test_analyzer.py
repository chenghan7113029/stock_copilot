"""PortfolioAnalyzer 的离线组合统计单元测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from dao.models import TradeRecord
from service.portfolio.analyzer import PortfolioAnalyzer


def _position(code: str, quantity: int) -> TradeRecord:
    return TradeRecord(
        code=code,
        action="BUY",
        quantity=quantity,
        price=10.0,
        trade_date=datetime(2026, 8, 1),
    )


def _snapshot(
    code: str,
    price: float | None,
    industry: str | None,
    *,
    fetched_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        current_price=price,
        industry=industry,
        data_timestamp=fetched_at,
        fetched_at=fetched_at or datetime.now(),
    )


def _analyzer(
    positions: list[TradeRecord],
    snapshots: dict[str, list[SimpleNamespace]],
) -> tuple[PortfolioAnalyzer, MagicMock, MagicMock]:
    trade_repo = MagicMock()
    trade_repo.find_open_positions.return_value = positions
    snapshot_repo = MagicMock()
    snapshot_repo.find_by_code.side_effect = lambda code: snapshots.get(code, [])
    return PortfolioAnalyzer(trade_repo, snapshot_repo), trade_repo, snapshot_repo


def test_analyze_offline_calculates_weights_top_n_and_industry_exposure():
    analyzer, _, _ = _analyzer(
        [_position("600000", 100), _position("600001", 200), _position("600002", 100)],
        {
            "600000": [_snapshot("600000", 10.0, "银行")],
            "600001": [_snapshot("600001", 20.0, "银行")],
            "600002": [_snapshot("600002", 20.0, "白酒")],
            "600003": [_snapshot("600003", 30.0, "银行")],
        },
    )

    result = analyzer.analyze_offline()

    assert result.total_value == 7000.0
    assert result.single_stock_weight == {"600000": 1 / 7, "600001": 4 / 7, "600002": 2 / 7}
    assert result.top_n_concentration[3] == 1.0
    assert result.industry_exposure["银行"] == 5 / 7
    assert analyzer.industry_exposure("600003") == 5 / 7
    assert any("原始文本粗匹配" in warning for warning in result.warnings)


def test_analyze_offline_returns_safe_empty_result():
    analyzer, _, _ = _analyzer([], {})

    result = analyzer.analyze_offline()

    assert result.total_value == 0.0
    assert result.positions == []
    assert result.single_stock_weight == {}
    assert result.top_n_concentration == {}
    assert any("当前无持仓" in warning for warning in result.warnings)


def test_analyze_offline_warns_for_stale_price():
    stale = datetime.now() - timedelta(days=8)
    analyzer, _, _ = _analyzer(
        [_position("600000", 100)],
        {"600000": [_snapshot("600000", 10.0, "银行", fetched_at=stale)]},
    )

    result = analyzer.analyze_offline()

    assert result.positions[0].price_as_of == stale
    assert any("价格数据已过期" in warning for warning in result.warnings)


def test_industry_exposure_returns_none_and_warns_without_target_industry():
    analyzer, _, _ = _analyzer(
        [_position("600000", 100)],
        {"600000": [_snapshot("600000", 10.0, "银行")]},
    )
    result = analyzer.analyze_offline()

    assert analyzer.industry_exposure("600003") is None
    assert any("无法获取行业信息" in warning for warning in result.warnings)


def test_simulate_add_recalculates_weight_without_writing_trade_records():
    analyzer, trade_repo, _ = _analyzer(
        [_position("600000", 100), _position("600001", 100)],
        {
            "600000": [_snapshot("600000", 10.0, "银行")],
            "600001": [_snapshot("600001", 10.0, "白酒")],
        },
    )

    result = analyzer.simulate_add("600000", 100)

    assert result.single_stock_weight["600000"] == 2 / 3
    assert result.industry_exposure["银行"] == 2 / 3
    trade_repo.add.assert_not_called()
    trade_repo.find_open_positions.assert_called_once()
