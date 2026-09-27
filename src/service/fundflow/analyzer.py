"""个股资金面确定性分析 Facade。"""

from __future__ import annotations

from typing import Any

from dao.engine import Base, create_db_engine, make_session_factory
from dao.fund_flow_repo import StockMarginDetailRepo, StockMoneyFlowRepo
from data_provider.fundflow.provider import FundFlowData, FundFlowProvider, FundFlowRepos
from service.fundflow.models.fund_flow_result import FundFlowResult
from service.fundflow.rules import (
    compute_main_net_inflow_5d,
    compute_margin_change_pct,
    compute_short_change_pct,
    leverage_direction,
    short_spike_reason,
)


class FundFlowAnalyzer:
    """个股资金面分析入口（纯确定性，零 LLM）。"""

    def __init__(self, provider: FundFlowProvider) -> None:
        self._provider = provider

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "FundFlowAnalyzer":
        engine = create_db_engine(config)
        Base.metadata.create_all(engine)
        session = make_session_factory(engine)()
        repos = FundFlowRepos(
            margin=StockMarginDetailRepo(session),
            moneyflow=StockMoneyFlowRepo(session),
        )
        return cls(FundFlowProvider.from_config(config, repos))

    def analyze(self, code: str) -> FundFlowResult:
        """联网分析；无可用源且无缓存时返回带警告的空结果。"""
        data, warnings = self._provider.get_latest(code, offline=False)
        if data is None:
            return FundFlowResult(
                code=code,
                warnings=["资金面数据不可用，请先运行 sync", *warnings],
            )
        return self._build_result(code, data, warnings)

    def analyze_offline(self, code: str) -> FundFlowResult | None:
        """严格离线分析；无本地缓存返回 None。"""
        data = self._provider.get_latest_offline(code)
        if data is None:
            return None
        return self._build_result(code, data, [])

    @staticmethod
    def _build_result(
        code: str, data: FundFlowData, extra_warnings: list[str]
    ) -> FundFlowResult:
        margin_change, margin_warnings = compute_margin_change_pct(data.margin_records)
        short_change, short_warnings = compute_short_change_pct(data.margin_records)
        inflow, inflow_warnings = compute_main_net_inflow_5d(data.moneyflow_records)
        direction = leverage_direction(margin_change)

        reasons: list[str] = []
        if margin_change is not None:
            reasons.append(f"两融余额近 5 个交易日变化 {margin_change:+.1f}%")
        spike = short_spike_reason(short_change)
        if spike:
            reasons.append(spike)
        elif short_change is not None:
            reasons.append(f"融券余额近 5 个交易日变化 {short_change:+.1f}%")
        if inflow is not None:
            reasons.append(f"主力资金近 5 个交易日净流入 {inflow:+.0f} 万元")

        warnings = [*margin_warnings, *short_warnings, *inflow_warnings, *extra_warnings]
        return FundFlowResult(
            code=code,
            margin_balance_change_pct=margin_change,
            short_balance_change_pct=short_change,
            main_net_inflow_5d=inflow,
            leverage_direction=direction,
            reasons=reasons,
            warnings=warnings,
            data_timestamp=data.data_timestamp,
        )
