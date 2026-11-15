"""历史成分 / 退市 ST / 分组切点（design §4.1，R12/R15/R16）。

三条不变量：
- 退市股在退市日**之前**计入、之后不计（R12）；
- ST 按**当时**状态（`PriceBar.st` / 名单按时点），不回填今日标签；
- 分组按季度重算且**不回改历史**（纯函数，无状态可回写；`effective_range` 标注生效区间）。

分档口径（`cut_basis` / `tier_count` / `recompute_freq` / `min_group_size`）是 Q6
未答复项：缺键即 `MissingBacktestConfigError`，不默认全 A 截面。
"""

from __future__ import annotations

import calendar
from typing import Mapping, Protocol, Sequence, runtime_checkable

from common.exceptions import BacktestDataGapError, BacktestError, MissingBacktestConfigError
from service.backtest.models import BacktestConfig, GroupAssignment

# R15：软标签只登记不参与回测
SOFT_LABELS = frozenset(
    {
        "theme",
        "industry_chain",
        "management",
        "主题",
        "产业链",
        "管理层评价",
    }
)
# R15：结果标签（用未来信息分组）禁止
RESULT_LABELS = frozenset(
    {
        "future_return",
        "forward_return",
        "next_return",
        "post_return",
        "hot_money",
        "后面涨了",
        "被主力青睐",
        "未来收益",
    }
)
# 分组维度 → GroupAssignment.tiers 的键
DIMENSION_TO_TIER = {
    "market_cap": "market_cap_tier",
    "dividend_yield": "dividend_tier",
    "volatility": "volatility_tier",
}


@runtime_checkable
class UniverseProvider(Protocol):
    """universe 数据源协议（design §4.1，T2-fix-6）；不可得 → `BacktestDataGapError`。"""

    def historical_constituents(self, as_of: str, scope: str) -> tuple[str, ...]:
        """历史时点成分名单（scope 如 "csi300"/"all_a"）；可得但确实为空 → 空 tuple（合法）。"""

    def delisted_codes(self, as_of: str) -> tuple[str, ...]:
        """截至 as_of 的退市名单（供「退市日前计入」判定）。"""

    def st_status(self, code: str, as_of: str) -> bool:
        """as_of 时点的 ST 状态（按时点判定，不回填）。"""


def build_universe(
    as_of: str, universe_scope: str, *, provider: UniverseProvider
) -> tuple[str, ...]:
    """合并历史成分 + 退市（退市日前计入）+ 当时 ST（R12）。

    - 任一名单数据源不可得 → `BacktestDataGapError`（不静默剔除）；
    - 名单可得但确实为空 → 空 tuple（合法，不是缺口）。
    """
    missing = [
        method
        for method in ("historical_constituents", "delisted_codes", "st_status")
        if not hasattr(provider, method)
    ]
    if missing:
        raise BacktestDataGapError(
            f"universe provider 缺方法 {missing}：名单不可得，按缺口处理（R12/T2-fix-6）"
        )
    members = tuple(str(code) for code in provider.historical_constituents(as_of, universe_scope))
    delisted = {str(code) for code in provider.delisted_codes(as_of)}
    included = [code for code in members if code not in delisted]
    for code in included:
        # ST 状态按时点可查（R12 Scenario2）：不可得即缺口；ST 股仍计入（不是剔除）
        provider.st_status(code, as_of)
    return tuple(included)


def assign_groups(
    codes: Sequence[str],
    as_of: str,
    features: Mapping[str, Mapping[str, float]],
    *,
    cfg: BacktestConfig,
) -> dict[str, GroupAssignment]:
    """分位切点分组（季度重算，不回改历史；软/结果标签拒绝）。"""
    if cfg.cut_basis is None:
        raise MissingBacktestConfigError("回测配置缺值: cut_basis（Q6）")
    if cfg.tier_count is None:
        raise MissingBacktestConfigError("回测配置缺值: tier_count（Q6）")
    if cfg.min_group_size is None:
        raise MissingBacktestConfigError("回测配置缺值: min_group_size（Q6）")
    if cfg.recompute_freq is None:
        raise MissingBacktestConfigError("回测配置缺值: recompute_freq（Q6）")
    tier_count = int(cfg.tier_count)
    min_group_size = int(cfg.min_group_size)
    if tier_count < 1:
        raise MissingBacktestConfigError(f"tier_count 非法: {tier_count}")
    if min_group_size <= 0:
        raise MissingBacktestConfigError(f"min_group_size 非法: {min_group_size}")
    recompute_freq = str(cfg.recompute_freq).strip().lower()
    if recompute_freq not in ("quarter", "quarterly"):
        raise BacktestError(f"分组必须按季度重算（R15），配置为 {recompute_freq!r}")
    if tier_count < 1:
        raise MissingBacktestConfigError(f"tier_count 非法: {tier_count}")
    if not codes:
        raise BacktestDataGapError("assign_groups 无标的：不得默认全 A 截面")

    dimensions = _dimensions(codes, features)
    tiers_by_code: dict[str, dict[str, int]] = {code: {} for code in codes}
    for dimension in dimensions:
        tier_key = DIMENSION_TO_TIER[dimension]
        ordered = sorted(
            ((float(features[code][dimension]), code) for code in codes),
            key=lambda pair: (pair[0], pair[1]),
        )
        n = len(ordered)
        for index, (_value, code) in enumerate(ordered):
            tiers_by_code[code][tier_key] = min(tier_count - 1, index * tier_count // n)

    effective_range = quarter_range(as_of)
    result: dict[str, GroupAssignment] = {}
    for code in codes:
        result[code] = GroupAssignment(
            code=code,
            as_of=as_of,
            tiers=tiers_by_code[code],
            effective_range=effective_range,
        )
    return result


def _dimensions(codes: Sequence[str], features: Mapping[str, Mapping[str, float]]) -> list[str]:
    dimensions: set[str] = set()
    for code in codes:
        if code not in features:
            raise BacktestDataGapError(f"{code} 缺分组特征：不得用缺失值分组（R15）")
        row = features[code]
        if not row:
            raise BacktestDataGapError(f"{code} 分组特征为空（R15）")
        for dimension in row:
            normalized = str(dimension).strip().lower()
            if normalized in SOFT_LABELS:
                raise BacktestError(
                    f"软标签只登记不参与回测：{dimension}（R15 Scenario「软标签被拒绝进入分组」）"
                )
            if normalized in RESULT_LABELS:
                raise BacktestError(
                    f"结果标签禁止用于分组（依赖未来信息）：{dimension}（R15）"
                )
            if normalized not in DIMENSION_TO_TIER:
                raise BacktestError(
                    f"未知分组维度 {dimension!r}：只允许 {sorted(DIMENSION_TO_TIER)}（R15）"
                )
            dimensions.add(normalized)
    return sorted(dimensions)


def quarter_range(as_of: str) -> tuple[str, str]:
    """`as_of` 所属季度的生效区间（分组季度重算，R15）。"""
    year = int(str(as_of)[:4])
    month = int(str(as_of)[5:7])
    quarter = (month - 1) // 3
    start_month = quarter * 3 + 1
    end_month = start_month + 2
    last_day = calendar.monthrange(year, end_month)[1]
    return (f"{year:04d}-{start_month:02d}-01", f"{year:04d}-{end_month:02d}-{last_day:02d}")
