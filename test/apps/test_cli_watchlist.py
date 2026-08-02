"""CLI watchlist / --watchlist 批量入口测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.cli import main


def test_watchlist_list_invocation(capsys):
    with patch(
        "apps.cli.load_watchlist",
        return_value=[{"code": "600519", "name": "贵州茅台"}],
    ):
        with patch("apps.cli.watchlist_path", return_value="config/watchlist.yaml"):
            main(["watchlist", "list"])
    out = capsys.readouterr().out
    assert "600519" in out
    assert "贵州茅台" in out


def test_watchlist_add_invocation():
    with patch("apps.cli.add_to_watchlist", return_value=([{"code": "600519"}], True)) as mock_add:
        with patch("apps.cli.watchlist_path", return_value="config/watchlist.yaml"):
            main(["watchlist", "add", "600519", "--name", "贵州茅台"])
    mock_add.assert_called_once_with("600519", name="贵州茅台")


def test_watchlist_remove_missing_exits():
    with patch("apps.cli.remove_from_watchlist", return_value=([], False)):
        with pytest.raises(SystemExit) as exc:
            main(["watchlist", "remove", "999999"])
    assert exc.value.code == 1


@patch("apps.cli.run_sync")
@patch("apps.cli.watchlist_codes", return_value=["600519", "601398"])
def test_sync_watchlist_calls_each_code(mock_codes, mock_run):
    main(["sync", "--watchlist"])
    codes = [c.args[0] for c in mock_run.call_args_list]
    assert codes == ["600519", "601398"]


@patch("apps.cli.run_report_value")
@patch("apps.cli.watchlist_codes", return_value=["600519"])
def test_report_value_watchlist(mock_codes, mock_run):
    main(["report", "value", "--watchlist", "-o", "reports/wl"])
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == "600519"
    out = mock_run.call_args.kwargs["output"].replace("\\", "/")
    assert out.endswith("600519_value.md")


def test_sync_code_and_watchlist_conflict():
    with pytest.raises(SystemExit) as exc:
        main(["sync", "600519", "--watchlist"])
    assert exc.value.code == 2


@patch("apps.cli.watchlist_codes", return_value=[])
def test_sync_empty_watchlist_exits(mock_codes):
    with pytest.raises(SystemExit) as exc:
        main(["sync", "--watchlist"])
    assert exc.value.code == 1
