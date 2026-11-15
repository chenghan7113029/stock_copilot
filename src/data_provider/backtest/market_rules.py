"""撮合所需市场数据适配器：成交额 / 涨跌停价 / 停牌（design §6.2，R7/R8）。

本机事实（KD-4-07 / KD-3-07）：`kline` 表无成交额；仓库的「涨跌停」只是市场广度近似，
不可用于单笔撮合。因此本适配器只提供契约：注入数据源才能取到字段，否则
`BacktestDataGapError`（**不按 0**、**不按可成交**）。
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from common.exceptions import BacktestDataGapError

MarketFetch = Callable[..., Iterable[Mapping[str, Any]]]

_REQUIRED_KEYS = ("amount", "limit_up_price", "limit_down_price", "suspended")


def _require_value(code: str, trade_date: str, key: str, row: Mapping[str, Any]) -> Any:
    value = row.get(key)
    if value is None:
        raise BacktestDataGapError(
            f"{code} {trade_date} 缺 {key}：撮合无法判定（不按 0 / 不按可成交处理，R7/R8）"
        )
    return value


class MarketRulesAdapter:
    """成交额 / 涨跌停价 / 停牌取数；`fetch=None` 表示本机无数据源。"""

    def __init__(self, fetch: MarketFetch | None = None) -> None:
        self._fetch = fetch

    @property
    def has_source(self) -> bool:
        return self._fetch is not None

    def load_rows(
        self,
        codes: Sequence[str],
        start: str,
        end: str,
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        if self._fetch is None:
            raise BacktestDataGapError(
                "成交额/涨跌停/停牌数据源缺失：kline 表无 amount（KD-4-07），"
                "涨跌停无单笔口径（KD-3-07）；补齐前撮合拒绝执行（R7/R8）"
            )
        rows = self._fetch(codes=list(codes), start=start, end=end)
        grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
        for row in rows:
            code = str(row.get("code", "")).strip()
            trade_date = str(row.get("trade_date", "")).strip()
            if not code or not trade_date:
                raise BacktestDataGapError(f"市场数据行缺 code/trade_date: {row!r}")
            record = {
                "code": code,
                "trade_date": trade_date,
                "amount": float(_require_value(code, trade_date, "amount", row)),
                "limit_up_price": float(
                    _require_value(code, trade_date, "limit_up_price", row)
                ),
                "limit_down_price": float(
                    _require_value(code, trade_date, "limit_down_price", row)
                ),
                "suspended": bool(_require_value(code, trade_date, "suspended", row)),
            }
            grouped.setdefault(code, []).append(record)
        return {
            code: tuple(sorted(items, key=lambda item: item["trade_date"]))
            for code, items in grouped.items()
        }


def merge_market_fields(
    price_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    market_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """把撮合字段并进价格行；任一日期缺字段即 `BacktestDataGapError`。"""
    merged: dict[str, tuple[dict[str, Any], ...]] = {}
    for code, bars in price_rows.items():
        fields = {row["trade_date"]: row for row in market_rows.get(code, ())}
        merged_bars: list[dict[str, Any]] = []
        for bar in bars:
            trade_date = bar["trade_date"]
            extra = fields.get(trade_date)
            if extra is None:
                raise BacktestDataGapError(
                    f"{code} {trade_date} 缺撮合字段（成交额/涨跌停/停牌）：不静默降级（R7/R8）"
                )
            merged_bars.append({**bar, **{k: extra[k] for k in _REQUIRED_KEYS}})
        merged[code] = tuple(merged_bars)
    return merged
