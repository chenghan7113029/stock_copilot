"""财务字段公告日对齐（design §6.2，R11）。

口径（spec R11，最终判据）：
- 有 `ann_date` → `visible_from = ann_date`（**不是**报告期；公告日当天及之后可见）；
- 无 `ann_date` → 保守回退到法定披露截止日，并标注 `ann_date_fallback=True`：
  一季报（0331）/ 年报（1231）→ 次年 4 月 30 日；半年报（0630）→ 8 月 31 日；
  三季报（0930）→ 10 月 31 日。
本机事实 KD-2-03：`stock_snapshot` 表无表级 `ann_date`，故无注入即
`BacktestDataGapError`（不拿报告期冒充公告日）。
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from common.exceptions import BacktestDataGapError

FinancialFetch = Callable[..., Iterable[Mapping[str, Any]]]

# report_period 的 MM = 报告期月份 → (月-日, 年份偏移)
CONSERVATIVE_CUTOFFS: Mapping[str, tuple[str, int]] = {
    "0331": ("04-30", 0),  # 一季报
    "0630": ("08-31", 0),  # 半年报
    "0930": ("10-31", 0),  # 三季报
    "1231": ("04-30", 1),  # 年报 → 次年 4 月底
}


def conservative_visible_from(report_period: str) -> str:
    """报告期 → 法定披露截止日（YYYY-MM-DD）；未知报告期按缺口处理。"""
    period = str(report_period).strip()
    if len(period) != 8 or not period.isdigit():
        raise BacktestDataGapError(f"报告期格式非法: {report_period!r}（应为 YYYYMMDD）")
    suffix = period[4:]
    cutoff = CONSERVATIVE_CUTOFFS.get(suffix)
    if cutoff is None:
        raise BacktestDataGapError(
            f"报告期 {period} 无保守截止日口径（只支持一季报/半年报/三季报/年报）"
        )
    month_day, year_offset = cutoff
    year = int(period[:4]) + year_offset
    return f"{year:04d}-{month_day}"


def annotate_visible_from(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """给财务行补 `visible_from` / `ann_date_fallback`，不改其它字段。"""
    annotated: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("code", "")).strip()
        report_period = str(row.get("report_period", "")).strip()
        if not code or not report_period:
            raise BacktestDataGapError(f"财务行缺 code/report_period: {row!r}")
        ann_date = row.get("ann_date")
        if ann_date not in (None, ""):
            visible_from = str(ann_date).strip()
            fallback = False
        else:
            visible_from = conservative_visible_from(report_period)
            fallback = True
        annotated.append(
            {
                **dict(row),
                "code": code,
                "report_period": report_period,
                "visible_from": visible_from,
                "ann_date_fallback": fallback,
            }
        )
    return tuple(sorted(annotated, key=lambda item: (item["code"], item["visible_from"])))


class FinancialTimingAdapter:
    """财务公告日取数；`fetch=None` 表示本机无 `ann_date` 通道（KD-2-03）。"""

    def __init__(self, fetch: FinancialFetch | None = None) -> None:
        self._fetch = fetch

    @property
    def has_source(self) -> bool:
        return self._fetch is not None

    def load_rows(
        self, codes: Sequence[str], as_of: str
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        if self._fetch is None:
            raise BacktestDataGapError(
                "财务公告日数据源缺失：stock_snapshot 无表级 ann_date（KD-2-03），"
                "不得用报告期冒充公告日（R11）"
            )
        rows = self._fetch(codes=list(codes), as_of=as_of)
        grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
        for row in annotate_visible_from(rows):
            grouped.setdefault(row["code"], []).append(row)
        return {code: tuple(items) for code, items in grouped.items()}
