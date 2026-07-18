"""narrate() Input Guard / Output Guard / confidence / cache / 未配置降级。"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

from common.config_loader import LLMConfig
from common.llm.grounding import check_grounded, extract_numeric_tokens
from common.llm.models import ChatResult
from common.llm.narrator import compute_cache_key, narrate


class _MemoryCache:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, cache_key: str) -> dict[str, Any] | None:
        self.get_calls += 1
        return self.store.get(cache_key)

    def set(self, cache_key: str, result: dict[str, Any]) -> None:
        self.set_calls += 1
        self.store[cache_key] = result


_SCHEMA = {
    "type": "object",
    "required": ["summary", "confidence"],
    "properties": {
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
    },
}


def _llm_cfg() -> LLMConfig:
    return LLMConfig(base_url="http://x", model="m", api_key="k", max_evidence_chars=200)


def test_narrate_rejects_empty_evidence():
    client = MagicMock()
    result = narrate({}, _SCHEMA, "写摘要", client=client, llm_config=_llm_cfg())
    assert not result.ok
    assert result.error == "evidence 为空"
    client.chat_json.assert_not_called()


def test_narrate_truncates_long_evidence():
    client = MagicMock()
    client.chat_json.return_value = ChatResult(
        ok=True,
        data={"summary": "pe 5.5", "confidence": 0.9},
        raw_text='{"summary": "pe 5.5", "confidence": 0.9}',
    )
    evidence = {"pe_ratio": 5.5, "note": "x" * 5000}
    result = narrate(
        evidence,
        _SCHEMA,
        "写摘要",
        client=client,
        llm_config=_llm_cfg(),
    )
    assert result.ok
    assert result.truncated is True
    user = client.chat_json.call_args.kwargs["user"]
    assert "truncated" in user.lower() or "…" in user or len(user) < len("x" * 5000) + 500


def test_schema_retry_then_success():
    client = MagicMock()
    client.chat_json.side_effect = [
        ChatResult(ok=True, data={"summary": "ok"}, raw_text='{"summary":"ok"}'),  # missing confidence
        ChatResult(
            ok=True,
            data={"summary": "ok pe 5.5", "confidence": 0.9},
            raw_text='{"summary":"ok pe 5.5","confidence":0.9}',
        ),
    ]
    result = narrate(
        {"pe_ratio": 5.5},
        _SCHEMA,
        "写摘要",
        client=client,
        llm_config=_llm_cfg(),
    )
    assert result.ok
    assert client.chat_json.call_count == 2


def test_schema_retry_exhausted():
    client = MagicMock()
    client.chat_json.return_value = ChatResult(
        ok=True,
        data={"summary": "ok"},  # missing confidence always
        raw_text='{"summary":"ok"}',
    )
    result = narrate(
        {"pe_ratio": 5.5},
        _SCHEMA,
        "写摘要",
        client=client,
        llm_config=_llm_cfg(),
    )
    assert not result.ok
    assert "schema" in (result.error or "").lower()
    assert client.chat_json.call_count == 3


def test_extract_numeric_tokens_units():
    tokens = extract_numeric_tokens("净利润 300.5 亿，股息率 5.5%，PB 0.68 倍")
    values = {v for v, _ in tokens}
    assert 300.5 in values
    assert 5.5 in values
    assert 0.68 in values


def test_grounded_pass_and_fail():
    evidence = {"pe_ratio": 5.5, "net_income": 300.0}
    ok, unmatched = check_grounded('{"summary":"PE 5.5","confidence":0.9}', evidence)
    assert ok
    assert unmatched == []
    ok2, unmatched2 = check_grounded('{"summary":"增长 40%","confidence":0.9}', evidence)
    assert not ok2
    assert 40.0 in unmatched2


def test_grounded_fail_triggers_retry():
    client = MagicMock()
    client.chat_json.side_effect = [
        ChatResult(
            ok=True,
            data={"summary": "增长 40%", "confidence": 0.9},
            raw_text='{"summary":"增长 40%","confidence":0.9}',
        ),
        ChatResult(
            ok=True,
            data={"summary": "PE 5.5", "confidence": 0.9},
            raw_text='{"summary":"PE 5.5","confidence":0.9}',
        ),
    ]
    result = narrate(
        {"pe_ratio": 5.5},
        _SCHEMA,
        "写摘要",
        client=client,
        llm_config=_llm_cfg(),
    )
    assert result.ok
    assert result.data["summary"] == "PE 5.5"
    assert client.chat_json.call_count == 2


def test_confidence_tiers():
    client = MagicMock()

    def run(conf: float):
        client.chat_json.return_value = ChatResult(
            ok=True,
            data={"summary": "pe 5.5", "confidence": conf},
            raw_text=f'{{"summary":"pe 5.5","confidence":{conf}}}',
        )
        return narrate(
            {"pe_ratio": 5.5},
            _SCHEMA,
            "写摘要",
            client=client,
            llm_config=_llm_cfg(),
        )

    low = run(0.5)
    assert not low.ok
    mid = run(0.7)
    assert mid.ok and mid.low_confidence_warning
    high = run(0.9)
    assert high.ok and not high.low_confidence_warning


def test_cache_hit_skips_second_llm_call():
    client = MagicMock()
    client.chat_json.return_value = ChatResult(
        ok=True,
        data={"summary": "pe 5.5", "confidence": 0.9},
        raw_text='{"summary":"pe 5.5","confidence":0.9}',
    )
    cache = _MemoryCache()
    evidence = {"pe_ratio": 5.5}
    r1 = narrate(evidence, _SCHEMA, "写摘要", client=client, cache=cache, llm_config=_llm_cfg())
    r2 = narrate(evidence, _SCHEMA, "写摘要", client=client, cache=cache, llm_config=_llm_cfg())
    assert r1.ok and r2.ok
    assert r2.from_cache is True
    assert client.chat_json.call_count == 1
    assert cache.set_calls == 1


def test_force_refresh_bypasses_cache():
    client = MagicMock()
    client.chat_json.return_value = ChatResult(
        ok=True,
        data={"summary": "pe 5.5", "confidence": 0.9},
        raw_text='{"summary":"pe 5.5","confidence":0.9}',
    )
    cache = _MemoryCache()
    evidence = {"pe_ratio": 5.5}
    narrate(evidence, _SCHEMA, "写摘要", client=client, cache=cache, llm_config=_llm_cfg())
    narrate(
        evidence,
        _SCHEMA,
        "写摘要",
        client=client,
        cache=cache,
        llm_config=_llm_cfg(),
        force_refresh=True,
    )
    assert client.chat_json.call_count == 2


def test_llm_not_configured():
    env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        result = narrate(
            {"pe_ratio": 5.5},
            _SCHEMA,
            "写摘要",
            config={"llm": {}},
        )
    assert not result.ok
    assert result.error == "LLM 未配置"


def test_compute_cache_key_stable():
    k1 = compute_cache_key("i", {"a": 1}, {"x": 2})
    k2 = compute_cache_key("i", {"a": 1}, {"x": 2})
    assert k1 == k2
    assert len(k1) == 64
