"""CLI 进度输出：长耗时命令向 stdout 打印阶段性状态（flush 避免无输出假死）。"""

from __future__ import annotations

import sys
import time
from typing import Callable

ProgressCallback = Callable[[str], None]


class CliProgress:
    """带耗时前缀的 CLI 进度行，默认写入 stdout（非 stderr，避免 PowerShell 误判）。"""

    def __init__(self, prefix: str, *, enabled: bool = True) -> None:
        self._prefix = prefix
        self._enabled = enabled
        self._start = time.monotonic()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def callback(self) -> ProgressCallback | None:
        return self.emit if self._enabled else None

    def emit(self, message: str) -> None:
        if not self._enabled:
            return
        elapsed = time.monotonic() - self._start
        print(f"[{self._prefix}] ({elapsed:5.1f}s) {message}", file=sys.stdout, flush=True)


def cli_progress_enabled(config: dict) -> bool:
    """是否启用 CLI 进度输出（config logging.cli_progress，默认 True）。"""
    return bool(config.get("logging", {}).get("cli_progress", True))
