"""估值方法论基类与结果模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValuationRange:
    """敏感性分析区间（低/基准/高）。"""

    low: float = 0.0
    base: float = 0.0
    high: float = 0.0

    @property
    def range_pct(self) -> float:
        if self.base == 0:
            return 0.0
        return ((self.high - self.low) / self.base) * 100


@dataclass
class ValuationResult:
    method: str
    fair_value: float
    current_price: float
    premium_discount: float
    assessment: str
    details: dict[str, Any] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)
    analysis: list[str] = field(default_factory=list)
    confidence: str = "Medium"
    fair_value_range: ValuationRange | None = None
    missing_fields: list[str] = field(default_factory=list)
    applicability: str = "Applicable"
    error: str | None = None

    @property
    def margin_of_safety(self) -> float:
        if self.fair_value > 0:
            return ((self.fair_value - self.current_price) / self.fair_value) * 100
        return 0.0

    @property
    def is_reliable(self) -> bool:
        return len(self.missing_fields) == 0 and self.fair_value > 0 and self.error is None


@dataclass
class FieldRequirement:
    name: str
    description: str
    is_critical: bool = True
    min_value: float | None = None
    max_value: float | None = None


class DataValidator:
    """校验估值输入；None 表示缺失，0.0 为真实零值。"""

    @staticmethod
    def check_required_fields(
        stock,
        requirements: list[FieldRequirement],
    ) -> tuple[bool, list[str], list[str]]:
        missing: list[str] = []
        warnings: list[str] = []

        for req in requirements:
            value = getattr(stock, req.name, None)

            if value is None:
                if req.is_critical:
                    missing.append(req.name)
                else:
                    warnings.append(f"{req.name} ({req.description})")
                continue

            if req.min_value is not None and value < req.min_value:
                warnings.append(f"{req.name}={value} < min {req.min_value}")
            elif req.max_value is not None and value > req.max_value:
                warnings.append(f"{req.name}={value} > max {req.max_value}")

        return len(missing) == 0, missing, warnings


class BaseValuation(ABC):
    method_name: str = "Base"
    required_fields: list[FieldRequirement] = []
    best_for: list[str] = []
    not_for: list[str] = []

    @abstractmethod
    def calculate(self, stock) -> ValuationResult:
        pass

    def validate_data(self, stock) -> tuple[bool, list[str], list[str]]:
        if not self.required_fields:
            return True, [], []
        return DataValidator.check_required_fields(stock, self.required_fields)

    def _assess(
        self,
        fair_value: float,
        current_price: float,
        threshold_high: float = 0.15,
        threshold_low: float = -0.15,
    ) -> str:
        if fair_value <= 0 or current_price <= 0:
            return "N/A"
        premium = ((fair_value - current_price) / current_price) * 100
        if premium > threshold_high * 100:
            return "Undervalued"
        if premium < threshold_low * 100:
            return "Overvalued"
        return "Fair"

    def _create_error_result(
        self,
        stock,
        reason: str,
        missing_fields: list[str] | None = None,
    ) -> ValuationResult:
        price = getattr(stock, "current_price", None) or 0
        return ValuationResult(
            method=self.method_name,
            fair_value=0,
            current_price=price,
            premium_discount=0,
            assessment=f"N/A - {reason}",
            missing_fields=missing_fields or [],
            confidence="N/A",
            applicability="Not Applicable",
            error=reason,
            analysis=[f"Cannot calculate: {reason}"],
        )
