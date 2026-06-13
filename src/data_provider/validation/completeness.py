"""数据完备性校验：按原型检查必需字段覆盖情况。

输出覆盖报告（CompletenessReport），下游根据报告决定哪些方法可靠。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from common.models.stock_data import StockData
from data_provider.validation.field_requirements import (
    BANK_TODO_FIELDS,
    get_required_fields,
)


@dataclass
class CompletenessReport:
    """单只股票的字段完备性报告。"""

    code: str
    prototype: str
    required_fields: FrozenSet[str]
    present_fields: FrozenSet[str]
    missing_required: FrozenSet[str]
    bank_todo_missing: FrozenSet[str]  # 银行专属 TODO 字段（警告级）
    coverage_ratio: float  # 必需字段覆盖率 [0, 1]
    passed: bool           # True 表示所有必需字段均已满足

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[{status}] {self.code} ({self.prototype})",
            f"  覆盖率: {self.coverage_ratio:.1%}"
            f" ({len(self.present_fields)}/{len(self.required_fields)} 必需字段满足)",
        ]
        if self.missing_required:
            lines.append(f"  缺失必需字段: {sorted(self.missing_required)}")
        if self.bank_todo_missing:
            lines.append(f"  银行专属 TODO 缺失（警告）: {sorted(self.bank_todo_missing)}")
        return "\n".join(lines)


def check_completeness(stock: StockData, prototype: str) -> CompletenessReport:
    """对 stock 按 prototype 做字段完备性校验，返回报告。"""
    required = get_required_fields(prototype)
    if not required:
        raise ValueError(f"未知原型: {prototype!r}，支持: bank / high_dividend / value_growth")

    # 实际已有的字段（不为 None 且不在 missing_fields 中）
    present = frozenset(
        f for f in required
        if getattr(stock, f, None) is not None
    )
    missing_required = required - present
    coverage = len(present) / len(required) if required else 1.0

    # 银行专属 TODO 字段缺失情况（只在银行原型时有意义）
    bank_todo_missing: FrozenSet[str] = frozenset()
    if prototype.lower() == "bank":
        bank_todo_missing = frozenset(
            f for f in BANK_TODO_FIELDS
            if getattr(stock, f, None) is None
        )

    return CompletenessReport(
        code=stock.code,
        prototype=prototype,
        required_fields=required,
        present_fields=present,
        missing_required=missing_required,
        bank_todo_missing=bank_todo_missing,
        coverage_ratio=coverage,
        passed=len(missing_required) == 0,
    )


def batch_check(
    stocks: list[tuple[StockData, str]],
) -> list[CompletenessReport]:
    """批量校验，返回每只股票的报告列表。

    参数: stocks = [(StockData, prototype_name), ...]
    """
    return [check_completeness(stock, proto) for stock, proto in stocks]
