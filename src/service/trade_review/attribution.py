"""基于 FIFO 的确定性交易复盘与 Badcase 归因。"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from dao.models import ChecklistRecord, TradeRecord
from service.trade_review.models.trade_review_result import Badcase, TradeReviewResult

BADCASE_THRESHOLD = -0.08


@dataclass(frozen=True)
class _MatchedTrade:
    code: str
    quantity: int
    return_rate: float
    checklist_id: int | None
    confrontation_id: int | None = None


class TradeReviewAnalyzer:
    """仅执行本地数据的 FIFO 配对和规则归因，不调用 LLM。"""

    def analyze(
        self,
        records: Iterable[TradeRecord],
        *,
        checklists: Iterable[ChecklistRecord] = (),
        declare_stances: dict[int, str] | None = None,
    ) -> TradeReviewResult:
        matches, open_positions = self._match_fifo(records)
        returns = [match.return_rate for match in matches]
        checklist_by_id = {record.id: record for record in checklists}
        available = bool(checklist_by_id) and any(
            match.checklist_id in checklist_by_id for match in matches
        )
        badcases = (
            self._badcases(matches, checklist_by_id, declare_stances or {})
            if available
            else []
        )
        warnings: list[str] = []
        if not available:
            warnings.append("⚠ 当前无关联 Checklist 记录，无法判定 Badcase，仅展示价格维度统计。")

        return TradeReviewResult(
            win_rate=sum(value > 0 for value in returns) / len(returns) if returns else None,
            avg_return=sum(returns) / len(returns) if returns else None,
            total_trades=len(matches),
            open_positions=open_positions,
            badcase_list=badcases,
            checklist_data_available=available,
            warnings=warnings,
            badcase_summary=self._summarize_badcases(badcases, checklist_by_id),
        )

    @staticmethod
    def _match_fifo(records: Iterable[TradeRecord]) -> tuple[list[_MatchedTrade], int]:
        ordered = sorted(records, key=lambda record: (record.code, record.trade_date, record.id or 0))
        lots: dict[str, deque[tuple[TradeRecord, int]]] = defaultdict(deque)
        matches: list[_MatchedTrade] = []
        for record in ordered:
            if record.action == "BUY":
                lots[record.code].append((record, record.quantity))
                continue
            remaining = record.quantity
            while remaining and lots[record.code]:
                buy, available = lots[record.code][0]
                quantity = min(remaining, available)
                matches.append(
                    _MatchedTrade(
                        code=record.code,
                        quantity=quantity,
                        return_rate=(record.price - buy.price) / buy.price,
                        checklist_id=buy.checklist_id,
                        confrontation_id=getattr(buy, "confrontation_id", None),
                    )
                )
                remaining -= quantity
                available -= quantity
                if available:
                    lots[record.code][0] = (buy, available)
                else:
                    lots[record.code].popleft()
        return matches, sum(quantity for code_lots in lots.values() for _, quantity in code_lots)

    @staticmethod
    def _badcases(
        matches: Iterable[_MatchedTrade],
        checklists: dict[int, ChecklistRecord],
        declare_stances: dict[int, str],
    ) -> list[Badcase]:
        return [
            Badcase(
                code=match.code,
                checklist_id=match.checklist_id,
                return_rate=match.return_rate,
                quantity=match.quantity,
                confrontation_id=match.confrontation_id,
                declare_stance=(
                    declare_stances.get(match.confrontation_id)
                    if match.confrontation_id is not None
                    else None
                ),
            )
            for match in matches
            if match.checklist_id is not None
            and (checklist := checklists.get(match.checklist_id)) is not None
            and checklist.passed
            and match.return_rate < BADCASE_THRESHOLD
        ]

    @staticmethod
    def _summarize_badcases(
        badcases: list[Badcase], checklists: dict[int, ChecklistRecord]
    ) -> list[str]:
        if not badcases:
            return []
        missing_stop_loss = sum(
            checklists[badcase.checklist_id].stop_loss_price is None for badcase in badcases
        )
        return [f"{len(badcases)} 次 Badcase 中，{missing_stop_loss} 次未填写止损点"]


# 可选增强（非 V1 范围）：未来可基于 TradeReviewResult 接入叙事层，仅限生成可读摘要。
