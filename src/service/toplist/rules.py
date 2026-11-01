"""龙虎榜确定性规则：上榜频次、主导事件净买额、机构席位、理由分类与覆盖告警。

口径要点（实测数据决定，勿随意改成求和）：
- 同一股票同一交易日可能因多条上榜理由出现多行，各行金额是该理由下前五席位的
  聚合，**跨 reason 求和会重复计算**，故只取主导事件（l_amount 最大者）。
- `top_inst` 中「机构专用」可占多个前五席位，且同一席位可能同时出现在买入前 5
  与卖出前 5（金额相同），故按 (exalter, buy, sell, reason) 去重后再求和。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from service.toplist.models.top_list_result import (
    ActiveLevel,
    InstParticipation,
    NetAmountLevel,
)

# 统计窗口（自然日）
WINDOW_DAYS = 90
# 活跃度阈值：窗口内上榜交易日数 >= 该值判「活跃」
ACTIVE_MIN_APPEARANCES = 3
# 大额净买额阈值（万元）；net_amount 单位为元，比较前需 ×1e4
LARGE_NET_BUY_10K = 5000.0
# 覆盖水位允许的起始偏差（自然日）；超过则视为窗口未覆盖完整
COVERAGE_START_TOLERANCE_DAYS = 5

# 理由分类：按顺序匹配，先命中先归类（「连续三日累计」优先于单日涨跌幅）
_REASON_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("连续三日累计", ("连续",)),
    ("跌幅偏离", ("跌幅",)),
    ("涨幅偏离", ("涨幅",)),
    ("换手率", ("换手率",)),
    ("振幅", ("振幅",)),
)
_OTHER_CATEGORY = "其他"
REASON_CATEGORY_ORDER = (
    "涨幅偏离",
    "跌幅偏离",
    "换手率",
    "振幅",
    "连续三日累计",
    _OTHER_CATEGORY,
)


def group_by_trade_date(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """按交易日分组（保持升序）。"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in sorted(records, key=lambda r: str(r.get("trade_date", ""))):
        grouped.setdefault(str(record.get("trade_date", ""))[:10], []).append(record)
    return grouped


def appearance_count(records: list[dict[str, Any]]) -> int:
    """去重后的上榜交易日数（同一交易日多条理由只计一次）。"""
    return len(group_by_trade_date(records))


def active_level(count: int) -> ActiveLevel:
    if count <= 0:
        return ActiveLevel.NOT_LISTED
    if count >= ACTIVE_MIN_APPEARANCES:
        return ActiveLevel.ACTIVE
    return ActiveLevel.OCCASIONAL


def dominant_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """主导上榜事件：l_amount 最大者；并列时取 reason 字典序最小者（确定性）。"""
    if not events:
        return None
    return max(
        events,
        key=lambda event: (
            float(event.get("l_amount") or 0.0),
            -_reason_sort_key(event),
        ),
    )


def _reason_sort_key(event: dict[str, Any]) -> int:
    """用于并列时稳定选择：reason 字符串越小 sort key 越小。"""
    reason = str(event.get("reason") or "")
    return int.from_bytes(reason.encode("utf-8")[:8].ljust(8, b"\x00"), "big")


def net_amount_level(net_amount: float | None) -> NetAmountLevel | None:
    """净买额分档（入参单位：元）。"""
    if net_amount is None:
        return None
    threshold = LARGE_NET_BUY_10K * 1e4
    if net_amount >= threshold:
        return NetAmountLevel.LARGE_NET_BUY
    if net_amount <= -threshold:
        return NetAmountLevel.LARGE_NET_SELL
    return NetAmountLevel.NEUTRAL


def classify_reason(reason: str | None) -> str:
    text = str(reason or "")
    for label, keywords in _REASON_RULES:
        if any(keyword in text for keyword in keywords):
            return label
    return _OTHER_CATEGORY


def reason_categories(records: list[dict[str, Any]]) -> list[str]:
    """理由分类去重，按固定顺序输出。"""
    found = {classify_reason(record.get("reason")) for record in records}
    return [category for category in REASON_CATEGORY_ORDER if category in found]


def dedupe_inst_rows(inst_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """席位去重：同一席位同时出现在买入/卖出前 5（金额相同）只计一次。"""
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for record in inst_records:
        key = (
            str(record.get("trade_date", ""))[:10],
            str(record.get("exalter") or ""),
            record.get("buy"),
            record.get("sell"),
            str(record.get("reason") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def is_institution_seat(exalter: str | None) -> bool:
    return "机构专用" in str(exalter or "")


def inst_net_buy(
    inst_records: list[dict[str, Any]],
) -> tuple[float | None, InstParticipation | None]:
    """机构席位净买额（元）与参与方向；无机构席位时 (None, None)。"""
    inst_rows = [
        record
        for record in dedupe_inst_rows(inst_records)
        if is_institution_seat(record.get("exalter"))
    ]
    if not inst_rows:
        return None, None
    total = 0.0
    has_value = False
    for record in inst_rows:
        value = record.get("net_buy")
        if value is None:
            continue
        total += float(value)
        has_value = True
    if not has_value:
        return None, None
    participation = (
        InstParticipation.INST_BUY if total >= 0 else InstParticipation.INST_SELL
    )
    return total, participation


def window_start(window_days: int = WINDOW_DAYS) -> str:
    return (date.today() - timedelta(days=max(window_days, 0))).isoformat()


def coverage_warning(
    covered_dates: list[str],
    latest_trade_date: str | None,
    *,
    window_days: int = WINDOW_DAYS,
) -> list[str] | None:
    """覆盖不足告警：水位未回溯到窗口起点时，上榜次数可能偏低。"""
    if not covered_dates:
        return ["龙虎榜本地覆盖为空，上榜次数不可信（请先运行 sync 或 sync market）"]
    start = window_start(window_days)
    oldest = covered_dates[0]
    newest = covered_dates[-1]
    covered_count = len(covered_dates)
    start_gap = (date.fromisoformat(oldest) - date.fromisoformat(start)).days
    if start_gap > COVERAGE_START_TOLERANCE_DAYS:
        return [
            f"龙虎榜仅覆盖 {covered_count} 个交易日（{oldest}~{newest}），"
            f"统计窗口 {window_days} 天内的上榜次数可能偏低"
            "（可用 sync market --top-list-days 回填）"
        ]
    return None
