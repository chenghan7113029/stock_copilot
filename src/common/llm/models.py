"""LLM 叙事核心数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NarrateResult:
    """narrate() 返回值。"""

    ok: bool
    data: dict[str, Any] | None = None
    confidence: float | None = None
    low_confidence_warning: bool = False
    error: str | None = None
    grounded: bool | None = None
    from_cache: bool = False
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ChatResult:
    """LLMClient.chat_json 返回值。"""

    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    raw_text: str | None = None
    used_json_mode: bool = False
    retries: int = 0
