from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_sync_market
from common.exceptions import DataProviderError


def _cfg_with_sources(*names: str, **extra):
    cfg = {
        "logging": {"cli_progress": False},
        "data_sources": {
            "enabled": [{"name": n, "priority": i + 1} for i, n in enumerate(names)]
        },
    }
    cfg.update(extra)
    return cfg


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_success(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare", "baostock")
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 50,
        "limit_down_count": 10,
        "fear_greed_index": 70.0,
    }

    run_sync_market()

    assert "市场情绪同步完成" in capsys.readouterr().out
    assert session.commit.call_count >= 1


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_data_source_error(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare")
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_provider.from_config.return_value.fetch_and_persist_today.side_effect = DataProviderError(
        "接口不可用"
    )

    with pytest.raises(SystemExit) as exc:
        run_sync_market()

    assert exc.value.code == 1
    assert "市场情绪同步失败" in capsys.readouterr().err


@patch("apps.cli.load_app_config")
def test_sync_market_no_sentiment_source_exits(mock_cfg, capsys) -> None:
    mock_cfg.return_value = _cfg_with_sources("baostock")

    with pytest.raises(SystemExit) as exc:
        run_sync_market()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "依赖已配置的数据源" in err
    assert "必须启用 AKShare" not in err


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_tushare_only_ok(mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare")
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
    assert session.commit.call_count >= 1


@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_legacy_akshare_still_allowed(
    mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, capsys
) -> None:
    mock_cfg.return_value = _cfg_with_sources("akshare")
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 10,
        "limit_down_count": 2,
        "fear_greed_index": 40.0,
    }

    run_sync_market()
    assert "市场情绪同步完成" in capsys.readouterr().out
    assert session.commit.call_count >= 1


@patch("apps.cli.run_sync_market")
def test_cli_sync_market_invocation(mock_run) -> None:
    main(["sync", "market"])

    mock_run.assert_called_once_with(config=None, top_list_days=20)


@patch("apps.cli.TopListProvider")
@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_backfills_top_list(
    mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, mock_top_list_cls, capsys
) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare")
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 30,
        "limit_down_count": 5,
        "fear_greed_index": 55.0,
    }
    mock_top_list_cls.from_config.return_value.backfill.return_value = (2, [])

    run_sync_market(top_list_days=2)

    mock_top_list_cls.from_config.return_value.backfill.assert_called_once()
    out = capsys.readouterr().out
    assert "龙虎榜回填 2 日" in out


@patch("apps.cli.TopListProvider")
@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_top_list_days_zero_skips(
    mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, mock_top_list_cls, capsys
) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare")
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 30,
        "limit_down_count": 5,
        "fear_greed_index": 55.0,
    }
    mock_top_list_cls.from_config.return_value.backfill.return_value = (0, [])

    run_sync_market(top_list_days=0)

    kwargs = mock_top_list_cls.from_config.return_value.backfill.call_args
    assert kwargs.args[0] == 0
    assert "龙虎榜跳过" in capsys.readouterr().out


@patch("apps.cli.TopListProvider")
@patch("apps.cli.MarketSentimentProvider")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_sync_market_top_list_failure_does_not_block(
    mock_cfg, mock_sf, mock_engine, mock_repo, mock_provider, mock_top_list_cls, capsys
) -> None:
    mock_cfg.return_value = _cfg_with_sources("tushare")
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_provider.from_config.return_value.fetch_and_persist_today.return_value = {
        "limit_up_count": 30,
        "limit_down_count": 5,
        "fear_greed_index": 55.0,
    }
    mock_top_list_cls.from_config.return_value.backfill.side_effect = RuntimeError(
        "top list down"
    )

    run_sync_market()

    captured = capsys.readouterr()
    assert "市场情绪同步完成" in captured.out
    assert "龙虎榜回填失败" in captured.err
