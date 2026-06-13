"""SourceManager：多数据源选源、优先级管理与自动 failover。

对齐 ref/daily_stock_analysis 的 DataFetcherManager 设计：
- 持有 fetcher 列表，按 priority 排序（数字越小越优先）
- 取数时顺序调用，第一个成功则返回；全部失败抛 DataProviderError
- 通过 from_config() 工厂方法按配置实例化（未启用的源不创建）
"""

from __future__ import annotations

import logging
from typing import Any

from common.exceptions import DataProviderError
from data_provider.base import BaseFetcher, FetchResult

logger = logging.getLogger(__name__)


class SourceManager:
    """多数据源管理器（对齐 daily_stock_analysis DataFetcherManager）。"""

    def __init__(self, fetchers: list[BaseFetcher]) -> None:
        self._fetchers: list[BaseFetcher] = sorted(fetchers, key=lambda f: f.priority)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SourceManager":
        """根据 config 的 data_sources.enabled 列表按需实例化 fetcher。

        config 结构示例（对应 app.yaml）：
            data_sources:
              enabled:
                - name: akshare
                  priority: 1
                - name: baostock
                  priority: 2
        """
        enabled: list[dict] = config.get("data_sources", {}).get("enabled", [])
        fetchers: list[BaseFetcher] = []

        for src in enabled:
            name = src.get("name", "").lower()
            priority_override = src.get("priority")

            fetcher = cls._build_fetcher(name, priority_override)
            if fetcher is not None:
                fetchers.append(fetcher)
            else:
                logger.warning("未知数据源 %r，跳过", name)

        if not fetchers:
            raise DataProviderError("配置中没有启用任何数据源，请检查 config/app.yaml")

        return cls(fetchers)

    @staticmethod
    def _build_fetcher(name: str, priority_override: int | None) -> BaseFetcher | None:
        """根据名称构建 fetcher 实例，可覆写优先级。"""
        if name == "akshare":
            from data_provider.akshare.fetcher import AKShareFetcher
            f = AKShareFetcher()
            if priority_override is not None:
                f.priority = priority_override
            return f

        if name == "baostock":
            from data_provider.baostock.fetcher import BaostockFetcher
            f = BaostockFetcher()
            if priority_override is not None:
                f.priority = priority_override
            return f

        return None

    # ── 取数 ─────────────────────────────────────────────────────────────────

    @property
    def fetchers(self) -> list[BaseFetcher]:
        return list(self._fetchers)

    def fetch_quote(self, code: str, exchange: str) -> FetchResult:
        """按优先级尝试行情取数，failover 到下一源。"""
        return self._fetch_with_fallback("fetch_quote", code, exchange)

    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        """按优先级尝试基本面取数，failover 到下一源。"""
        return self._fetch_with_fallback("fetch_fundamentals", code, exchange)

    def fetch_all(self, code: str, exchange: str) -> FetchResult:
        """按优先级尝试完整取数，failover 到下一源。"""
        return self._fetch_with_fallback("fetch_all", code, exchange)

    def _fetch_with_fallback(self, method: str, code: str, exchange: str) -> FetchResult:
        last_error: str | None = None
        for fetcher in self._fetchers:
            try:
                result: FetchResult = getattr(fetcher, method)(code, exchange)
                if result.ok:
                    logger.debug("取数成功: %s via %s", code, fetcher.source_name)
                    return result
                logger.info("源 %s 返回失败: %s，尝试下一源", fetcher.source_name, result.error)
                last_error = result.error
            except Exception as exc:
                logger.warning("源 %s 抛出异常: %s，尝试下一源", fetcher.source_name, exc)
                last_error = str(exc)

        return FetchResult(
            code=code,
            source="all_failed",
            error=f"所有数据源均失败。最后错误: {last_error}",
        )
