"""AKShare 数据源实现。

基于 ref/valueinvest/valueinvest/data/fetcher/akshare.py 的设计，
适配本项目 BaseFetcher 接口与 FetchResult 缺失语义（None ≠ 0）。

关键差异：
- 缺失字段用 None 标记，不填 0；由 missing_fields 列出。
- 指数退避重试包裹每个 API 调用（见 base.retry_with_backoff）。
- 不计算派生指标（pe/pb/bvps from shares），留给 Provider 层合并后统一计算。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.akshare.field_mapping import (
    BALANCE_SHEET_FIELD_MAP,
    CASHFLOW_FIELD_MAP,
    FINANCIAL_INDICATOR_FIELD_MAP,
    INCOME_STMT_FIELD_MAP,
    QUOTE_INFO_FIELD_MAP,
)
from data_provider.base import BaseFetcher, FetchResult, retry_with_backoff

logger = logging.getLogger(__name__)


def _parse_value(raw: Any) -> Optional[float]:
    """将原始值解析为 float，无效值返回 None（不填 0）。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("--", "-", "nan", "None", "N/A"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _parse_date(raw: Any) -> Optional[date]:
    """解析 YYYYMMDD 或 YYYY-MM-DD 格式为 date。"""
    if raw is None:
        return None
    s = str(raw).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class AKShareFetcher(BaseFetcher):
    """AKShare 数据源（主源，免 token）。

    优先级：1（最高）
    """

    source_name = "akshare"
    priority = 1

    def _get_ak(self):
        import akshare as ak
        return ak

    # ── 行情 ─────────────────────────────────────────────────────────────────

    def fetch_quote(self, code: str, exchange: str) -> FetchResult:
        """从 stock_individual_info_em 获取实时行情。"""
        data: dict[str, Any] = {}
        missing: list[str] = []

        try:
            ak = self._get_ak()
            raw_df = retry_with_backoff(ak.stock_individual_info_em, symbol=code)
            info = dict(zip(raw_df["item"], raw_df["value"]))

            for ak_col, our_field in QUOTE_INFO_FIELD_MAP.items():
                v = _parse_value(info.get(ak_col))
                if v is not None:
                    data[our_field] = v
                else:
                    missing.append(our_field)

            data["name"] = str(info.get("股票简称", "")) or None  # type: ignore[assignment]
            data["exchange"] = exchange
            data["code"] = code
            data["data_timestamp"] = datetime.now().isoformat()

        except Exception as exc:
            logger.warning("AKShare quote 失败 %s: %s", code, exc)
            return FetchResult(code=code, source=self.source_name, error=str(exc))

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

    def fetch_kline(
        self,
        code: str,
        exchange: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """获取日 K 线 OHLCV（前复权），列名与 Baostock 对齐。"""
        del exchange  # AKShare 使用 6 位代码即可
        ak = self._get_ak()
        raw_df = retry_with_backoff(
            ak.stock_zh_a_hist,
            symbol=code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if raw_df is None or raw_df.empty:
            raise DataProviderError(f"AKShare 未查询到 {code} 的 K 线数据")

        column_map = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
        df = raw_df.rename(columns=column_map)
        df["date"] = df["date"].astype(str).str[:10]
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["date", "open", "high", "low", "close", "volume"]]

    # ── 基本面 ────────────────────────────────────────────────────────────────

    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        """分别调用新浪财报 API 获取三大报表、分红、财务指标，并合并。"""
        data: dict[str, Any] = {}
        missing: list[str] = []

        self._fetch_balance_sheet(code, data, missing)
        self._fetch_income_stmt(code, data, missing)
        self._fetch_cashflow(code, data, missing)
        self._fetch_dividends(code, data, missing)
        self._fetch_financial_indicators(code, data, missing)
        self._derive_computed_fields(data)

        return FetchResult(code=code, source=self.source_name, data=data, missing_fields=missing)

    # ── 私有：各报表 ──────────────────────────────────────────────────────────

    def _fetch_balance_sheet(self, code: str, data: dict, missing: list) -> None:
        try:
            ak = self._get_ak()
            df = retry_with_backoff(ak.stock_financial_report_sina, stock=code, symbol="资产负债表")
            if df is None or df.empty:
                missing.append("balance_sheet")
                return

            row = df.iloc[0]

            # 报告期
            report_date = _parse_date(row.get("报告日"))
            if report_date:
                data["fundamental_report_date"] = report_date

            current_liabilities: Optional[float] = None

            for col in df.columns:
                col_str = str(col)
                field_name = BALANCE_SHEET_FIELD_MAP.get(col_str)
                if not field_name:
                    # 模糊匹配归母权益
                    if "归属于母公司股东" in col_str and "权益" in col_str:
                        field_name = "shareholder_equity"
                    else:
                        continue

                v = _parse_value(row.get(col))
                if field_name == "_current_liabilities":
                    current_liabilities = v
                    if v is not None:
                        data["current_liabilities"] = v
                elif field_name not in data or data[field_name] is None:
                    if v is not None:
                        data[field_name] = v

            # 净营运资本 = 流动资产 − 流动负债
            ca = data.get("current_assets")
            cl = current_liabilities
            if ca is not None and cl is not None:
                data["net_working_capital"] = ca - cl

        except Exception as exc:
            logger.warning("AKShare balance sheet 失败 %s: %s", code, exc)
            missing.append("balance_sheet")

    def _fetch_income_stmt(self, code: str, data: dict, missing: list) -> None:
        try:
            ak = self._get_ak()
            df = retry_with_backoff(ak.stock_financial_report_sina, stock=code, symbol="利润表")
            if df is None or df.empty:
                missing.append("income_stmt")
                return

            row = df.iloc[0]
            profit_before_tax: Optional[float] = None
            income_tax: Optional[float] = None

            for col in df.columns:
                col_str = str(col)
                field_name = INCOME_STMT_FIELD_MAP.get(col_str)
                if not field_name:
                    continue

                v = _parse_value(row.get(col))
                if field_name == "_profit_before_tax":
                    profit_before_tax = v
                elif field_name == "_income_tax":
                    income_tax = v
                elif field_name not in data or data[field_name] is None:
                    if v is not None:
                        data[field_name] = v

            # 税率
            if profit_before_tax is not None and income_tax is not None and profit_before_tax != 0:
                data["tax_rate"] = (income_tax / profit_before_tax) * 100

            # 营业利润率
            revenue = data.get("revenue")
            ebit = data.get("ebit")
            if revenue and ebit and revenue != 0:
                data["operating_margin"] = (ebit / revenue) * 100

        except Exception as exc:
            logger.warning("AKShare income stmt 失败 %s: %s", code, exc)
            missing.append("income_stmt")

    def _fetch_cashflow(self, code: str, data: dict, missing: list) -> None:
        try:
            ak = self._get_ak()
            df = retry_with_backoff(ak.stock_financial_report_sina, stock=code, symbol="现金流量表")
            if df is None or df.empty:
                missing.append("cashflow")
                return

            row = df.iloc[0]
            operating_cf: Optional[float] = None

            for col in df.columns:
                col_str = str(col)
                field_name = CASHFLOW_FIELD_MAP.get(col_str)
                if not field_name:
                    continue

                v = _parse_value(row.get(col))
                if field_name == "_operating_cf":
                    operating_cf = v
                elif field_name not in data or data[field_name] is None:
                    if v is not None:
                        data[field_name] = abs(v) if field_name in ("capex", "depreciation") else v

            # FCF = 经营现金流 − capex
            if operating_cf is not None:
                capex = data.get("capex")
                data["fcf"] = operating_cf - (capex or 0.0)

        except Exception as exc:
            logger.warning("AKShare cashflow 失败 %s: %s", code, exc)
            missing.append("cashflow")

    def _fetch_dividends(self, code: str, data: dict, missing: list) -> None:
        try:
            ak = self._get_ak()
            df = retry_with_backoff(ak.stock_dividend_cn, symbol=code)
            if df is None or df.empty:
                missing.append("dividend_per_share")
                return

            recent = df.head(5)
            latest_amount = _parse_value(recent.iloc[0].get("分红金额")) if "分红金额" in recent.columns else None

            if latest_amount is not None:
                data["dividend_per_share"] = latest_amount / 10  # 每10股 → 每股

            # 股息增长率（近3期以上才计算）
            dividends = []
            for _, row in recent.iterrows():
                v = _parse_value(row.get("分红金额"))
                if v is not None and v > 0:
                    dividends.append(v)

            if len(dividends) >= 2:
                years = len(dividends) - 1
                try:
                    growth = ((dividends[0] / dividends[-1]) ** (1 / years) - 1) * 100
                    data["dividend_growth_rate"] = growth
                except ZeroDivisionError:
                    pass

        except Exception as exc:
            logger.warning("AKShare dividend 失败 %s: %s", code, exc)
            missing.append("dividend_per_share")

    def _fetch_financial_indicators(self, code: str, data: dict, missing: list) -> None:
        try:
            ak = self._get_ak()
            df = retry_with_backoff(ak.stock_financial_analysis_indicator, symbol=code)
            if df is None or df.empty:
                missing.append("financial_indicators")
                return

            row = df.iloc[0]
            for ak_col, our_field in FINANCIAL_INDICATOR_FIELD_MAP.items():
                if ak_col in df.columns and (our_field not in data or data[our_field] is None):
                    v = _parse_value(row.get(ak_col))
                    if v is not None:
                        data[our_field] = v

        except Exception as exc:
            logger.warning("AKShare financial indicators 失败 %s: %s", code, exc)
            missing.append("financial_indicators")

    def _derive_computed_fields(self, data: dict) -> None:
        """计算 bvps（若无直接值）与净负债。"""
        shares = data.get("shares_outstanding")
        equity = data.get("shareholder_equity")
        if "bvps" not in data or data["bvps"] is None:
            if shares and equity and shares != 0:
                data["bvps"] = equity / shares

        total_liab = data.get("total_liabilities")
        current_assets = data.get("current_assets")
        if total_liab is not None and current_assets is not None:
            data["net_debt"] = total_liab - current_assets * 0.5
