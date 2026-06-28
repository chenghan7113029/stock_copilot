"""双轨分析配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DualTrackConfig:
    undervalued_mos_threshold: float = 0.20
    overvalued_mos_threshold: float = -0.10
