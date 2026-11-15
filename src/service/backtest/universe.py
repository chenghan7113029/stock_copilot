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
from typing import Any, Mapping, Sequence

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


def build_universe(
    as_of: str, universe_spec: Mapping[str, Any], *, provider: Any
) -> tuple[str, ...]:
    """含退市（退市日前计入）、当时 ST、历史成分（R12）；名单不可得→报缺口。"""
    if not hasattr(provider, "load_members"):
        raise BacktestDataGapError("universe provider 缺 load_members：名单不可得（R12）")
    members = tuple(provider.load_members(as_of, dict(universe_spec)))
    if not members:
        raise BacktestDataGapError(f"{as_of} 成分名单为空：按缺口处理，不静默降级")
    flags = _load_flags(provider, members, as_of)
    included: list[str] = []
    for code in members:
        flag = flags[code]
        if flag["delisted"]:
            delist_date = flag.get("delist_date")
            if not delist_date:
                raise BacktestDataGapError(f"{code} 已退市但无退市日：无法判定计入区间（R12）")
            if str(delist_date) <= as_of:
                continue  # 退市日之后不再计入
        included.append(code)
    return tuple(included)


def _load_flags(provider: Any, members: Sequence[str], as_of: str) -> dict[str, dict[str, Any]]:
    loader = getattr(provider, "load_flags", None)
    if loader is None:
        raise BacktestDataGapError("universe provider 缺 load_flags：退市/ST 状态不可得（R12）")
    flags = loader(members, as_of)
    missing = [code for code in members if code not in flags]
    if missing:
        raise BacktestDataGapError(f"退市/ST 标记缺失: {missing[:5]}（共 {len(missing)} 只）")
    return flags


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
