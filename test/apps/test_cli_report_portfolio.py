"""CLI portfolio report 单元测试。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_portfolio
from service.portfolio.models.portfolio_result import PortfolioAnalysisResult, PositionSummary


def _result() -> PortfolioAnalysisResult:
    return PortfolioAnalysisResult(
        total_value=3000.0,
        positions=[
            PositionSummary(
                code="600000",
                quantity=100,
                market_value=3000.0,
                weight=1.0,
                industry="银行",
                price_as_of=datetime(2026, 8, 1),
            )
        ],
        single_stock_weight={"600000": 1.0},
        top_n_concentration={3: 1.0},
        industry_exposure={"银行": 1.0},
        warnings=["⚠ 行业分类基于原始文本粗匹配，未做标准化归一，可能低估实际同行业暴露"],
    )


@patch("apps.cli.PortfolioAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_report_portfolio_formats_overview(
    mock_cfg, mock_engine, mock_session_factory, mock_trade_repo, mock_snapshot_repo, mock_analyzer, capsys
):
    mock_session_factory.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = _result()

    run_report_portfolio()

    mock_analyzer.return_value.analyze_offline.assert_called_once()
    assert "前 3 大持仓占比" in capsys.readouterr().out


@patch("apps.cli.PortfolioAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_report_portfolio_simulates_addition(
    mock_cfg, mock_engine, mock_session_factory, mock_trade_repo, mock_snapshot_repo, mock_analyzer, capsys
):
    mock_session_factory.return_value = MagicMock(return_value=MagicMock())
    simulated = _result()
    simulated.single_stock_weight["600519"] = 0.5
    mock_analyzer.return_value.simulate_add.return_value = simulated
    mock_analyzer.return_value.industry_exposure.return_value = 1.0

    run_report_portfolio("600519", add_quantity=500)

    mock_analyzer.return_value.simulate_add.assert_called_once_with("600519", 500)
    assert "以下为模拟计算，不代表任何实际交易操作" in capsys.readouterr().out


@patch("apps.cli.PortfolioAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_report_portfolio_rejects_empty_positions(
    mock_cfg, mock_engine, mock_session_factory, mock_trade_repo, mock_snapshot_repo, mock_analyzer, capsys
):
    mock_session_factory.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = PortfolioAnalysisResult(
        total_value=0.0,
        warnings=["⚠ 当前无持仓记录"],
    )

    with pytest.raises(SystemExit):
        run_report_portfolio()

    assert "当前无持仓记录" in capsys.readouterr().err


@patch("apps.cli.run_report_portfolio")
def test_report_portfolio_command_routes_simulation(mock_report):
    main(["report", "portfolio", "--code", "600519", "--add-quantity", "500", "--json"])

    mock_report.assert_called_once_with(
        "600519",
        add_quantity=500,
        as_json=True,
        output=None,
        config=None,
    )
