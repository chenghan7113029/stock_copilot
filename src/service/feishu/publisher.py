"""通过本机 lark-cli 新建云文档并发送消息。"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from common.config_loader import FeishuConfig
from common.exceptions import StockCopilotError


class FeishuPublisherError(StockCopilotError):
    """lark-cli 调用失败。"""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]


class CommandRunner(Protocol):
    def __call__(self, argv: list[str]) -> CommandResult: ...


@dataclass(frozen=True)
class PublishResult:
    code: str
    doc_url: str
    title: str
    dry_run: bool
    error: str | None = None


def push_title(name: str, *, day_iso: str, slot: str) -> str:
    label = (name or "").strip()
    return f"今日研报_{label}_{day_iso}_{slot}"


def subprocess_runner(argv: list[str], timeout: float = 120.0) -> CommandResult:
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        argv=tuple(argv),
    )


def _parse_json_blob(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(raw[start : end + 1])
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def extract_doc_url(payload: dict) -> str:
    def walk(obj: object) -> str:
        if isinstance(obj, dict):
            for key in ("doc_url", "url", "document_url"):
                value = obj.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return value
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found:
                    return found
        return ""

    return walk(payload)


class LarkCliPublisher:
    def __init__(
        self,
        config: FeishuConfig,
        runner: CommandRunner | None = None,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        self.config = config
        self.runner = runner or subprocess_runner
        self.which = which or shutil.which

    def missing_cli_message(self) -> str:
        return (
            f"未找到 lark-cli（当前配置: {self.config.lark_cli}）。"
            "请安装 https://github.com/larksuite/cli 并执行 lark-cli auth login"
        )

    def resolve_binary(self) -> str:
        configured = self.config.lark_cli or "lark-cli"
        path = Path(configured)
        if path.is_file():
            return str(path)
        found = self.which(configured)
        if found:
            return found
        raise FeishuPublisherError(self.missing_cli_message())

    def publish(
        self,
        *,
        code: str,
        name: str,
        md_path: Path,
        slot: str,
        day_iso: str,
        dry_run: bool = False,
    ) -> PublishResult:
        title = push_title(name or code, day_iso=day_iso, slot=slot)
        if dry_run:
            return PublishResult(code=code, doc_url="", title=title, dry_run=True)
        if not md_path.exists():
            raise FeishuPublisherError(f"本地 dual.md 不存在：{md_path}")
        binary = self.resolve_binary()
        markdown = md_path.read_text(encoding="utf-8")
        create_argv = [
            binary,
            "docs",
            "+create",
            "--format",
            "json",
            "--doc-format",
            "markdown",
            "--as",
            "user",
            "--title",
            title,
            "--content",
            markdown,
        ]
        if self.config.folder_token:
            create_argv.extend(["--parent-token", self.config.folder_token])
        created = self.runner(create_argv)
        payload = _parse_json_blob(created.stdout)
        if created.returncode != 0 or payload.get("ok") is False:
            detail = payload.get("error") or created.stderr or created.stdout or "create failed"
            return PublishResult(
                code=code,
                doc_url="",
                title=title,
                dry_run=False,
                error=f"lark-cli docs +create 失败：{detail}",
            )
        url = extract_doc_url(payload)
        if not url:
            return PublishResult(
                code=code,
                doc_url="",
                title=title,
                dry_run=False,
                error="lark-cli 未返回文档 URL",
            )
        user_id = self.config.user_id
        chat_id = self.config.chat_id
        if not user_id and not chat_id:
            return PublishResult(
                code=code,
                doc_url=url,
                title=title,
                dry_run=False,
                error="未配置 feishu.user_id 或 feishu.chat_id，文档已创建但无法发消息",
            )
        text = f"{title}\n{url}"
        send_argv = [
            binary,
            "im",
            "+messages-send",
            "--format",
            "json",
            "--as",
            "user",
        ]
        # user_id（自聊）优先；与 chat_id 互斥
        if user_id:
            send_argv.extend(["--user-id", user_id])
        else:
            send_argv.extend(["--chat-id", chat_id])
        send_argv.extend(["--text", text])
        sent = self.runner(send_argv)
        send_payload = _parse_json_blob(sent.stdout)
        if sent.returncode != 0 or send_payload.get("ok") is False:
            detail = send_payload.get("error") or sent.stderr or sent.stdout or "send failed"
            return PublishResult(
                code=code,
                doc_url=url,
                title=title,
                dry_run=False,
                error=f"文档已创建但发消息失败：{detail}",
            )
        return PublishResult(code=code, doc_url=url, title=title, dry_run=False)
