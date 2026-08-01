"""CLI position set 单元测试。"""

from unittest.mock import MagicMock, patch

from apps.cli import main, run_position_set


@patch("apps.cli.PositionRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_run_position_set_persists_and_confirms(mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)

    run_position_set("600519", cost_price=1500.0, shares=100)

    mock_repo.return_value.upsert.assert_called_once_with("600519", 1500.0, 100)
    session.commit.assert_called_once()
    assert "持仓已录入" in capsys.readouterr().out


@patch("apps.cli.run_position_set")
def test_position_set_command_routes_arguments(mock_set):
    main(["position", "set", "600519", "--cost", "1500", "--shares", "100"])

    mock_set.assert_called_once_with("600519", cost_price=1500.0, shares=100, config=None)
