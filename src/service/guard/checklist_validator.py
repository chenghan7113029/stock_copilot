"""结构化决策清单的确定性校验。"""

from __future__ import annotations

from service.guard.models.checklist import ChecklistSubmission, ChecklistValidationResult

_AVAILABILITY_KEYWORDS = (
    "新闻",
    "消息",
    "听说",
    "传闻",
    "网上说",
    "群里",
    "大 V",
    "涨停",
    "抱团",
)
_GROUNDED_KEYWORDS = (
    "估值",
    "PE",
    "PB",
    "安全边际",
    "低估",
    "护城河",
    "现金流",
    "ROE",
    "基本面",
    "财报",
    "DCF",
    "分位",
)
_MIN_REASON_CHARS = 15


class ChecklistValidator:
    """执行不可由 LLM 代替的决策清单硬规则。"""

    def validate(self, submission: ChecklistSubmission) -> ChecklistValidationResult:
        """返回全部拒绝原因，不因首个错误而短路。"""
        rejection_reasons: list[str] = []
        reasons = [reason.strip() for reason in submission.value_reasons if reason and reason.strip()]

        if len(reasons) < 2:
            rejection_reasons.append("价值理由不足 2 条")

        valid_reason_count = 0
        for index, reason in enumerate(reasons, 1):
            if len(reason) < _MIN_REASON_CHARS:
                rejection_reasons.append(f"第 {index} 条价值理由过短，疑似非实质性理由")
                continue
            if self._is_availability_only(reason):
                rejection_reasons.append(f"第 {index} 条价值理由疑似可得性单一来源")
                continue
            valid_reason_count += 1

        if valid_reason_count < 2:
            rejection_reasons.append("价值理由中有效条目不足 2 条（存在过短或疑似新闻/传闻式单一来源理由）")

        if not (submission.tech_alignment or "").strip():
            rejection_reasons.append("技术面配合情况未填写")
        if not (submission.sentiment_position or "").strip():
            rejection_reasons.append("情绪位置及解读未填写")
        if submission.stop_loss_price is None:
            rejection_reasons.append("止损点未填写")
        if submission.take_profit_price is None:
            rejection_reasons.append("止盈点未填写")

        return ChecklistValidationResult(
            passed=not rejection_reasons,
            rejection_reasons=rejection_reasons,
        )

    @staticmethod
    def _is_availability_only(reason: str) -> bool:
        return any(keyword in reason for keyword in _AVAILABILITY_KEYWORDS) and not any(
            keyword in reason for keyword in _GROUNDED_KEYWORDS
        )
