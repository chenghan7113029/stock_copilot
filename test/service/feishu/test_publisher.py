"""lark-cli publisher 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from common.config_loader import FeishuConfig
from service.feishu.publisher import (
    CommandResult,
    FeishuPublisherError,
    LarkCliPublisher,
    extract_doc_url,
    push_title,
)


def test_push_title_includes_date_and_slot():
    assert push_title("贵州茅台", day_iso="2026-08-18", slot="1700") == "今日研报_贵州茅台_2026-08-18_1700"
    assert (
        push_title("贵州茅台", day_iso="2026-08-18", slot="1700", tag="红蓝对抗")
        == "今日研报_贵州茅台_红蓝对抗_2026-08-18_1700"
    )


def test_extract_doc_url_from_ok_envelope():
    url = extract_doc_url({"ok": True, "data": {"doc_url": "https://feishu.cn/docx/abc"}})
    assert url == "https://feishu.cn/docx/abc"


class ScriptedRunner:
    def __init__(self, responses: list[CommandResult]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> CommandResult:
        self.calls.append(argv)
        if not self.responses:
            raise AssertionError(f"unexpected call: {argv}")
        return self.responses.pop(0)


def _cfg(**kwargs) -> FeishuConfig:
    data = dict(lark_cli="lark-cli", chat_id="oc_chat")
    data.update(kwargs)
    return FeishuConfig(**data)


def test_publish_create_then_send(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = tmp_path / "600519_dual.md"
    md.write_text("# dual", encoding="utf-8")
    runner = ScriptedRunner(
        [
            CommandResult(
                0,
                json.dumps({"ok": True, "data": {"doc_url": "https://feishu.cn/docx/d1"}}),
                "",
                (),
            ),
            CommandResult(0, json.dumps({"ok": True, "data": {}}), "", ()),
        ]
    )
    pub = LarkCliPublisher(_cfg(), runner=runner, which=lambda _: "lark-cli")
    result = pub.publish(
        code="600519",
        name="贵州茅台",
        md_path=md,
        slot="1700",
        day_iso="2026-08-18",
    )
    assert result.error is None
    assert result.doc_url == "https://feishu.cn/docx/d1"
    assert result.title == "今日研报_贵州茅台_2026-08-18_1700"
    assert runner.calls[0][1:3] == ["docs", "+create"]
    assert runner.calls[0][runner.calls[0].index("--as") + 1] == "user"
    assert "--title" in runner.calls[0]
    content_arg = runner.calls[0][runner.calls[0].index("--content") + 1]
    assert content_arg.startswith("@")
    assert content_arg.endswith("600519_dual.md")
    assert "\n" not in content_arg
    assert runner.calls[1][1:3] == ["im", "+messages-send"]
    assert runner.calls[1][runner.calls[1].index("--as") + 1] == "user"
    assert "--chat-id" in runner.calls[1]
    content = runner.calls[1][runner.calls[1].index("--content") + 1]
    payload = json.loads(content)
    assert payload["text"] == (
        "今日研报_贵州茅台_2026-08-18_1700\nhttps://feishu.cn/docx/d1"
    )
    assert "\\n" in content  # argv 中必须是转义换行，不能是真实 \\n 字符
    assert "\n" not in content


def test_markdown_content_arg_uses_relative_atfile(tmp_path: Path, monkeypatch):
    md = tmp_path / "reports" / "x_dual.md"
    md.parent.mkdir(parents=True)
    md.write_text("# dual\n\nbody", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    arg = LarkCliPublisher._markdown_content_arg(md)
    assert arg == "@reports/x_dual.md"


def test_publish_message_content_avoids_raw_newlines_in_argv(tmp_path: Path, monkeypatch):
    """回归：Windows 下 --text 含真实换行会导致 URL 被截断。"""
    monkeypatch.chdir(tmp_path)
    md = tmp_path / "600519_dual.md"
    md.write_text("# dual", encoding="utf-8")
    runner = ScriptedRunner(
        [
            CommandResult(
                0,
                json.dumps({"ok": True, "data": {"doc_url": "https://feishu.cn/docx/d1"}}),
                "",
                (),
            ),
            CommandResult(0, json.dumps({"ok": True, "data": {}}), "", ()),
        ]
    )
    pub = LarkCliPublisher(_cfg(), runner=runner, which=lambda _: "lark-cli")
    pub.publish(
        code="600519",
        name="贵州茅台",
        md_path=md,
        slot="1700",
        day_iso="2026-08-18",
    )
    send = runner.calls[1]
    assert "--text" not in send
    content = send[send.index("--content") + 1]
    assert "\n" not in content
    assert "https://feishu.cn/docx/d1" in json.loads(content)["text"]


def test_publish_prefers_user_id_over_chat_id(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = tmp_path / "600519_dual.md"
    md.write_text("# dual", encoding="utf-8")
    runner = ScriptedRunner(
        [
            CommandResult(
                0,
                json.dumps({"ok": True, "data": {"url": "https://feishu.cn/docx/d2"}}),
                "",
                (),
            ),
            CommandResult(0, json.dumps({"ok": True, "data": {}}), "", ()),
        ]
    )
    pub = LarkCliPublisher(
        _cfg(user_id="ou_me", chat_id="oc_chat", folder_token="fld_x"),
        runner=runner,
        which=lambda _: "lark-cli",
    )
    result = pub.publish(
        code="600519",
        name="贵州茅台",
        md_path=md,
        slot="1700",
        day_iso="2026-08-18",
    )
    assert result.error is None
    create_argv = runner.calls[0]
    assert create_argv[create_argv.index("--as") + 1] == "user"
    assert create_argv[create_argv.index("--parent-token") + 1] == "fld_x"
    send_argv = runner.calls[1]
    assert send_argv[send_argv.index("--as") + 1] == "user"
    assert "--user-id" in send_argv
    assert send_argv[send_argv.index("--user-id") + 1] == "ou_me"
    assert "--chat-id" not in send_argv


def test_missing_cli_raises():
    pub = LarkCliPublisher(_cfg(), which=lambda _: None)
    try:
        pub.resolve_binary()
        raise AssertionError("expected missing cli")
    except FeishuPublisherError as exc:
        assert "lark-cli auth login" in str(exc)


def test_dry_run_does_not_run_cli(tmp_path: Path):
    md = tmp_path / "600519_dual.md"
    md.write_text("# dual", encoding="utf-8")
    runner = ScriptedRunner([])
    pub = LarkCliPublisher(_cfg(), runner=runner, which=lambda _: "lark-cli")
    result = pub.publish(
        code="600519",
        name="茅台",
        md_path=md,
        slot="0900",
        day_iso="2026-08-18",
        dry_run=True,
    )
    assert result.dry_run is True
    assert runner.calls == []


def test_create_failure_does_not_send(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = tmp_path / "600519_dual.md"
    md.write_text("# dual", encoding="utf-8")
    runner = ScriptedRunner(
        [CommandResult(1, json.dumps({"ok": False, "error": {"message": "no auth"}}), "", ())]
    )
    pub = LarkCliPublisher(_cfg(), runner=runner, which=lambda _: "lark-cli")
    result = pub.publish(
        code="600519",
        name="茅台",
        md_path=md,
        slot="0900",
        day_iso="2026-08-18",
    )
    assert result.error is not None
    assert "docs +create" in result.error
    assert len(runner.calls) == 1
