"""后复权 / 分段复权价格适配器（design §6.2，R9）。

本机数据事实（knowledge-delta KD-1-04）：三个 extant fetcher 都返回**前复权**序列，
且本地 `Kline` 表只有 OHLCV 无成交额。所以：

- 请求前复权（`qfq`）→ `InvalidAdjustModeError`（口径写错 ≠ 数据没有）；
- 没有注入数据源（本机默认）→ `BacktestDataGapError`（不静默降级，不按前复权继续）。

注入契约 `fetch(codes=..., start=..., end=..., adjust=...)` 返回原始行（dict），每行
必须含 `code/trade_date/open/high/low/close/factor`；`factor` 是**后复权因子**，
适配器负责换算成后复权价（`adj = raw * factor`），从而保证分红日前后持有期收益连续
（R9 Scenario「分红日无假跳空」）。分段复权（`segmented_hfq`）与后复权共用同一换算：
因子在分红日分段变化，即「分段复权且在分红日调整」。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from common.exceptions import BacktestDataGapError, InvalidAdjustModeError

ADJUST_MODES: tuple[str, ...] = ("hfq", "segmented_hfq")
_PRICE_KEYS = ("open", "high", "low", "close")


def parse_adjust_mode(adjust: str | Enum) -> str:
    """把入参归一成 `hfq` / `segmented_hfq`；前复权与非法值一律 `InvalidAdjustModeError`。"""
    raw = adjust.value if isinstance(adjust, Enum) else adjust
    mode = str(raw).strip().lower()
    if mode in ("qfq", "前复权", "forward"):
        raise InvalidAdjustModeError(
            "拒绝前复权：前复权价会随新分红改写历史价、制造假信号（R9）；"
            "回测必须用 hfq 或 segmented_hfq"
        )
    if mode not in ADJUST_MODES:
        raise InvalidAdjustModeError(
            f"非法复权口径: {adjust!r}；只允许 {ADJUST_MODES}（前复权不在契约内）"
        )
    return mode


FetchPrices = Callable[..., Iterable[Mapping[str, Any]]]


class BacktestPriceAdapter:
    """后复权价适配器；`fetch=None` 表示本机无数据源（缺口显式报错）。"""

    def __init__(self, fetch: FetchPrices | None = None) -> None:
        self._fetch = fetch

    @property
    def has_source(self) -> bool:
        return self._fetch is not None

    def load_rows(
        self,
        codes: Sequence[str],
        start: str,
        end: str,
        adjust: str | Enum,
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        mode = parse_adjust_mode(adjust)
        if self._fetch is None:
            raise BacktestDataGapError(
                "后复权价数据源缺失：三个 extant fetcher 均为前复权（KD-1-04），"
                "未接入 hfq/segmented_hfq 通道前回测拒绝执行（R9）"
            )
        rows = self._fetch(codes=list(codes), start=start, end=end, adjust=mode)
        grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
        for row in rows:
            code = str(row.get("code", "")).strip()
            if code not in grouped:
                grouped[code] = []
            grouped[code].append(_adjusted_row(row, mode))
        return {
            code: tuple(sorted(items, key=lambda item: item["trade_date"]))
            for code, items in grouped.items()
        }


def _adjusted_row(row: Mapping[str, Any], mode: str) -> dict[str, Any]:
    code = str(row.get("code", "")).strip()
    trade_date = str(row.get("trade_date", "")).strip()
    if not code or not trade_date:
        raise BacktestDataGapError(f"价格行缺 code/trade_date: {row!r}")
    factor = row.get("factor")
    if factor is None:
        raise BacktestDataGapError(
            f"{code} {trade_date} 缺后复权因子 factor：无法确认口径，拒绝按原始价继续（R9）"
        )
    factor_value = float(factor)
    if factor_value <= 0:
        raise BacktestDataGapError(f"{code} {trade_date} 后复权因子非法: {factor!r}")
    missing = [key for key in _PRICE_KEYS if row.get(key) is None]
    if missing:
        raise BacktestDataGapError(f"{code} {trade_date} 价格缺口: {missing}")
    adjusted: dict[str, Any] = {
        "code": code,
        "trade_date": trade_date,
        "adjust_mode": mode,
        "factor": factor_value,
        "suspended": bool(row.get("suspended", False)),
        "delisted": bool(row.get("delisted", False)),
        "st": bool(row.get("st", False)),
    }
    for key in _PRICE_KEYS:
        adjusted[key] = float(row[key]) * factor_value
    # 成交额/涨跌停价是「撮合所需字段」，不在本适配器伪造（缺就留 None，由 market_rules 报缺口）
    for key in ("amount", "limit_up_price", "limit_down_price"):
        value = row.get(key)
        adjusted[key] = None if value is None else float(value)
    return adjusted
