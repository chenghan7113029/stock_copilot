"""选源策略：价值面字段合并 vs 旁路 failover。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class FailoverResult:
    value: Any
    source_name: str
    errors: tuple[str, ...] = ()


class FailoverStrategy:
    """按 priority 顺序尝试，首次成功即停。"""

    @staticmethod
    def try_each(
        fetchers: list[Any],
        call: Callable[[Any], T],
        *,
        source_name: Callable[[Any], str] | None = None,
        skip: Callable[[Any], bool] | None = None,
    ) -> FailoverResult:
        errors: list[str] = []
        name_of = source_name or (lambda f: getattr(f, "source_name", type(f).__name__))
        for fetcher in fetchers:
            if skip is not None and skip(fetcher):
                continue
            name = name_of(fetcher)
            try:
                value = call(fetcher)
                return FailoverResult(value=value, source_name=name, errors=tuple(errors))
            except Exception as exc:  # noqa: BLE001 — failover 需吞掉单源失败
                logger.warning("源 %s 失败: %s，尝试下一源", name, exc)
                errors.append(f"{name}: {exc}")
        raise RuntimeError("; ".join(errors) if errors else "no fetchers available")


class ValueMergeStrategy:
    """字段级 priority 合并：高优先级先写，低优先级不覆盖已有值。

    不包含任何「按 source 名强制 override」特例。
    """

    @staticmethod
    def should_write(existing_source: str | None, new_source: str, source_priority: Callable[[str], int]) -> bool:
        if not existing_source:
            return True
        return source_priority(new_source) < source_priority(existing_source)
