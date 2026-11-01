"""龙虎榜确定性分析 Facade。"""

from __future__ import annotations

from typing import Any

from dao.engine import Base, create_db_engine, make_session_factory
from dao.top_list_repo import (
    StockTopInstRepo,
    StockTopListRepo,
    TopListSyncMarkerRepo,
)
from data_provider.toplist.provider import TopListData, TopListProvider, TopListRepos
from service.toplist.models.top_list_result import TopListResult
from service.toplist.rules import (
    ActiveLevel,
    active_level,
    appearance_count,
    coverage_warning,
    dominant_event,
    group_by_trade_date,
    inst_net_buy,
    net_amount_level,
    reason_categories,
    WINDOW_DAYS,
)


def _fmt_yuan(value: float | None) -> str:
    """金额（元）→ 「+X.XX 亿元 / +XXX 万元」事实陈述。"""
    if value is None:
        return "N/A"
    if abs(value) >= 1e8:
        return f"{value / 1e8:+.2f} 亿元"
    return f"{value / 1e4:+.0f} 万元"


class TopListAnalyzer:
    """龙虎榜观察维度分析入口（纯确定性，零 LLM）。"""

    def __init__(self, provider: TopListProvider) -> None:
        self._provider = provider

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TopListAnalyzer":
        engine = create_db_engine(config)
        Base.metadata.create_all(engine)
        session = make_session_factory(engine)()
        repos = TopListRepos(
            top_list=StockTopListRepo(session),
            top_inst=StockTopInstRepo(session),
            marker=TopListSyncMarkerRepo(session),
        )
        return cls(TopListProvider.from_config(config, repos))

    def analyze(self, code: str) -> TopListResult:
        """联网分析：先同步最近交易日全市场榜单，再按本地缓存构建结果。"""
        _, sync_warnings = self._provider.sync_latest()
        data = self._provider.get_offline(code, WINDOW_DAYS)
        if data is None:
            return TopListResult(
                code=code,
                warnings=["龙虎榜数据不可用，请先运行 sync", *sync_warnings],
            )
        return self._build(code, data, sync_warnings)

    def analyze_offline(self, code: str) -> TopListResult | None:
        """严格离线分析；窗口内既无榜单记录也无覆盖水位时返回 None。"""
        data = self._provider.get_offline(code, WINDOW_DAYS)
        if data is None:
            return None
        return self._build(code, data, [])

    @staticmethod
    def _build(
        code: str, data: TopListData, extra_warnings: list[str]
    ) -> TopListResult:
        grouped = group_by_trade_date(data.list_records)
        count = appearance_count(data.list_records)
        level = active_level(count)
        covered = data.covered_dates

        latest_date = max(grouped) if grouped else None
        latest_events = grouped.get(latest_date, []) if latest_date else []
        dominant = dominant_event(latest_events)
        raw_net = dominant.get("net_amount") if dominant else None
        latest_net = float(raw_net) if raw_net is not None else None
        net_level = net_amount_level(latest_net)
        inst_total, inst_part = inst_net_buy(data.inst_records)
        categories = reason_categories(data.list_records)

        reasons: list[str] = []
        if count == 0:
            reasons.append(
                f"近 {WINDOW_DAYS} 日未上榜（已覆盖 {len(covered)} 个交易日）"
            )
        else:
            reasons.append(
                f"近 {WINDOW_DAYS} 日上榜 {count} 个交易日（{level.value}）"
            )
        if dominant is not None and latest_date is not None:
            reasons.append(
                f"最近上榜 {latest_date}：主导事件净买额 {_fmt_yuan(latest_net)}"
                f"（{net_level.value if net_level is not None else 'N/A'}），"
                f"当次上榜理由 {dominant.get('reason') or 'N/A'}"
            )
            if len(latest_events) > 1:
                reasons.append(f"该日共 {len(latest_events)} 条上榜理由（不可跨理由累加金额）")
        if inst_part is not None:
            reasons.append(f"机构席位净买 {_fmt_yuan(inst_total)}（{inst_part.value}）")
        if categories:
            reasons.append("上榜理由类型：" + "、".join(categories))

        warnings: list[str] = []
        coverage_hint = coverage_warning(
            covered, latest_date, window_days=WINDOW_DAYS
        )
        if coverage_hint:
            warnings.extend(coverage_hint)
        if inst_part is None and not data.inst_records:
            warnings.append("机构席位数据缺失（top_inst 未拉取或权限不足），机构维度不可用")
        warnings.extend(extra_warnings)

        return TopListResult(
            code=code,
            appearance_count=count,
            active_level=level if level is not None else ActiveLevel.NOT_LISTED,
            latest_trade_date=latest_date,
            latest_net_amount=latest_net,
            latest_net_amount_level=net_level,
            latest_event_count=len(latest_events) if latest_events else None,
            latest_reasons=[str(event.get("reason") or "") for event in latest_events],
            inst_net_buy=inst_total,
            inst_participation=inst_part,
            reason_categories=categories,
            coverage_trade_days=len(covered),
            coverage_start=covered[0] if covered else None,
            coverage_end=covered[-1] if covered else None,
            reasons=reasons,
            warnings=warnings,
            data_timestamp=data.data_timestamp,
        )
