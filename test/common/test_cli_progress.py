"""CliProgress 单元测试。"""

from __future__ import annotations

from common.cli_progress import CliProgress, cli_progress_enabled


def test_emit_includes_elapsed(capsys):
    p = CliProgress("sync")
    p.emit("hello")
    out = capsys.readouterr().out
    assert "[sync]" in out
    assert "hello" in out
    assert "s)" in out


def test_disabled_emits_nothing(capsys):
    p = CliProgress("sync", enabled=False)
    p.emit("hello")
    assert capsys.readouterr().out == ""


def test_cli_progress_enabled_default():
    assert cli_progress_enabled({}) is True


def test_cli_progress_enabled_config():
    assert cli_progress_enabled({"logging": {"cli_progress": False}}) is False
