"""CLI sync 命令测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from apps.cli import main, run_sync
from common.models.stock_data import StockData


@patch("apps.cli.load_app_config")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.StockDataProvider")
@patch("apps.cli.KlineProvider")
def test_sync_success(mock_kline_cls, mock_value_cls, mock_sf, mock_engine, mock_cfg):
    mock_cfg.return_value = {"tech": {"kline_days": 90}}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)

    stock = StockData(code="600519", exchange="SH", name="贵州茅台")
    stock.current_price = 1800.0
    mock_value_cls.from_config.return_value.get_stock_data.return_value = stock

    kline = mock_kline_cls.return_value
    kline.get_kline.return_value = (pd.DataFrame({"date": ["2025-06-01"]}), [], "eod")

    run_sync("600519")
    session.commit.assert_called_once()
    kline.get_kline.assert_called_once_with(
        "600519", days=90, use_realtime=False, persist_today=False
    )


@patch("apps.cli.load_app_config")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.StockDataProvider")
@patch("apps.cli.KlineProvider")
def test_sync_realtime(mock_kline_cls, mock_value_cls, mock_sf, mock_engine, mock_cfg):
    mock_cfg.return_value = {"tech": {"kline_days": 90}}
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_value_cls.from_config.return_value.get_stock_data.return_value = StockData(
        code="600519", exchange="SH"
    )
    mock_kline_cls.return_value.get_kline.return_value = (
        pd.DataFrame({"date": ["2025-06-28"]}),
        [],
        "realtime",
    )

    run_sync("600519", realtime=True)
    mock_kline_cls.return_value.get_kline.assert_called_once_with(
        "600519", days=90, use_realtime=True, persist_today=True
    )


@patch("apps.cli.run_sync")
def test_cli_sync_invocation(mock_run_sync):
    main(["sync", "600519"])
    mock_run_sync.assert_called_once_with("600519", realtime=False)


@patch("apps.cli.load_app_config")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.StockDataProvider")
def test_sync_network_error_exits(mock_value_cls, mock_sf, mock_engine, mock_cfg, capsys):
    mock_cfg.return_value = {"tech": {"kline_days": 90}}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_value_cls.from_config.return_value.get_stock_data.side_effect = RuntimeError("network down")

    with pytest.raises(SystemExit) as exc:
        run_sync("600519")
    assert exc.value.code == 1
