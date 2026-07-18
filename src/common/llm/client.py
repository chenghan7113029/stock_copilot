"""OpenAI 兼容 LLM Client。"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from common.llm.models import ChatResult

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2  # 初次失败后再试 2 次，共最多 3 次调用
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


def _parse_json_content(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(text)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError(f"期望 JSON object，得到 {type(data).__name__}")
    return data


def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if any(k in name for k in ("timeout", "ratelimit", "apierror", "apiconnection", "internalserver")):
        return True
    if any(k in msg for k in ("429", "rate limit", "timeout", "503", "502", "500", "overloaded")):
        return True
    return False


def _json_mode_unsupported(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(
        k in msg
        for k in (
            "response_format",
            "json_object",
            "not support",
            "unsupported",
            "unknown parameter",
            "invalid parameter",
        )
    )


class LLMClient:
    """基于 OpenAI 兼容 chat.completions 的 JSON 调用封装。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        sleep_fn=time.sleep,
    ) -> None:
        from openai import OpenAI

        self._model = model
        self._sleep = sleep_fn
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        prefer_json_mode: bool = True,
    ) -> ChatResult:
        """调用 chat.completions，解析为 JSON object。

        优先 response_format=json_object；不支持时 fallback 到纯 prompt + fence 剥离。
        超时/429/5xx 指数退避重试（最多 2 次额外尝试）。
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        use_json_mode = prefer_json_mode
        last_error: str | None = None
        retries = 0

        for attempt in range(_MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = self._client.chat.completions.create(**kwargs)
                content = (resp.choices[0].message.content or "").strip()
                data = _parse_json_content(content)
                return ChatResult(
                    ok=True,
                    data=data,
                    raw_text=content,
                    used_json_mode=use_json_mode,
                    retries=retries,
                )
            except Exception as exc:
                last_error = str(exc)
                if use_json_mode and _json_mode_unsupported(exc):
                    logger.info("provider 不支持 JSON mode，fallback 到 prompt 解析: %s", exc)
                    use_json_mode = False
                    # 不计入重试次数，立即用 fallback 再试本轮
                    try:
                        kwargs = {
                            "model": self._model,
                            "messages": messages,
                        }
                        resp = self._client.chat.completions.create(**kwargs)
                        content = (resp.choices[0].message.content or "").strip()
                        data = _parse_json_content(content)
                        return ChatResult(
                            ok=True,
                            data=data,
                            raw_text=content,
                            used_json_mode=False,
                            retries=retries,
                        )
                    except Exception as exc2:
                        last_error = str(exc2)
                        if not _is_retryable(exc2) or attempt >= _MAX_RETRIES:
                            return ChatResult(ok=False, error=last_error, retries=retries)
                        retries += 1
                        self._sleep(2 ** attempt)
                        continue

                if not _is_retryable(exc) or attempt >= _MAX_RETRIES:
                    return ChatResult(ok=False, error=last_error, retries=retries)
                retries += 1
                wait = 2 ** attempt
                logger.warning("LLM 调用失败，%ss 后重试 (%s/%s): %s", wait, retries, _MAX_RETRIES, exc)
                self._sleep(wait)

        return ChatResult(ok=False, error=last_error or "LLM 调用失败", retries=retries)
