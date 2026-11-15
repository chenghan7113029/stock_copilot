"""退市 / ST / 历史指数成分适配器（design §6.2，R12）。

生存偏差的三条硬要求：退市股在退市日**之前**计入、ST 按**当时**状态判定（不回填今日
标签）、指数成分用**历史时点**名单。本机无权威名单源 → 无注入即 `BacktestDataGapError`
（不静默剔除、不用当前成分回看历史）。
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from common.exceptions import BacktestDataGapError

UniverseFetch = Callable[..., Iterable[Mapping[str, Any]]]


class UniverseAdapter:
    """历史成分 / 退市 / ST 取数；`fetch=None` 表示本机无权威名单源。"""

    def __init__(self, fetch: UniverseFetch | None = None) -> None:
        self._fetch = fetch

    @property
    def has_source(self) -> bool:
        return self._fetch is not None

    def load_members(self, as_of: str, universe_spec: Mapping[str, Any]) -> tuple[str, ...]:
        """返回 `as_of` 时点的成分名单（历史成分，不用当前成分回看历史）。"""
        if self._fetch is None:
            raise BacktestDataGapError(
                "历史成分名单缺失：不得用当前成分回看历史（R12 Scenario「历史成分与当前成分不同」）"
            )
        rows = self._fetch(as_of=as_of, spec=dict(universe_spec))
        codes: list[str] = []
        for row in rows:
            code = str(row.get("code", "")).strip()
            if not code:
                raise BacktestDataGapError(f"成分名单行缺 code: {row!r}")
            codes.append(code)
        if not codes:
            raise BacktestDataGapError(f"{as_of} 成分名单为空：按缺口处理，不静默降级")
        return tuple(sorted(dict.fromkeys(codes)))

    def load_flags(
        self, codes: Sequence[str], as_of: str
    ) -> dict[str, dict[str, Any]]:
        """返回 {code: {delisted: bool, delist_date: str|None, st: bool}}（按时点）。"""
        if self._fetch is None:
            raise BacktestDataGapError(
                "退市/ST 名单缺失：无法排除生存偏差（R12 Scenario「名单不可得时报缺口」）"
            )
        rows = self._fetch(codes=list(codes), as_of=as_of)
        flags: dict[str, dict[str, Any]] = {}
        for row in rows:
            code = str(row.get("code", "")).strip()
            if not code:
                raise BacktestDataGapError(f"退市/ST 行缺 code: {row!r}")
            if "st" not in row or "delisted" not in row:
                raise BacktestDataGapError(
                    f"{code} 退市/ST 标记不完整: {sorted(row)}（按缺口处理）"
                )
            flags[code] = {
                "delisted": bool(row["delisted"]),
                "delist_date": (
                    None if row.get("delist_date") in (None, "") else str(row["delist_date"])
                ),
                "st": bool(row["st"]),
            }
        missing = [code for code in codes if code not in flags]
        if missing:
            raise BacktestDataGapError(f"退市/ST 标记缺失: {missing[:5]}（共 {len(missing)} 只）")
        return flags

    # ---- T2-fix-6：`UniverseProvider` 协议（service/universe.build_universe 的注入面）----
    def historical_constituents(self, as_of: str, scope: str) -> tuple[str, ...]:
        """历史时点成分名单；数据源不可得 → 缺口，可得但确实为空 → 空 tuple（合法）。"""
        if self._fetch is None:
            raise BacktestDataGapError(
                "历史成分名单缺失：不得用当前成分回看历史（R12/T2-fix-6）"
            )
        rows = self._fetch(kind="constituents", as_of=as_of, scope=scope)
        codes: list[str] = []
        for row in rows:
            code = str(row.get("code", "")).strip()
            if code:
                codes.append(code)
        return tuple(codes)

    def delisted_codes(self, as_of: str) -> tuple[str, ...]:
        """截至 `as_of` 的退市名单；不可得 → 缺口。"""
        if self._fetch is None:
            raise BacktestDataGapError("退市名单缺失：无法排除生存偏差（R12/T2-fix-6）")
        rows = self._fetch(kind="delisted", as_of=as_of)
        return tuple(
            str(row["code"]).strip() for row in rows if str(row.get("code", "")).strip()
        )

    def st_status(self, code: str, as_of: str) -> bool:
        """`as_of` 时点的 ST 状态；不可得 → 缺口（不回填今日标签）。"""
        if self._fetch is None:
            raise BacktestDataGapError("ST 名单缺失：无法按时点判定（R12/T2-fix-6）")
        rows = list(self._fetch(kind="st", code=code, as_of=as_of))
        if not rows or "st" not in rows[0]:
            raise BacktestDataGapError(f"{code} 在 {as_of} 的 ST 状态不可得（R12）")
        return bool(rows[0]["st"])
