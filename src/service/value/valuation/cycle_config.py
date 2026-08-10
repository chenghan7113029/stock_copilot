"""周期位置与均值化输入解析（配置优先，其次简单启发式）。"""

from __future__ import annotations

from typing import Any

from common.models.stock_data import StockData

_VALID_POSITIONS = frozenset(
    {"bottom", "early_up", "mid", "late", "top", "early_down"}
)

_POSITION_LABELS_ZH = {
    "bottom": "周期底部",
    "early_up": "复苏早期",
    "mid": "周期中段",
    "late": "景气末段",
    "top": "周期顶部",
    "early_down": "下行早期",
}


def cycle_position_label_zh(position: str | None) -> str:
    if not position:
        return "未知"
    return _POSITION_LABELS_ZH.get(position, position)


def _cycle_section(config: dict[str, Any] | None) -> dict[str, Any]:
    return ((config or {}).get("value_analysis") or {}).get("cyclical") or {}


def apply_cycle_inputs(stock: StockData, config: dict[str, Any] | None = None) -> list[str]:
    """把配置/启发式写入 stock 周期字段；返回说明性 notes（非错误）。"""
    notes: list[str] = []
    section = _cycle_section(config)
    by_code = section.get("by_code") or {}
    code_cfg = by_code.get(stock.code) if isinstance(by_code, dict) else None
    if not isinstance(code_cfg, dict):
        code_cfg = {}

    if stock.cycle_position is None and code_cfg.get("cycle_position"):
        pos = str(code_cfg["cycle_position"]).strip()
        if pos in _VALID_POSITIONS:
            stock.cycle_position = pos
            notes.append(f"周期位置来自配置: {cycle_position_label_zh(pos)}")

    if stock.normalized_eps is None and code_cfg.get("normalized_eps") is not None:
        stock.normalized_eps = float(code_cfg["normalized_eps"])
        notes.append("均值化 EPS 来自配置")

    if stock.normalized_fcf is None and code_cfg.get("normalized_fcf") is not None:
        stock.normalized_fcf = float(code_cfg["normalized_fcf"])
        notes.append("均值化 FCF 来自配置")

    if stock.historical_roe is None and isinstance(code_cfg.get("historical_roe"), list):
        stock.historical_roe = [float(x) for x in code_cfg["historical_roe"]]

    if stock.historical_fcf is None and isinstance(code_cfg.get("historical_fcf"), list):
        stock.historical_fcf = [float(x) for x in code_cfg["historical_fcf"]]

    if stock.cycle_position is None:
        inferred = infer_cycle_position_from_pe(stock)
        if inferred is not None:
            stock.cycle_position = inferred
            notes.append(
                f"周期位置由历史 PE 分位启发式推断: {cycle_position_label_zh(inferred)}"
            )

    return notes


def infer_cycle_position_from_pe(stock: StockData) -> str | None:
    """用当前 PE 相对历史 PE 分位粗判周期位置；数据不足返回 None。"""
    series = stock.historical_pe
    pe = stock.pe_ratio
    if not series or len(series) < 5 or pe is None or pe <= 0:
        return None
    sorted_pe = sorted(float(x) for x in series if x is not None and float(x) > 0)
    if len(sorted_pe) < 5:
        return None
    # 分位：当前 PE 在历史中的位置（高 PE → 更像底部）
    rank = sum(1 for x in sorted_pe if x <= pe) / len(sorted_pe)
    if rank <= 0.2:
        return "late"  # 景气末段常见低 PE 陷阱
    if rank <= 0.4:
        return "mid"
    if rank <= 0.6:
        return "early_up"
    if rank <= 0.8:
        return "early_down"
    return "bottom"
