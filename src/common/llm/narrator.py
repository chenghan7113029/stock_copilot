"""narrate()：确定性证据 → 结构化叙事（三层防御）。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Protocol

import jsonschema

from common.config_loader import LLMConfig, resolve_llm_config
from common.llm.client import LLMClient
from common.llm.grounding import check_grounded, serialize_evidence
from common.llm.models import NarrateResult

logger = logging.getLogger(__name__)

_SCHEMA_RETRIES = 2  # 校验失败后最多再试 2 次
_SYSTEM_PROMPT = (
    "你是严谨的金融分析叙述助手。你只能基于用户提供的 evidence 组织叙述，"
    "不得编造 evidence 中不存在的数字或事实。"
    "必须输出符合给定 JSON Schema 的 JSON 对象，且包含 confidence 字段（0-1 浮点数）。"
)


class NarrateCache(Protocol):
    def get(self, cache_key: str) -> dict[str, Any] | None: ...

    def set(self, cache_key: str, result: dict[str, Any]) -> None: ...


def compute_cache_key(instruction: str, schema: dict[str, Any], evidence: dict[str, Any]) -> str:
    payload = {
        "instruction": instruction,
        "schema": schema,
        "evidence": evidence,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ensure_confidence_in_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """保证 schema 要求 confidence 字段（不修改调用方原对象）。"""
    merged = json.loads(json.dumps(schema))  # deep copy via JSON
    props = merged.setdefault("properties", {})
    if "confidence" not in props:
        props["confidence"] = {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "模型对本次叙述的置信度",
        }
    required = merged.setdefault("required", [])
    if "confidence" not in required:
        required.append("confidence")
    return merged


def _truncate_evidence(
    evidence: dict[str, Any],
    max_chars: int,
) -> tuple[dict[str, Any], bool]:
    """序列化超长时截断非关键字段（优先保留标量数值字段）。"""
    text = serialize_evidence(evidence)
    if len(text) <= max_chars:
        return evidence, False

    logger.info("evidence 超长（%s > %s），触发截断", len(text), max_chars)
    trimmed: dict[str, Any] = {}
    for key, value in evidence.items():
        if isinstance(value, (int, float, bool)) or value is None:
            trimmed[key] = value
        elif isinstance(value, str) and len(value) > 500:
            trimmed[key] = value[:500] + "…[truncated]"
        elif isinstance(value, list) and len(serialize_evidence({key: value})) > 2000:
            kept = value[:20]
            if len(value) > 20:
                kept = list(kept) + [f"…[+{len(value) - 20} truncated]"]
            trimmed[key] = kept
        else:
            trimmed[key] = value

    if len(serialize_evidence(trimmed)) <= max_chars:
        return trimmed, True

    # 仍超长：保留全部标量，其余字段压缩为短摘要
    scalars: dict[str, Any] = {}
    others: dict[str, Any] = {}
    for key, value in trimmed.items():
        if isinstance(value, (int, float, bool)) or value is None:
            scalars[key] = value
        else:
            others[key] = value
    budget = max(max_chars - len(serialize_evidence(scalars)) - 80, 64)
    raw_others = serialize_evidence(others)
    scalars["_truncated_other"] = raw_others[:budget] + "…[truncated]"
    return scalars, True


def _apply_confidence(result_data: dict[str, Any]) -> NarrateResult:
    confidence = result_data.get("confidence")
    try:
        conf = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        return NarrateResult(ok=False, error="confidence 字段无效", grounded=True)

    if conf < 0.6:
        return NarrateResult(
            ok=False,
            data=result_data,
            confidence=conf,
            grounded=True,
            error=f"置信度过低（{conf:.2f}）",
        )
    if conf < 0.8:
        return NarrateResult(
            ok=True,
            data=result_data,
            confidence=conf,
            low_confidence_warning=True,
            grounded=True,
        )
    return NarrateResult(
        ok=True,
        data=result_data,
        confidence=conf,
        grounded=True,
    )


def _result_to_cache_dict(result: NarrateResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "data": result.data,
        "confidence": result.confidence,
        "low_confidence_warning": result.low_confidence_warning,
        "error": result.error,
        "grounded": result.grounded,
        "warnings": result.warnings,
        "truncated": result.truncated,
    }


def _result_from_cache_dict(cached: dict[str, Any]) -> NarrateResult:
    return NarrateResult(
        ok=bool(cached.get("ok")),
        data=cached.get("data"),
        confidence=cached.get("confidence"),
        low_confidence_warning=bool(cached.get("low_confidence_warning")),
        error=cached.get("error"),
        grounded=cached.get("grounded"),
        from_cache=True,
        truncated=bool(cached.get("truncated")),
        warnings=list(cached.get("warnings") or []),
    )


def narrate(
    evidence: dict[str, Any],
    schema: dict[str, Any],
    instruction: str,
    *,
    force_refresh: bool = False,
    config: dict[str, Any] | None = None,
    client: LLMClient | None = None,
    cache: NarrateCache | None = None,
    llm_config: LLMConfig | None = None,
) -> NarrateResult:
    """将确定性 evidence 叙述为符合 schema 的结构化 JSON。"""
    if not evidence:
        return NarrateResult(ok=False, error="evidence 为空")

    cfg = llm_config if llm_config is not None else resolve_llm_config(config)
    if client is None and cfg is None:
        return NarrateResult(ok=False, error="LLM 未配置")

    max_chars = cfg.max_evidence_chars if cfg else 24_000
    evidence_for_llm, truncated = _truncate_evidence(evidence, max_chars)

    effective_schema = _ensure_confidence_in_schema(schema)
    cache_key = compute_cache_key(instruction, effective_schema, evidence_for_llm)

    if cache is not None and not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            result = _result_from_cache_dict(cached)
            result.truncated = truncated or result.truncated
            return result

    if client is None:
        assert cfg is not None
        client = LLMClient(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

    schema_text = json.dumps(effective_schema, ensure_ascii=False)
    evidence_text = serialize_evidence(evidence_for_llm)
    base_user = (
        f"Instruction:\n{instruction}\n\n"
        f"Evidence (JSON):\n{evidence_text}\n\n"
        f"Output JSON Schema:\n{schema_text}\n"
    )

    last_error: str | None = None
    correction: str | None = None

    for attempt in range(_SCHEMA_RETRIES + 1):
        user = base_user
        if correction:
            user += f"\n上次输出校验失败，请修正：\n{correction}\n"

        chat = client.chat_json(system=_SYSTEM_PROMPT, user=user)
        if not chat.ok or chat.data is None:
            last_error = chat.error or "LLM 调用失败"
            # API 级失败也允许重试（client 内部已重试过；此处主要给 schema/grounded 纠错用）
            if attempt >= _SCHEMA_RETRIES:
                return NarrateResult(ok=False, error=last_error, truncated=truncated)
            correction = last_error
            continue

        try:
            jsonschema.validate(chat.data, effective_schema)
        except jsonschema.ValidationError as exc:
            last_error = f"schema 校验失败: {exc.message}"
            if attempt >= _SCHEMA_RETRIES:
                return NarrateResult(ok=False, error=last_error, truncated=truncated)
            correction = last_error
            continue

        output_text = chat.raw_text or serialize_evidence(chat.data)
        grounded_ok, unmatched = check_grounded(output_text, evidence_for_llm)
        if not grounded_ok:
            last_error = f"grounded 校验失败: 输出含 evidence 之外的数值 {unmatched}"
            if attempt >= _SCHEMA_RETRIES:
                return NarrateResult(
                    ok=False,
                    error=last_error,
                    grounded=False,
                    data=chat.data,
                    truncated=truncated,
                )
            correction = last_error
            continue

        result = _apply_confidence(chat.data)
        result.truncated = truncated
        if truncated:
            result.warnings.append("evidence 已截断")

        if cache is not None and result.ok:
            cache.set(cache_key, _result_to_cache_dict(result))
        return result

    return NarrateResult(ok=False, error=last_error or "narrate 失败", truncated=truncated)
