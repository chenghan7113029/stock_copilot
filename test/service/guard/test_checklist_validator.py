"""ChecklistValidator 单元测试。"""

from service.guard.checklist_validator import ChecklistValidator
from service.guard.models.checklist import ChecklistSubmission


def _submission(**overrides):
    values = {
        "code": "600519",
        "action": "buy",
        "value_reasons": [
            "PE 处于历史低分位，安全边际充足，当前价格低于合理估值区间。",
            "现金流稳健，ROE 持续高于行业均值，基本面仍有韧性。",
        ],
        "tech_alignment": "价格回到 MA20 上方，成交量温和放大。",
        "sentiment_position": "市场情绪偏谨慎，尚未出现极端贪婪。",
        "stop_loss_price": 1400.0,
        "take_profit_price": 1800.0,
    }
    values.update(overrides)
    return ChecklistSubmission(**values)


def test_rejects_less_than_two_value_reasons():
    result = ChecklistValidator().validate(_submission(value_reasons=["PE 很低，值得买入。"]))

    assert result.passed is False
    assert any("价值理由不足 2 条" in reason for reason in result.rejection_reasons)


def test_rejects_availability_only_reasons():
    result = ChecklistValidator().validate(
        _submission(
            value_reasons=[
                "昨晚看新闻说公司要涨，感觉市场会追捧。",
                "群里有人说不错，传闻资金正在抱团。",
            ]
        )
    )

    assert result.passed is False
    assert any("疑似可得性单一来源" in reason for reason in result.rejection_reasons)
    assert any("有效条目不足 2 条" in reason for reason in result.rejection_reasons)


def test_accepts_grounded_complete_submission():
    result = ChecklistValidator().validate(_submission())

    assert result.passed is True
    assert result.rejection_reasons == []


def test_accumulates_missing_required_field_reasons():
    result = ChecklistValidator().validate(
        _submission(
            tech_alignment="",
            sentiment_position="",
            stop_loss_price=None,
            take_profit_price=None,
        )
    )

    assert result.passed is False
    assert result.rejection_reasons == [
        "技术面配合情况未填写",
        "情绪位置及解读未填写",
        "止损点未填写",
        "止盈点未填写",
    ]
