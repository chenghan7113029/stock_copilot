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
from dao.stock_snapshot_repo import StockSnapshotRepo

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

    def __init__(self, manager: SourceManager, repo: Any = None, config: dict[str, Any] | None = None) -> None:
        self._manager = manager
        self._repo = repo  # 可选 DAO，若注入则落库
        self._config = config or {}

    @classmethod
    def from_config(cls, config: dict[str, Any], repo: Any = None) -> "StockDataProvider":
        manager = SourceManager.from_config(config)
        return cls(manager, repo, config)

    def get_stock_data(self, raw_code: str) -> StockData:
        """获取指定 A 股的完整估值数据。

        非 A 股代码（港股/美股等）抛 UnsupportedMarketError。

        实现策略（防 SQLite 锁）：
        1. 先完成全部网络请求，收集 FetchResult 列表
        2. 所有网络操作结束后，开短生命周期 Session 批量 upsert
        """
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code, exchange = normalize_stock_code(raw_code)
        stock = StockData(code=code, exchange=exchange)

        # ── 阶段一：网络取数（不持有 Session）──────────────────────────────────
        fetch_results: list = []
        for fetcher in self._manager.fetchers:
            try:
                result = fetcher.fetch_all(code, exchange)
            except Exception as exc:
                logger.warning("fetcher %s 抛出异常: %s", fetcher.source_name, exc)
                continue

            if not result.ok:
                logger.info("fetcher %s 未成功: %s", fetcher.source_name, result.error)
                continue

            fetch_results.append(result)
            self._merge_result(stock, result.data, fetcher.source_name)

        # ── 阶段二：批量落库（短生命周期 Session）──────────────────────────────
        if self._repo is not None and fetch_results:
            try:
                self._repo.upsert_many(fetch_results)
            except Exception as exc:
                logger.warning("DAO 批量落库失败 (%s): %s", code, exc)

        # 计算派生字段（PE/PB/dividend_yield 若可得）
        self._derive_ratios(stock)
        self._derive_ttm_fields(stock)
        self._derive_fcf_fields(stock)

        # 最终整理 missing_fields
        self._audit_missing(stock)

        return stock

    def get_stock_data_offline(self, raw_code: str) -> StockData | None:
        """从本地快照合并重建 StockData，不触发网络请求。"""
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )
        if self._repo is None:
            return None

        code, exchange = normalize_stock_code(raw_code)
        snapshots = self._repo.find_by_code(code)
        if not snapshots:
            return None

        by_source: dict[str, Any] = {}
        for snap in snapshots:
            if snap.source not in by_source:
                by_source[snap.source] = snap

        priority_order = {f.source_name: f.priority for f in self._manager.fetchers}
        sorted_sources = sorted(by_source.keys(), key=lambda s: priority_order.get(s, 999))

        stock = StockData(code=code, exchange=exchange)
        for source in sorted_sources:
            data = self._snapshot_to_dict(by_source[source])
            self._merge_result(stock, data, source)

        self._derive_ratios(stock)
        self._derive_ttm_fields(stock)
        self._derive_fcf_fields(stock)
        self._audit_missing(stock)
        return stock

    # ── 私有辅助 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
        """将 ORM 快照转为与 FetchResult.data 兼容的 dict。"""
        data: dict[str, Any] = {}
        for field_name in _STOCK_DATA_FIELDS:
            v = getattr(snapshot, field_name, None)
            if v is not None:
                data[field_name] = v
        hist_pe = StockSnapshotRepo.historical_pe_from_snapshot(snapshot)
        if hist_pe is not None:
            data["historical_pe"] = hist_pe
        if snapshot.data_timestamp is not None:
            data["data_timestamp"] = snapshot.data_timestamp
        if snapshot.name:
            data["name"] = snapshot.name
        if snapshot.exchange:
            data["exchange"] = snapshot.exchange
        return data

    def _merge_result(self, stock: StockData, data: dict[str, Any], source: str) -> None:
        """将 FetchResult.data 中的字段合并到 StockData（高优先级先写，不被覆盖）。"""
        self._merge_fields(stock, data, source)

    def _merge_fields(self, stock: StockData, data: dict[str, Any], source: str) -> None:
        """将 data dict 中的字段合并到 StockData（高优先级先写，不被覆盖）。"""
        # 元数据单独处理
        if "data_timestamp" in data and stock.data_timestamp is None:
            ts = data["data_timestamp"]
            stock.data_timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else ts

        if "fundamental_report_date" in data and stock.fundamental_report_date is None:
            rd = data["fundamental_report_date"]
            stock.fundamental_report_date = rd if isinstance(rd, date) else None

        if stock.name == "" and data.get("name"):
            stock.name = str(data["name"])

        hist_pe = data.get("historical_pe")
        if (
            isinstance(hist_pe, list)
            and len(hist_pe) >= 3
            and stock.historical_pe is None
        ):
            stock.historical_pe = hist_pe
            stock.field_sources["historical_pe"] = source
            if "historical_pe" in stock.missing_fields:
                stock.missing_fields.remove("historical_pe")

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

    def _derive_ttm_fields(self, stock: StockData) -> None:
        """用 epsTTM × 总股本推导 TTM 净利润（跨源合并后执行）。"""
        eps = stock.eps
        shares = stock.shares_outstanding
        if eps and shares and eps > 0 and shares > 0:
            stock.net_income = eps * shares
            stock.field_sources["net_income"] = "derived"
            if "net_income" in stock.missing_fields:
                stock.missing_fields.remove("net_income")

    def _derive_fcf_fields(self, stock: StockData) -> None:
        """net_income TTM 修正后，用同一推导链刷新 FCF。"""
        if stock.field_sources.get("net_income") != "derived":
            return
        from data_provider.baostock.fetcher import derive_fcf

        fcf_rate = float(self._config.get("value_analysis", {}).get("fcf_rate", 0.85))
        data = {
            "revenue": stock.revenue,
            "net_income": stock.net_income,
            "operating_margin": stock.operating_margin,
        }
        fcf, _ = derive_fcf(data, fcf_rate)
        if fcf is not None and fcf > 0:
            stock.fcf = fcf
            stock.field_sources["fcf"] = "derived"
            if "fcf" in stock.missing_fields:
                stock.missing_fields.remove("fcf")

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
