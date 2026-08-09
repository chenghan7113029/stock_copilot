"""DataFetcherRouter：配置驱动的唯一选源入口。"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from data_provider.base import BaseFetcher

logger = logging.getLogger(__name__)


class DataFetcherRouter:
    """按 `data_sources.enabled` + `priority` 实例化并排序 fetcher。

    Fetcher 类上的默认 `priority` 仅在 config 未给 priority 时作为回退，
    运行态顺序以实例上的 priority（已被 config 覆写）为准。
    """

    def __init__(self, fetchers: list[BaseFetcher]) -> None:
        self._fetchers: list[BaseFetcher] = sorted(fetchers, key=lambda f: f.priority)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DataFetcherRouter":
        enabled: list[dict] = config.get("data_sources", {}).get("enabled", [])
        fetchers: list[BaseFetcher] = []
        for src in enabled:
            name = str(src.get("name", "")).lower()
            priority_override = src.get("priority")
            fetcher = cls.build_fetcher(name, priority_override, src, config)
            if fetcher is not None:
                fetchers.append(fetcher)
            elif name == "tushare":
                pass
            elif name:
                logger.warning("未知数据源 %r，跳过", name)
        return cls(fetchers)

    @staticmethod
    def build_fetcher(
        name: str,
        priority_override: int | None,
        src: dict | None = None,
        config: dict | None = None,
    ) -> BaseFetcher | None:
        """根据名称构建 fetcher；未启用/缺 token 时返回 None（不实例化）。"""
        if name == "akshare":
            from data_provider.akshare.fetcher import AKShareFetcher

            f: BaseFetcher = AKShareFetcher()
            if priority_override is not None:
                f.priority = priority_override
            return f

        if name == "baostock":
            from data_provider.baostock.fetcher import BaostockFetcher

            f = BaostockFetcher(config=config or {})
            if priority_override is not None:
                f.priority = priority_override
            return f

        if name == "tushare":
            token = ((src or {}).get("token") or os.environ.get("TUSHARE_TOKEN") or "").strip()
            if not token:
                logger.warning(
                    "Tushare 已启用但未配置 token，跳过（请编辑 config/app.yaml 或设置 TUSHARE_TOKEN）"
                )
                return None
            from data_provider.tushare.fetcher import TushareFetcher

            f = TushareFetcher(token=token)
            if priority_override is not None:
                f.priority = priority_override
            return f

        return None

    @property
    def fetchers(self) -> list[BaseFetcher]:
        return list(self._fetchers)

    def fetchers_with_method(self, method: str) -> list[BaseFetcher]:
        """返回实现了指定方法的 fetcher（保持 priority 序）。"""
        out: list[BaseFetcher] = []
        for f in self._fetchers:
            fn = getattr(f, method, None)
            if callable(fn):
                out.append(f)
        return out

    def require_fetchers(self) -> list[BaseFetcher]:
        """在线取数入口：无可用源时抛错。"""
        from common.exceptions import DataProviderError

        if not self._fetchers:
            raise DataProviderError("配置中没有启用任何数据源，请检查 config/app.yaml")
        return self.fetchers
