"""配置执行器输入加载：只读 tracked 政策与 ignored 私人快照。

- 政策唯一真源 = `config/ips.yaml`（R1），本模块不写回、不缓存、不合并。
- 快照 = `config/ips.local.yaml`；派生字段 `deployment.gap_to_target` /
  `deployment.monthly_amount` 不读取（结构隔离：`Snapshot` 上没有这两个字段）。
- 缺键/类型错/YAML 解析失败一律 `AllocationConfigError`（CLI 退出码 1）：
  缺字段不得按 0 或默认值继续。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from service.allocation.models import (
    AllocationConfigError,
    IpsPolicy,
    PlanInput,
    Snapshot,
)

# 本文件位于 src/service/allocation/，上溯三层为仓库根
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _REPO_ROOT / "config"
_IPS_YAML = _CONFIG_DIR / "ips.yaml"
_IPS_LOCAL_YAML = _CONFIG_DIR / "ips.local.yaml"

_IPS_LABEL = "政策文件 config/ips.yaml"
_SNAPSHOT_LABEL = "快照文件 config/ips.local.yaml"

# `deployment.execution_day` 目前只支持「每月最后一个周四」（design R2）
SUPPORTED_EXECUTION_DAY = "last_thursday"


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    """`yaml.safe_load` 读一个映射文件；任何读取/解析失败都转成配置错误。"""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AllocationConfigError(f"找不到{label}：{path}") from exc
    except OSError as exc:
        raise AllocationConfigError(f"读取{label}失败：{path}（{exc}）") from exc
    except yaml.YAMLError as exc:
        raise AllocationConfigError(f"{label} YAML 解析失败：{exc}") from exc
    if not isinstance(raw, dict):
        raise AllocationConfigError(f"{label} 顶层必须是映射：{path}")
    return raw


def _require(raw: dict[str, Any], dotted: str, label: str) -> Any:
    """按点号路径取必填字段；缺失即拒绝（不猜默认值）。"""
    node: Any = raw
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise AllocationConfigError(f"{label} 缺少字段 {dotted}")
        node = node[key]
    return node


def _as_decimal(value: Any, dotted: str, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise AllocationConfigError(f"{label} 字段 {dotted} 类型错误：{value!r}（应为数值）")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise AllocationConfigError(f"{label} 字段 {dotted} 不是合法数值：{value!r}") from exc


def _as_int(value: Any, dotted: str, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AllocationConfigError(f"{label} 字段 {dotted} 类型错误：{value!r}（应为整数）")
    return value


def _as_date(value: Any, dotted: str, label: str) -> date:
    if isinstance(value, datetime):
        raise AllocationConfigError(f"{label} 字段 {dotted} 必须是日期（YYYY-MM-DD），不是时间：{value!r}")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise AllocationConfigError(
                f"{label} 字段 {dotted} 不是合法日期（YYYY-MM-DD）：{value!r}"
            ) from exc
    raise AllocationConfigError(f"{label} 字段 {dotted} 不是日期：{value!r}")


def load_ips_policy() -> IpsPolicy:
    """读取 `config/ips.yaml` 的执行器政策字段（目标比例/期限/执行日/阈值）。"""
    raw = _load_yaml(_IPS_YAML, _IPS_LABEL)

    def decimal_of(dotted: str) -> Decimal:
        return _as_decimal(_require(raw, dotted, _IPS_LABEL), dotted, _IPS_LABEL)

    execution_day = str(_require(raw, "deployment.execution_day", _IPS_LABEL))
    if execution_day != SUPPORTED_EXECUTION_DAY:
        raise AllocationConfigError(
            f"{_IPS_LABEL} 字段 deployment.execution_day 不支持：{execution_day!r}"
            f"（当前只实现 {SUPPORTED_EXECUTION_DAY}）"
        )

    return IpsPolicy(
        target_equity=decimal_of("allocation.target.equity"),
        target_fixed_income=decimal_of("allocation.target.fixed_income"),
        target_cash=decimal_of("allocation.target.cash"),
        start_month=_as_int(_require(raw, "deployment.start_month", _IPS_LABEL), "deployment.start_month", _IPS_LABEL),
        horizon_months=_as_int(
            _require(raw, "deployment.horizon_months", _IPS_LABEL), "deployment.horizon_months", _IPS_LABEL
        ),
        target_date=_as_date(_require(raw, "deployment.target_date", _IPS_LABEL), "deployment.target_date", _IPS_LABEL),
        execution_day=execution_day,
        skip_if_equity_above=decimal_of("deployment.skip_if_equity_above"),
        trial_ratio=decimal_of("fixed_income_detail.migration.trial_ratio"),
        equity_cap=decimal_of("rules.R1_equity_cap"),
        rebalance_band=decimal_of("rules.R4_rebalance_band"),
        cash_floor=decimal_of("rules.R7_cash_floor"),
        stale_days=_as_int(_require(raw, "rules.R8_stale_days", _IPS_LABEL), "rules.R8_stale_days", _IPS_LABEL),
    )


def load_snapshot() -> Snapshot:
    """读取 `config/ips.local.yaml` 的快照字段；显式不返回派生金额字段。"""
    raw = _load_yaml(_IPS_LOCAL_YAML, _SNAPSHOT_LABEL)

    def decimal_of(dotted: str) -> Decimal:
        return _as_decimal(_require(raw, dotted, _SNAPSHOT_LABEL), dotted, _SNAPSHOT_LABEL)

    return Snapshot(
        pool_total=decimal_of("pool.total"),
        current_equity=decimal_of("allocation.current.equity"),
        current_fixed_income=decimal_of("allocation.current.fixed_income"),
        current_cash=decimal_of("allocation.current.cash"),
        holdings_market_value=decimal_of("holdings.total_market_value"),
        holdings_as_of=_as_date(_require(raw, "holdings.as_of", _SNAPSHOT_LABEL), "holdings.as_of", _SNAPSHOT_LABEL),
    )


def load_plan_input() -> PlanInput:
    """执行器入参 = 政策 + 快照（派生金额字段结构上不可达）。"""
    return PlanInput(policy=load_ips_policy(), snapshot=load_snapshot())
