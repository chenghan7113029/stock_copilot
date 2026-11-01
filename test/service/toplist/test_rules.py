"""龙虎榜确定性规则单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

from service.toplist.models.top_list_result import (
    ActiveLevel,
    InstParticipation,
    NetAmountLevel,
)
from service.toplist.rules import (
    ACTIVE_MIN_APPEARANCES,
    LARGE_NET_BUY_10K,
    active_level,
    appearance_count,
    classify_reason,
    coverage_warning,
    dominant_event,
    inst_net_buy,
    net_amount_level,
    reason_categories,
)


def _event(trade_date: str, reason: str, l_amount: float, net_amount: float | None) -> dict:
    return {
        "trade_date": trade_date,
        "reason": reason,
        "l_amount": l_amount,
        "net_amount": net_amount,
    }


def test_appearance_count_dedupes_same_day_multiple_reasons() -> None:
    records = [
        _event("2026-10-08", "日振幅值达到15%的前5只证券", 5.5e8, -8.5e7),
        _event("2026-10-08", "日换手率达到20%的前5只证券", 5.5e8, -8.5e7),
        _event("2026-09-30", "日涨幅达到15%的前5只证券", 1.3e8, 7.6e7),
    ]
    assert appearance_count(records) == 2


def test_active_level_threshold_boundaries() -> None:
    assert active_level(0) is ActiveLevel.NOT_LISTED
    assert active_level(1) is ActiveLevel.OCCASIONAL
    assert active_level(ACTIVE_MIN_APPEARANCES - 1) is ActiveLevel.OCCASIONAL
    assert active_level(ACTIVE_MIN_APPEARANCES) is ActiveLevel.ACTIVE


def test_net_amount_level_boundaries() -> None:
    threshold_yuan = LARGE_NET_BUY_10K * 1e4
    assert net_amount_level(threshold_yuan) is NetAmountLevel.LARGE_NET_BUY
    assert net_amount_level(threshold_yuan - 1.0) is NetAmountLevel.NEUTRAL
    assert net_amount_level(-threshold_yuan) is NetAmountLevel.LARGE_NET_SELL
    assert net_amount_level(-threshold_yuan + 1.0) is NetAmountLevel.NEUTRAL
    assert net_amount_level(None) is None


def test_dominant_event_picks_largest_l_amount_and_is_deterministic() -> None:
    small = _event("2026-10-08", "日涨幅达到15%的前5只证券", 1.3e8, 7.6e7)
    large = _event("2026-10-08", "连续三个交易日内，涨幅偏离值累计达到30%的证券", 1.8e8, 6.5e7)
    assert dominant_event([small, large]) is large
    # 并列时按 reason 稳定选择（多次调用结果一致）
    tie_a = _event("2026-10-08", "日换手率达到20%的前5只证券", 5.0e8, 1.0)
    tie_b = _event("2026-10-08", "日振幅值达到15%的前5只证券", 5.0e8, 2.0)
    first = dominant_event([tie_a, tie_b])
    second = dominant_event([tie_b, tie_a])
    assert first is second
    assert dominant_event([]) is None


def test_reason_classification_and_ordering() -> None:
    assert classify_reason("日涨幅偏离值达到7%的前5只证券") == "涨幅偏离"
    assert classify_reason("日跌幅偏离值达到7%的前5只证券") == "跌幅偏离"
    assert classify_reason("日换手率达到20%的前5只证券") == "换手率"
    assert classify_reason("日振幅值达到15%的前5只证券") == "振幅"
    assert classify_reason("连续三个交易日内，涨幅偏离值累计达到20%的证券") == "连续三日累计"
    assert classify_reason("其他异常波动") == "其他"
    assert classify_reason(None) == "其他"

    records = [
        _event("2026-10-08", "日换手率达到20%的前5只证券", 1.0, 1.0),
        _event("2026-10-08", "日涨幅偏离值达到7%的前5只证券", 1.0, 1.0),
        _event("2026-10-08", "日涨幅偏离值达到7%的前5只证券", 1.0, 1.0),
    ]
    assert reason_categories(records) == ["涨幅偏离", "换手率"]


def test_inst_net_buy_dedupes_cross_side_duplicate_seat() -> None:
    """同一席位同时出现在买入/卖出前 5（金额相同）只计一次。"""
    records = [
        {"trade_date": "2026-10-08", "exalter": "机构专用", "buy": 1.5e7, "sell": 4.1e7,
         "net_buy": -2.6e7, "reason": "日跌幅偏离值达到7%的前5只证券"},
        {"trade_date": "2026-10-08", "exalter": "机构专用", "buy": 1.5e7, "sell": 4.1e7,
         "net_buy": -2.6e7, "reason": "日跌幅偏离值达到7%的前5只证券"},
        {"trade_date": "2026-10-08", "exalter": "机构专用", "buy": 3.6e7, "sell": 2.2e7,
         "net_buy": 1.4e7, "reason": "日跌幅偏离值达到7%的前5只证券"},
    ]
    total, participation = inst_net_buy(records)
    assert total == -1.2e7
    assert participation is InstParticipation.INST_SELL


def test_inst_net_buy_ignores_non_institution_seats() -> None:
    records = [
        {"trade_date": "2026-10-08", "exalter": "深股通专用", "buy": 6.3e7, "sell": 6.5e7,
         "net_buy": -1.6e6, "reason": "日跌幅偏离值达到7%的前5只证券"},
        {"trade_date": "2026-10-08", "exalter": "中信建投证券股份有限公司北四环东路证券营业部",
         "buy": 0.0, "sell": 5.0e7, "net_buy": -5.0e7, "reason": "日跌幅偏离值达到7%的前5只证券"},
    ]
    assert inst_net_buy(records) == (None, None)


def test_inst_net_buy_positive_sign() -> None:
    records = [
        {"trade_date": "2026-10-08", "exalter": "机构专用", "buy": 1.2e8, "sell": 4.0e7,
         "net_buy": 8.0e7, "reason": "日涨幅偏离值达到7%的前5只证券"},
    ]
    total, participation = inst_net_buy(records)
    assert total == 8.0e7
    assert participation is InstParticipation.INST_BUY


def test_coverage_warning_none_when_window_covered() -> None:
    today = date.today()
    covered = sorted(
        [
            (today - timedelta(days=90)).isoformat(),
            (today - timedelta(days=3)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
        ]
    )
    assert coverage_warning(covered, covered[-1]) is None


def test_coverage_warning_when_window_not_covered() -> None:
    today = date.today()
    covered = [(today - timedelta(days=offset)).isoformat() for offset in (1, 2)]
    hint = coverage_warning(sorted(covered), covered[0])
    assert hint is not None
    assert any("覆盖 2 个交易日" in item for item in hint)


def test_coverage_warning_when_empty() -> None:
    hint = coverage_warning([], None)
    assert hint is not None
    assert any("覆盖为空" in item for item in hint)
