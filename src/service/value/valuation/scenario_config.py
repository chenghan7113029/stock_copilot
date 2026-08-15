"""制造成长股浅情景 DCF 假设（悲观/基准/乐观）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 百分数点（与 DCF / AssumptionProvider 一致，如 12.0 = 12%）
_DEFAULT_SCENARIOS: dict[str, dict[str, float]] = {
    "bear": {
        "growth_rate_1_5": 6.0,
        "growth_rate_6_10": 3.0,
        "terminal_growth": 1.5,
    },
    "base": {
        "growth_rate_1_5": 12.0,
        "growth_rate_6_10": 5.0,
        "terminal_growth": 2.0,
    },
    "bull": {
        "growth_rate_1_5": 18.0,
        "growth_rate_6_10": 7.0,
        "terminal_growth": 2.5,
    },
}

_SCENARIO_ORDER = ("bear", "base", "bull")
_SCENARIO_LABELS_ZH = {
    "bear": "悲观",
    "base": "基准",
    "bull": "乐观",
}


@dataclass(frozen=True)
class ScenarioParams:
    growth_rate_1_5: float
    growth_rate_6_10: float
    terminal_growth: float
    discount_rate: float | None = None


def scenario_label_zh(key: str) -> str:
    return _SCENARIO_LABELS_ZH.get(key, key)


def _merge_scenario(base: dict[str, float], override: dict[str, Any] | None) -> ScenarioParams:
    payload = dict(base)
    if isinstance(override, dict):
        for key in ("growth_rate_1_5", "growth_rate_6_10", "terminal_growth", "discount_rate"):
            if key in override and override[key] is not None:
                payload[key] = float(override[key])
    return ScenarioParams(
        growth_rate_1_5=float(payload["growth_rate_1_5"]),
        growth_rate_6_10=float(payload["growth_rate_6_10"]),
        terminal_growth=float(payload["terminal_growth"]),
        discount_rate=(
            float(payload["discount_rate"]) if payload.get("discount_rate") is not None else None
        ),
    )


def resolve_scenario_params(
    code: str | None,
    config: dict[str, Any] | None = None,
) -> dict[str, ScenarioParams]:
    """返回三档情景参数；缺省用内置默认，可被 value_analysis.scenario_dcf 覆盖。"""
    section = ((config or {}).get("value_analysis") or {}).get("scenario_dcf") or {}
    defaults_cfg = section.get("defaults") or {}
    by_code = section.get("by_code") or {}
    code_cfg = by_code.get(code or "") if isinstance(by_code, dict) else None
    if not isinstance(code_cfg, dict):
        code_cfg = {}

    resolved: dict[str, ScenarioParams] = {}
    for key in _SCENARIO_ORDER:
        base = dict(_DEFAULT_SCENARIOS[key])
        default_override = defaults_cfg.get(key) if isinstance(defaults_cfg, dict) else None
        code_override = code_cfg.get(key)
        # code 覆盖优先于 defaults 覆盖
        merged_override: dict[str, Any] = {}
        if isinstance(default_override, dict):
            merged_override.update(default_override)
        if isinstance(code_override, dict):
            merged_override.update(code_override)
        resolved[key] = _merge_scenario(base, merged_override or None)
    return resolved
