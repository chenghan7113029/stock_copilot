"""LLM narrate 端到端集成（mock client，不联网）。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from common.config_loader import LLMConfig
from common.llm.models import ChatResult
from common.llm.narrator import narrate


class _MemoryCache:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def get(self, cache_key: str) -> dict[str, Any] | None:
        return self.store.get(cache_key)

    def set(self, cache_key: str, result: dict[str, Any]) -> None:
        self.store[cache_key] = result


def test_e2e_input_guard_llm_core_output_guard():
    schema = {
        "type": "object",
        "required": ["bull_report", "bear_report", "confidence"],
        "properties": {
            "bull_report": {"type": "string"},
            "bear_report": {"type": "string"},
            "confidence": {"type": "number"},
        },
    }
    evidence = {
        "pe_ratio": 5.5,
        "bull": ["低估，安全边际 20%"],
        "bear": ["RSI 超买"],
    }
    client = MagicMock()
    client.chat_json.return_value = ChatResult(
        ok=True,
        data={
            "bull_report": "安全边际 20%，PE 5.5 显示低估",
            "bear_report": "RSI 超买提示短期风险",
            "confidence": 0.85,
        },
        raw_text=(
            '{"bull_report":"安全边际 20%，PE 5.5 显示低估",'
            '"bear_report":"RSI 超买提示短期风险","confidence":0.85}'
        ),
    )
    cache = _MemoryCache()
    result = narrate(
        evidence,
        schema,
        "生成多空叙述",
        client=client,
        cache=cache,
        llm_config=LLMConfig(base_url="http://x", model="m", api_key="k"),
    )
    assert result.ok
    assert result.grounded is True
    assert result.data is not None
    assert "5.5" in result.data["bull_report"]
    # 第二次命中缓存
    result2 = narrate(
        evidence,
        schema,
        "生成多空叙述",
        client=client,
        cache=cache,
        llm_config=LLMConfig(base_url="http://x", model="m", api_key="k"),
    )
    assert result2.from_cache is True
    assert client.chat_json.call_count == 1
