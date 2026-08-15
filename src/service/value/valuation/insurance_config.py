"""保险 EV/NBV 输入：配置优先写入 StockData。"""

from __future__ import annotations

from typing import Any

from common.models.stock_data import StockData


def _section(config: dict[str, Any] | None) -> dict[str, Any]:
    return ((config or {}).get("value_analysis") or {}).get("insurance") or {}


def apply_insurance_inputs(
    stock: StockData, config: dict[str, Any] | None = None
) -> list[str]:
    """从 value_analysis.insurance.by_code 注入 EV/NBV 字段。"""
    notes: list[str] = []
    by_code = _section(config).get("by_code") or {}
    code_cfg = by_code.get(stock.code) if isinstance(by_code, dict) else None
    if not isinstance(code_cfg, dict):
        return notes

    field_map = (
        ("embedded_value", "内含价值 EV"),
        ("nbv", "一年新业务价值 NBV"),
        ("p_ev_fair", "公允 P/EV"),
    )
    for field_name, label in field_map:
        if getattr(stock, field_name, None) is not None:
            continue
        if code_cfg.get(field_name) is None:
            continue
        setattr(stock, field_name, float(code_cfg[field_name]))
        notes.append(f"{label}来自配置")

    return notes


def has_insurance_ev_inputs(stock: StockData) -> bool:
    ev = getattr(stock, "embedded_value", None)
    return ev is not None and float(ev) > 0
