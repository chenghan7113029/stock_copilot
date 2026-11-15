"""R15 标签准入与切点纪律 / R16 部分池化（TC-R15-01..03、TC-R16-01..02）。

锚点：spec R15/R16；design §4.1 `GroupAssignment{code, as_of, tiers, effective_range}`、
`assign_groups(codes, as_of, features, *, cfg)`（分位切点、季度重算、生效区间不回改历史）、
`partial_pooling(estimates, group_mean, *, shrink)`、§4.2 R16「拒绝绝对收益预测」。
"""

from __future__ import annotations

import dataclasses

import pytest


def _features(**overrides):
    base = {"market_cap_tier": {"000001": 2}, "dividend_tier": {"000001": 1}}
    base.update(overrides)
    return base


def test_tc_r15_01_soft_label_rejected(load, models, cfg_labels):
    """TC-R15-01（R15 Scenario1）：软标签（主题归属）请求分组 → 拒绝，且提示「软标签只登记不参与」。"""
    universe_mod = load("service.backtest.universe")

    with pytest.raises(models.BacktestError) as exc:
        universe_mod.assign_groups(["000001"], "2021-06-30",
                                   _features(theme={"000001": "新能源"}), cfg=cfg_labels)

    assert "软标签" in str(exc.value)


def test_tc_r15_02_future_grouping_rejected(load, models, cfg_labels):
    """TC-R15-02（R15 Scenario2）：用事后涨跌幅/当前成本分组 → 拒绝并说明依赖未来信息。"""
    universe_mod = load("service.backtest.universe")

    with pytest.raises(models.BacktestError) as exc:
        universe_mod.assign_groups(["000001"], "2015-06-30",
                                   _features(future_return={"000001": 0.87}), cfg=cfg_labels)
    assert "未来" in str(exc.value) or "时点" in str(exc.value)

    ok = universe_mod.assign_groups(["000001"], "2015-06-30", _features(), cfg=cfg_labels)
    assert ok["000001"].as_of == "2015-06-30"


def test_tc_r15_03_quarterly_recompute_never_rewrites_history(load, cfg_labels):
    """TC-R15-03（R15 Scenario3）：重算 2021Q2 新切点后，再查 2020-06-30 的分组必须一模一样。"""
    universe_mod = load("service.backtest.universe")
    before = universe_mod.assign_groups(["000001"], "2020-06-30", _features(), cfg=cfg_labels)
    universe_mod.assign_groups(["000001"], "2021-06-30", _features(), cfg=cfg_labels)
    after = universe_mod.assign_groups(["000001"], "2020-06-30", _features(), cfg=cfg_labels)

    assert after == before, "季度重算不得回改历史分组（R15 Scenario3）"
    assert after["000001"].effective_range[0] <= after["000001"].as_of <= after["000001"].effective_range[1]


def test_tc_r16_01_thin_sample_shrinks_to_group_mean(load):
    """TC-R16-01（R16 Scenario1）：单票 12 观测 vs 组均值 400 → 估计向组均值收缩并给出强度。"""
    metrics = load("service.backtest.metrics")
    estimates = [1.2]  # 单票原始估计
    group_mean = 0.0
    shrink = 0.8

    pooled = metrics.partial_pooling(estimates, group_mean, shrink=shrink)[0]

    assert abs(pooled - group_mean) < abs(estimates[0] - group_mean), "样本少时估计必须更靠近组均值"
    assert pooled != estimates[0]


def test_tc_r16_02_no_absolute_return_prediction_field(load, models):
    """TC-R16-02（R16 Scenario2）：输出契约只给组内分位/样本量，不含绝对收益预测字段。"""
    fields = {field.name for field in dataclasses.fields(models.GroupAssignment)}
    assert not any("predict" in name or "future_return" in name or "expected_return" in name
                   for name in fields)
