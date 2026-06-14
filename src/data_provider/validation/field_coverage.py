"""V1 字段覆盖率分析工具。

功能：
- 计算 V1 所有原型的必需字段并集（union_required）
- 跨样本聚合：哪些字段至少被一只股票覆盖（covered）
- 哪些字段在所有样本中均无数据（blocked / gap）
- 生成 JSON 格式的覆盖率报告和缺口报告

设计原则：
- "covered" = 至少一只样本股 + 一个数据源能返回该字段的非 None 值
- "blocked" = covered 的补集（union_required - covered）
- 报告按原型维度拆分，便于产品决策
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_provider.validation.field_requirements import (
    PROTOTYPE_REQUIRED_FIELDS,
    get_required_fields,
)

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class StockFieldResult:
    """单只股票的字段覆盖结果。"""
    code: str
    name: str
    prototype: str
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    """跨样本聚合的覆盖率报告。"""
    generated_at: str = ""
    union_required: list[str] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    coverage_rate: float = 0.0
    per_prototype: dict[str, dict] = field(default_factory=dict)
    per_stock: list[dict] = field(default_factory=list)


# ── 核心逻辑 ──────────────────────────────────────────────────────────────────

def compute_union_required() -> frozenset[str]:
    """计算所有 V1 原型必需字段的并集。"""
    union: set[str] = set()
    for fields in PROTOTYPE_REQUIRED_FIELDS.values():
        union |= fields
    return frozenset(union)


def analyze_stock_coverage(
    code: str,
    name: str,
    prototype: str,
    data: dict[str, Any],
) -> StockFieldResult:
    """分析单只股票相对于其原型必需字段的覆盖情况。

    Args:
        data: FetchResult.data 或合并后的字段字典（field_name → 值）
    """
    required = get_required_fields(prototype)
    covered = [f for f in required if data.get(f) is not None]
    missing = [f for f in required if data.get(f) is None]
    return StockFieldResult(
        code=code, name=name, prototype=prototype,
        covered=sorted(covered), missing=sorted(missing),
    )


def aggregate_coverage(
    stock_results: list[StockFieldResult],
) -> CoverageReport:
    """跨样本聚合，生成总体覆盖率报告。

    - union_required：所有 V1 原型必需字段的并集
    - covered：至少一只股票覆盖的字段
    - blocked：所有样本中均为 None 的字段（需人工决策）
    """
    union_required = compute_union_required()
    globally_covered: set[str] = set()

    for sr in stock_results:
        globally_covered |= set(sr.covered)

    covered = sorted(globally_covered & union_required)
    blocked = sorted(union_required - globally_covered)

    total = len(union_required)
    rate = len(covered) / total if total > 0 else 0.0

    # 按原型汇总
    per_prototype: dict[str, dict] = {}
    for proto, proto_fields in PROTOTYPE_REQUIRED_FIELDS.items():
        proto_covered = sorted(globally_covered & proto_fields)
        proto_blocked = sorted(proto_fields - globally_covered)
        per_prototype[proto] = {
            "required": sorted(proto_fields),
            "covered": proto_covered,
            "blocked": proto_blocked,
            "coverage_rate": len(proto_covered) / len(proto_fields) if proto_fields else 0.0,
        }

    return CoverageReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        union_required=sorted(union_required),
        covered=covered,
        blocked=blocked,
        coverage_rate=rate,
        per_prototype=per_prototype,
        per_stock=[asdict(sr) for sr in stock_results],
    )


# ── 报告输出 ──────────────────────────────────────────────────────────────────

def save_coverage_report(report: CoverageReport, output_dir: Path) -> tuple[Path, Path]:
    """将覆盖率报告和缺口报告分别写入 JSON 文件。

    Returns:
        (coverage_path, gaps_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    coverage_path = output_dir / f"value-data-field-coverage-{ts}.json"
    gaps_path = output_dir / f"value-data-field-gaps-{ts}.json"

    # 完整覆盖率报告
    with coverage_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    logger.info("覆盖率报告写入: %s", coverage_path)

    # 精简缺口报告（仅 blocked 字段，便于产品决策）
    gaps = {
        "generated_at": report.generated_at,
        "summary": {
            "total_required": len(report.union_required),
            "covered": len(report.covered),
            "blocked": len(report.blocked),
            "coverage_rate": f"{report.coverage_rate:.1%}",
        },
        "blocked_fields": report.blocked,
        "blocked_by_prototype": {
            proto: info["blocked"]
            for proto, info in report.per_prototype.items()
            if info["blocked"]
        },
    }
    with gaps_path.open("w", encoding="utf-8") as f:
        json.dump(gaps, f, ensure_ascii=False, indent=2)
    logger.info("缺口报告写入: %s", gaps_path)

    return coverage_path, gaps_path


def print_coverage_summary(report: CoverageReport) -> None:
    """在控制台打印人类可读的覆盖率摘要。"""
    print("\n" + "=" * 60)
    print(f"  V1 字段覆盖率报告  ({report.generated_at[:10]})")
    print("=" * 60)
    print(f"  必需字段总数:  {len(report.union_required)}")
    print(f"  已覆盖字段:    {len(report.covered)}")
    print(f"  缺口字段:      {len(report.blocked)}")
    print(f"  整体覆盖率:    {report.coverage_rate:.1%}")

    print("\n  ── 分原型覆盖率 ──")
    for proto, info in report.per_prototype.items():
        rate = info["coverage_rate"]
        n_cov = len(info["covered"])
        n_req = len(info["required"])
        print(f"    {proto:<16} {n_cov:>2}/{n_req} ({rate:.0%})")

    if report.blocked:
        print(f"\n  -- 缺口字段（{len(report.blocked)} 个，需产品决策）--")
        for f in report.blocked:
            print(f"    [blocked] {f}")
    print()
