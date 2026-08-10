"""双轨分析配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DualTrackConfig:
    # 与 ValueAnalysisResult.margin_of_safety 相同单位：百分数点（20.0 = 20%）
    undervalued_mos_threshold: float = 20.0
    overvalued_mos_threshold: float = -10.0
    mos_thresholds_by_proto: dict[str, dict[str, float]] | None = None

    def to_mos_config(self) -> dict[str, Any]:
        if self.mos_thresholds_by_proto:
            return {"value": {"mos_thresholds_by_proto": self.mos_thresholds_by_proto}}
        return {}
