"""价值面分析输出契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from service.value.valuation.base import ValuationRange, ValuationResult


@dataclass
class ValueAnalysisResult:
    code: str
    name: str
    current_price: float | None
    prototype: str
    method_keys_used: list[str]
    fair_value_range: ValuationRange | None
    margin_of_safety: float | None
    price_percentile: float | None
    assessment: str
    confidence: str
    method_results: dict[str, ValuationResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    data_timestamp: datetime | None = None
    fundamental_report_date: date | None = None
    value_score: int | None = None
    value_trap_alert: str | None = None
    methodology_applicable: bool = True
