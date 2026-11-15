"""R9 后复权（或分段复权）价格口径（TC-R09-01..03）。

锚点：spec R9；design §4.1 `AdjustMode`（无 QFQ）、`load_price_series(codes, start, end, adjust, *, loader)`
抛 `InvalidAdjustModeError`、`ExperimentRecord.adjust_mode/data_version`、§4.1 异常清单（口径非法 ≠ 数据缺失）。
"""

from __future__ import annotations

import pytest


def test_tc_r09_01_qfq_request_rejected(load, models):
    """TC-R09-01（R9 Scenario1）：请求前复权 → InvalidAdjustModeError（不是数据缺口异常）。"""
    data = load("service.backtest.data")
    calls = []

    def _loader(codes, start, end, adjust):
        calls.append(adjust)
        return {}

    with pytest.raises(models.InvalidAdjustModeError) as exc:
        data.load_price_series(["000001"], "2020-01-01", "2020-01-31", "qfq", loader=_loader)

    assert "前复权" in str(exc.value) or "qfq" in str(exc.value)
    assert calls == [], "口径非法时不得触达取数层（design §4.1 二分表）"
    assert not isinstance(exc.value, models.BacktestDataGapError)


def test_tc_r09_02_adjusted_series_has_no_fake_gap(load, models):
    """TC-R09-02（R9 Scenario2）：分红日按所用口径调整 → 持有期收益连续，不出现除权假跌。"""
    data = load("service.backtest.data")
    recorded = {}

    def _loader(codes, start, end, adjust):
        recorded["adjust"] = adjust
        # 已按口径调整后的序列：除权日不产生假跳空（持有期收益连续）
        return {"000001": tuple(
            models.PriceBar(code="000001", trade_date=day, open=close, high=close, low=close, close=close,
                            amount=1e6, limit_up_price=None, limit_down_price=None,
                            suspended=False, delisted=False, st=False)
            for day, close in (("2020-06-11", 20.0), ("2020-06-12", 19.9)))}

    series = data.load_price_series(["000001"], "2020-06-01", "2020-06-30",
                                    models.AdjustMode.SEGMENTED_HFQ, loader=_loader)
    closes = [bar.close for bar in series["000001"]]
    holding_return = closes[1] / closes[0] - 1.0

    assert recorded["adjust"] is models.AdjustMode.SEGMENTED_HFQ, "口径必须传达到取数层，不得由调用方绕过"
    assert abs(holding_return) < 0.02, "分红日不得出现除权造成的假跌"


def test_tc_r09_03_result_records_adjust_metadata(models):
    """TC-R09-03（R9 Scenario3）：结果行带复权口径 + 数据版本，且不得为 qfq。"""
    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE, metrics={},
        prereg_commit="deadbeef", data_version="snapshot-2026-01-02",
        adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)

    assert record.adjust_mode in (models.AdjustMode.HFQ, models.AdjustMode.SEGMENTED_HFQ)
    assert record.adjust_mode.value != "qfq"
    assert record.data_version
