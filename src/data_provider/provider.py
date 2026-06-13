"""数据提供者 Facade：get_stock_data(code) -> StockData。

职责：
- 非 A 股代码拒绝（抛 UnsupportedMarketError）
- 调用 SourceManager，按优先级逐字段填充 StockData
- 记录每字段命中的数据源（field_sources）
- 合并 missing_fields
- 如果 DAO 实例已注入，则将每个源的原始 FetchResult 落库

调用示例：
    provider = StockDataProvider.from_config(config)
    stock = provider.get_stock_data("600519")
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from common.exceptions import UnsupportedMarketError
from common.models.stock_data import StockData
from data_provider.base import is_a_share, normalize_stock_code
from data_provider.manager import SourceManager

logger = logging.getLogger(__name__)

# 需要从 FetchResult.data 映射到 StockData 字段的全部键名
# （顺序不重要，set_field 会保留首次写入的高优先级值）
_STOCK_DATA_FIELDS = {
    "name", "exchange",
    "current_price", "shares_outstanding", "market_cap",
    "eps", "bvps", "dividend_per_share",
    "revenue", "net_income", "ebit", "ebitda", "operating_margin",
    "roe", "roic", "tax_rate", "pe_ratio", "pb_ratio",
    "fcf", "capex", "depreciation",
    "total_assets", "total_liabilities", "current_assets", "current_liabilities",
    "shareholder_equity", "net_debt", "short_term_debt", "long_term_debt",
    "interest_expense", "net_working_capital", "net_fixed_assets",
    "accounts_receivable", "inventory", "accounts_payable",
    "dividend_yield", "dividend_payout_ratio", "dividend_growth_rate",
    "prior_roa", "prior_debt_ratio", "prior_current_ratio",
    "prior_shares_outstanding", "prior_gross_margin", "prior_asset_turnover",
    "net_interest_margin", "npl_ratio", "provision_coverage",
    "growth_rate", "sbc", "shares_issued", "shares_repurchased",
}


class StockDataProvider:
    """统一 A 股数据提供者。"""

    def __init__(self, manager: SourceManager, repo: Any = None) -> None:
        self._manager = manager
        self._repo = repo  # 可选 DAO，若注入则落库

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: Any = None) -> "StockDataProvider":
        manager = SourceManager.from_config(config)
        return cls(manager, repo)

    def get_stock_data(self, raw_code: str) -> StockData:
        """获取指定 A 股的完整估值数据。

        非 A 股代码（港股/美股等）抛 UnsupportedMarketError。
        """
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code, exchange = normalize_stock_code(raw_code)
        stock = StockData(code=code, exchange=exchange)

        # 按优先级从高到低遍历各 fetcher，逐字段填充
        for fetcher in self._manager.fetchers:
            try:
                result = fetcher.fetch_all(code, exchange)
            except Exception as exc:
                logger.warning("fetcher %s 抛出异常: %s", fetcher.source_name, exc)
                continue

            if not result.ok:
                logger.info("fetcher %s 未成功: %s", fetcher.source_name, result.error)
                continue

            source = fetcher.source_name
            self._merge_result(stock, result.data, source)

            # 落库（每源独立存储）
            if self._repo is not None:
                try:
                    self._repo.upsert_from_fetch_result(result)
                except Exception as exc:
                    logger.warning("DAO 落库失败 (%s / %s): %s", code, source, exc)

        # 计算派生字段（PE/PB/dividend_yield 若可得）
        self._derive_ratios(stock)

        # 最终整理 missing_fields
        self._audit_missing(stock)

        return stock

    # ── 私有辅助 ─────────────────────────────────────────────────────────────

    def _merge_result(self, stock: StockData, data: dict[str, Any], source: str) -> None:
        """将 FetchResult.data 中的字段合并到 StockData（高优先级先写，不被覆盖）。"""
        # 元数据单独处理
        if "data_timestamp" in data and stock.data_timestamp is None:
            ts = data["data_timestamp"]
            stock.data_timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else ts

        if "fundamental_report_date" in data and stock.fundamental_report_date is None:
            rd = data["fundamental_report_date"]
            stock.fundamental_report_date = rd if isinstance(rd, date) else None

        if stock.name == "" and data.get("name"):
            stock.name = str(data["name"])

        for field_name in _STOCK_DATA_FIELDS - {"name", "exchange"}:
            v = data.get(field_name)
            if v is not None and isinstance(v, (int, float)):
                stock.set_field(field_name, float(v), source)

    def _derive_ratios(self, stock: StockData) -> None:
        """在字段合并后计算依赖行情的派生比率。"""
        price = stock.current_price
        eps = stock.eps
        bvps = stock.bvps
        dps = stock.dividend_per_share

        if price and price > 0:
            if eps and eps != 0 and stock.pe_ratio is None:
                stock.set_field("pe_ratio", price / eps, "derived")
            if bvps and bvps > 0 and stock.pb_ratio is None:
                stock.set_field("pb_ratio", price / bvps, "derived")
            if dps and dps > 0 and stock.dividend_yield is None:
                stock.set_field("dividend_yield", (dps / price) * 100, "derived")

    def _audit_missing(self, stock: StockData) -> None:
        """遍历所有数值字段，将 None 字段加入 missing_fields。"""
        import dataclasses
        for f in dataclasses.fields(stock):
            if f.name in ("code", "name", "exchange", "field_sources",
                          "data_timestamp", "fundamental_report_date", "missing_fields"):
                continue
            if getattr(stock, f.name) is None:
                if f.name not in stock.missing_fields:
                    stock.missing_fields.append(f.name)
