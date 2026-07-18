"""LLMClient 单元测试（mock openai）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from common.llm.client import LLMClient


def _make_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("openai.OpenAI")
def test_chat_json_success_with_json_mode(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_response('{"a": 1}')

    client = LLMClient(api_key="k", model="m", base_url="http://x")
    result = client.chat_json(system="s", user="u")

    assert result.ok
    assert result.data == {"a": 1}
    assert result.used_json_mode is True
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}


@patch("openai.OpenAI")
def test_chat_json_fallback_when_json_mode_unsupported(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    def side_effect(**kwargs):
        if "response_format" in kwargs:
            raise ValueError("response_format is not supported")
        return _make_response('```json\n{"ok": true}\n```')

    mock_client.chat.completions.create.side_effect = side_effect
    client = LLMClient(api_key="k", model="m", base_url="http://x")
    result = client.chat_json(system="s", user="u")

    assert result.ok
    assert result.data == {"ok": True}
    assert result.used_json_mode is False


@patch("openai.OpenAI")
def test_chat_json_retries_on_rate_limit_then_succeeds(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = [
        Exception("429 rate limit"),
        _make_response('{"v": 2}'),
    ]
    sleeps: list[float] = []
    client = LLMClient(api_key="k", model="m", base_url="http://x", sleep_fn=sleeps.append)
    result = client.chat_json(system="s", user="u")

    assert result.ok
    assert result.data == {"v": 2}
    assert result.retries == 1
    assert sleeps == [1]


@patch("openai.OpenAI")
def test_chat_json_retries_exhausted(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("timeout")
    sleeps: list[float] = []
    client = LLMClient(api_key="k", model="m", base_url="http://x", sleep_fn=sleeps.append)
    result = client.chat_json(system="s", user="u")

    assert not result.ok
    assert "timeout" in (result.error or "")
    assert result.retries == 2
    assert len(sleeps) == 2
