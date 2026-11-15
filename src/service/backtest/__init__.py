"""回测业务子域（design §4.0/§6.1）。

依赖方向：`apps/cli → service/backtest → data_provider/backtest + dao → common`。
本子域是**确定性计算**：回测全链路零 LLM 调用点（design §3A）。
"""

from __future__ import annotations

__all__ = [
    "broker",
    "calibration",
    "config",
    "data",
    "gates",
    "metrics",
    "models",
    "registry",
    "signal",
    "universe",
]
