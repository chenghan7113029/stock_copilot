"""CLI feishu push 测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.cli import main
from service.feishu.pipeline import PushRunResult
from service.feishu.publisher import FeishuPublisherError


@patch("apps.cli.run_feishu_push")
def test_feishu_push_dry_run(mock_push, capsys, tmp_path):
    mock_push.return_value = PushRunResult(
        succeeded=["600519"],
        local_paths={"600519": str(tmp_path / "600519_dual.md")},
    )
    main(["feishu", "push", "600519", "--dry-run", "--no-sync", "--slot", "1700"])
    assert mock_push.call_args.kwargs["dry_run"] is True
    assert mock_push.call_args.kwargs["slot"] == "1700"
    assert "dry-run" in capsys.readouterr().out


@patch("apps.cli.run_feishu_push")
def test_feishu_push_skip_non_trading_day(mock_push, capsys):
    mock_push.return_value = PushRunResult(skipped=True, skip_reason="非交易日，跳过飞书推送（2026-08-15）")
    main(["feishu", "push", "600519", "--no-sync"])
    assert "[skip]" in capsys.readouterr().out


@patch("apps.cli.run_feishu_push")
def test_feishu_push_missing_cli_nonzero(mock_push):
    mock_push.side_effect = FeishuPublisherError("未找到 lark-cli")
    with pytest.raises(SystemExit) as exc:
        main(["feishu", "push", "600519", "--no-sync"])
    assert exc.value.code == 1
