"""数值锚定 grounded 校验。"""

from __future__ import annotations

import json
import re
from typing import Any

# 阿拉伯数字 + 可选小数/千分位，后接可选常见单位
_NUM_RE = re.compile(
    r"(?<![A-Za-z_])"
    r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    r"(?:\s*(亿|万|%|倍))?"
)

_UNIT_SCALE = {
    "": 1.0,
    "%": 1.0,  # 百分比按字面数值比对（5.5 与 5.5% 同源）
    "倍": 1.0,
    "万": 10_000.0,
    "亿": 100_000_000.0,
}


def extract_numeric_tokens(text: str) -> list[tuple[float, str]]:
    """从文本提取 (数值, 单位) 列表。单位为 '' / '%' / '倍' / '万' / '亿'。"""
    if not text:
        return []
    out: list[tuple[float, str]] = []
    for m in _NUM_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        unit = m.group(2) or ""
        out.append((value, unit))
    return out


def _canonical_values(tokens: list[tuple[float, str]]) -> set[float]:
    """将带单位数值归一到可比对的集合（含字面值与换算后绝对值）。"""
    values: set[float] = set()
    for value, unit in tokens:
        values.add(round(value, 6))
        scale = _UNIT_SCALE.get(unit, 1.0)
        if scale != 1.0:
            values.add(round(value * scale, 6))
        # 百分比：5.5% 与 0.055 互通
        if unit == "%":
            values.add(round(value / 100.0, 6))
        elif abs(value) <= 1.0 and unit == "":
            values.add(round(value * 100.0, 6))
    return values


def serialize_evidence(evidence: dict[str, Any]) -> str:
    return json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=str)


def check_grounded(output_text: str, evidence: dict[str, Any]) -> tuple[bool, list[float]]:
    """检查输出中的数值是否都能在 evidence 中锚定。

    返回 (ok, unmatched_values)。
    """
    evidence_text = serialize_evidence(evidence)
    evidence_values = _canonical_values(extract_numeric_tokens(evidence_text))
    # 输出侧：跳过 confidence 字段本身的常见范围噪声，先移除 confidence 键再提取
    output_for_check = output_text
    try:
        parsed = json.loads(output_text) if output_text.strip().startswith("{") else None
        if isinstance(parsed, dict):
            parsed = dict(parsed)
            parsed.pop("confidence", None)
            output_for_check = json.dumps(parsed, ensure_ascii=False, default=str)
    except (json.JSONDecodeError, TypeError):
        pass

    unmatched: list[float] = []
    for value, unit in extract_numeric_tokens(output_for_check):
        candidates = _canonical_values([(value, unit)])
        if not candidates.intersection(evidence_values):
            unmatched.append(value)
    return (len(unmatched) == 0, unmatched)
