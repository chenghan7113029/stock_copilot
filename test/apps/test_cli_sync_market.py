from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_sync_market
from common.exceptions import DataProviderError


def _cfg_with_akshare(**extra):
    cfg = {
        "logging": {"cli_progress": False},
        "data_sources": {"enabled": [{"name": "akshare", "priority": 1}]},
    }
    cfg.update(extra)
    return cfg


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_success(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = _cfg_with_akshare()
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 50,
        "limit_down_count": 10,
        "fear_greed_index": 70.0,
    }

    run_sync_market()

    assert "市场情绪同步完成" in capsys.readouterr().out
    session.commit.assert_called_once()


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_data_source_error(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = _cfg_with_akshare()
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_provider.from_config.return_value.fetch_and_persist_today.side_effect = DataProviderError(
        "接口不可用"
    )

    with pytest.raises(SystemExit) as exc:
        run_sync_market()

    assert exc.value.code == 1
    assert "市场情绪同步失败" in capsys.readouterr().err


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_tushare_only_ok(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = {
        "logging": {"cli_progress": False},
        "data_sources": {"enabled": [{"name": "tushare", "priority": 1}]},
    }
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 30,
        "limit_down_count": 5,
        "fear_greed_index": 55.0,
        "source": "tushare",
        "warnings": ["涨跌停家数为近似"],
    }

    run_sync_market()

    out = capsys.readouterr()
    assert "市场情绪同步完成" in out.out
    assert "近似" in out.err
    session.commit.assert_called_once()


@patch("apps.cli.run_sync_market")
def test_cli_sync_market_invocation(mock_run) -> None:
    main(["sync", "market"])

    mock_run.assert_called_once_with(config=None)
