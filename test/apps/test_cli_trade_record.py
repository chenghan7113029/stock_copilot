"""CLI trade record 单元测试。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_trade_record


@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_run_trade_record_persists_optional_checklist_id(
    mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)

    run_trade_record(
        "600519",
        "buy",
        1500.0,
        100,
        trade_date="2026-08-01",
        checklist_id=42,
        note="首次建仓",
    )

    record = mock_repo.return_value.add.call_args.args[0]
    assert record.action == "BUY"
    assert record.checklist_id == 42
    assert record.trade_date == datetime(2026, 8, 1)
    assert "交易已录入" in capsys.readouterr().out


@patch("apps.cli.TradeRecordRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_run_trade_record_allows_missing_optional_checklist_id(
    mock_cfg, mock_engine, mock_session_factory, mock_repo
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)

    run_trade_record("600519", "sell", 1600.0, 100)

    record = mock_repo.return_value.add.call_args.args[0]
    assert record.action == "SELL"
    assert record.checklist_id is None


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["trade", "record", "600519", "hold", "1500", "100"], "action 必须为 buy 或 sell"),
        (["trade", "record", "600519", "buy", "-1", "100"], "price 必须大于 0"),
        (["trade", "record", "600519", "buy", "1500", "0"], "quantity 必须大于 0"),
        (["trade", "record", "AAPL", "buy", "150", "10"], "仅支持 A 股"),
    ],
)
def test_trade_record_rejects_invalid_input_before_persisting(argv, message, capsys):
    with pytest.raises(SystemExit):
        main(argv)

    assert message in capsys.readouterr().err


@patch("apps.cli.run_trade_record")
def test_trade_record_command_routes_arguments(mock_record):
    main(
        [
            "trade",
            "record",
            "600519",
            "buy",
            "1500",
            "100",
            "--date",
            "2026-08-01",
            "--checklist-id",
            "42",
            "--note",
            "首次建仓",
        ]
    )

    mock_record.assert_called_once_with(
        "600519",
        "buy",
        1500.0,
        100,
        trade_date="2026-08-01",
        checklist_id=42,
        note="首次建仓",
        config=None,
    )
