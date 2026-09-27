"""治理事件面确定性分析 Facade。"""

from __future__ import annotations

from datetime import date
from typing import Any

from dao.engine import Base, create_db_engine, make_session_factory
from dao.event_repo import (
    BlockTradeRepo,
    HolderTradeRepo,
    NorthboundFlowRepo,
    PledgeStatRepo,
    RepurchaseRepo,
    ShareFloatRepo,
)
from data_provider.event.provider import EventData, EventProvider, EventRepos
from service.event.models.event_result import EventResult
from service.event.rules import (
    compute_block_trade_discount,
    compute_holder_net_sell,
    compute_northbound_net_inflow,
    compute_pledge_ratio,
    compute_repurchase_active,
    compute_upcoming_unlock_30d,
)


class EventAnalyzer:
    """个股治理事件面分析入口（纯确定性，零 LLM）。"""

    def __init__(self, provider: EventProvider) -> None:
        self._provider = provider

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "EventAnalyzer":
        engine = create_db_engine(config)
        Base.metadata.create_all(engine)
        session = make_session_factory(engine)()
        repos = EventRepos(
            holder_trade=HolderTradeRepo(session),
            repurchase=RepurchaseRepo(session),
            share_float=ShareFloatRepo(session),
            pledge_stat=PledgeStatRepo(session),
            block_trade=BlockTradeRepo(session),
            northbound=NorthboundFlowRepo(session),
        )
        return cls(EventProvider.from_config(config, repos))

    def analyze(self, code: str) -> EventResult:
        """联网分析；无可用源且无缓存时返回带警告的空结果。"""
        data, warnings = self._provider.get_latest(code, offline=False)
        if data is None:
            return EventResult(
                code=code,
                warnings=["治理事件数据不可用，请先运行 sync", *warnings],
            )
        return self._build_result(code, data, warnings)

    def analyze_offline(self, code: str) -> EventResult | None:
        """严格离线分析；无本地治理事件缓存返回 None。"""
        data = self._provider.get_latest_offline(code)
        if data is None:
            return None
        return self._build_result(code, data, [])

    @staticmethod
    def _build_result(
        code: str, data: EventData, extra_warnings: list[str]
    ) -> EventResult:
        today = date.today()
        holder, holder_warnings = compute_holder_net_sell(data.holder_trade_records, today)
        repurchase_active, repurchase_warnings = compute_repurchase_active(
            data.repurchase_records, today
        )
        unlock, unlock_warnings = compute_upcoming_unlock_30d(data.share_float_records, today)
        pledge, pledge_warnings = compute_pledge_ratio(data.pledge_records)
        discount, discount_warnings = compute_block_trade_discount(
            data.block_trade_records, today
        )
        north, north_warnings = compute_northbound_net_inflow(data.northbound_records)

        reasons: list[str] = []
        if holder is not None:
            direction = "减持" if holder >= 0 else "增持"
            reasons.append(f"近 90 日股东净{direction} {abs(holder) / 10000:g} 万股")
        if repurchase_active:
            reasons.append("近 90 日存在回购（实施/完成）")
        if unlock is not None:
            reasons.append(f"未来 30 日解禁占流通盘 {unlock:g}%")
        if pledge is not None:
            reasons.append(f"质押比例 {pledge:g}%")
        if discount is not None:
            label = "折价" if discount >= 0 else "溢价"
            reasons.append(f"近 30 日大宗平均{label} {abs(discount):g}%")
        if north is not None:
            reasons.append(f"北向近 5 日净流入 {north:+.0f}（市场级）")

        warnings = [
            *holder_warnings,
            *repurchase_warnings,
            *unlock_warnings,
            *pledge_warnings,
            *discount_warnings,
            *north_warnings,
            *extra_warnings,
        ]
        return EventResult(
            code=code,
            holder_net_sell_90d=holder,
            repurchase_active=repurchase_active,
            upcoming_unlock_30d=unlock,
            pledge_ratio=pledge,
            block_trade_discount=discount,
            northbound_net_inflow_5d=north,
            reasons=reasons,
            warnings=warnings,
            data_timestamp=data.data_timestamp,
        )
