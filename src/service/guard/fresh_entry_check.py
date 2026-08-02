"""隐藏持仓成本的无仓位视角入场检查。"""

from __future__ import annotations

from dao.position_repo import PositionRepo
from service.dual_track.analyzer import DualTrackAnalyzer
from service.dual_track.models.report import DualTrackReport
from service.guard.models.fresh_entry_view import FreshEntryView


class LocalDataMissingError(RuntimeError):
    """本地价值快照或 K 线缓存缺失。"""


class FreshEntryCheck:
    """基于严格离线双轨结果构造不暴露持仓盈亏的检查视图。"""

    def __init__(self, dual_analyzer: DualTrackAnalyzer, position_repo: PositionRepo) -> None:
        self._dual_analyzer = dual_analyzer
        self._position_repo = position_repo

    def build(self, code: str) -> FreshEntryView:
        report = self._dual_analyzer.analyze_offline(code)
        self._require_local_data(report)

        value = report.value_result
        tech = report.tech_result
        assert value is not None
        assert tech is not None
        current_price = value.current_price if value.current_price is not None else tech.current_price
        if current_price is None:
            raise LocalDataMissingError(f"未找到 {code} 的本地数据，请先运行 sync")

        has_position = self._position_repo.get_by_code(code) is not None
        reminder = (
            "以上评估已隐藏你的实际买入依据，请基于当前信息独立判断，不要被既有投入影响决策。"
            if has_position
            else "未检测到本地持仓记录，以下为标准三维分析"
        )
        fair_value = "N/A"
        if value.fair_value_range is not None:
            fair_value = (
                f"{value.fair_value_range.low:.2f} ~ {value.fair_value_range.base:.2f} "
                f"~ {value.fair_value_range.high:.2f}"
            )
        value_summary = f"价值面：评估={value.assessment}；公允价区间={fair_value}；置信度={value.confidence}"
        tech_summary = (
            f"技术面：趋势={tech.trend_status.value}；信号={tech.buy_signal.value}；"
            f"综合评分={tech.signal_score if tech.signal_score is not None else 'N/A'}"
        )
        return FreshEntryView(
            code=code,
            current_price=current_price,
            value_summary=value_summary,
            tech_summary=tech_summary,
            framing_question=f"若你今天没有 {code} 的仓位，以现价 {current_price:.2f} 买入，你还会买吗？",
            has_position=has_position,
            reminder_text=reminder,
        )

    @staticmethod
    def _require_local_data(report: DualTrackReport) -> None:
        tech = report.tech_result
        no_tech = tech is None or any("无K线缓存" in item for item in tech.warnings) or any(
            "无K线缓存" in item for item in tech.risk_factors
        )
        if report.value_result is None or no_tech:
            raise LocalDataMissingError(f"未找到 {report.code} 的本地数据，请先运行 sync")
