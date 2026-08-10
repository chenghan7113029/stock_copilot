"""军工在手订单输入：配置优先写入 StockData。"""

from __future__ import annotations

from typing import Any

from common.models.stock_data import StockData


def _section(config: dict[str, Any] | None) -> dict[str, Any]:
    return ((config or {}).get("value_analysis") or {}).get("defense_orders") or {}


def apply_defense_order_inputs(
    stock: StockData, config: dict[str, Any] | None = None
) -> list[str]:
    """从 value_analysis.defense_orders.by_code 注入订单字段；返回说明 notes。"""
    notes: list[str] = []
    by_code = _section(config).get("by_code") or {}
    code_cfg = by_code.get(stock.code) if isinstance(by_code, dict) else None
    if not isinstance(code_cfg, dict):
        return notes

    field_map = (
        ("order_backlog", "在手订单"),
        ("order_execution_years", "订单消化年限"),
        ("order_margin", "订单利润率"),
        ("revaluation_assets", "资产重估增量"),
    )
    for field_name, label in field_map:
        if getattr(stock, field_name, None) is not None:
            continue
        if code_cfg.get(field_name) is None:
            continue
        setattr(stock, field_name, float(code_cfg[field_name]))
        notes.append(f"{label}来自配置")

    return notes


def has_defense_order_inputs(stock: StockData) -> bool:
    backlog = getattr(stock, "order_backlog", None)
    years = getattr(stock, "order_execution_years", None)
    return (
        backlog is not None
        and float(backlog) > 0
        and years is not None
        and float(years) > 0
    )
