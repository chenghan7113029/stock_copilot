"""R6 统计推断按有效样本（TC-R06-01..02）。

锚点：spec R6；design §4.1 `metrics.block_bootstrap(excess, *, block_length, n_bootstrap, seed)`
返回「CI + 有效样本量（时间块数）」、`EventStudyResult.effective_n`、§4.2 R6「禁 iid t 检验下结论」。
"""

from __future__ import annotations

import pytest


def _excess(load, series):
    """把 30×100 的共因子矩阵压平成事件超额序列（QA 侧准备数据，不测被测统计量）。"""
    np = pytest.importorskip("numpy")
    stacked = np.stack([series[key] for key in sorted(series)], axis=0)
    return stacked.mean(axis=0)


def test_tc_r06_01_block_bootstrap_reports_effective_sample(load, common_factor_series, cfg_inference):
    """TC-R06-01（R6 Scenario1）：名义 3000 → 有效样本只能是时间块数（< 名义），CI 由块重采样给出。"""
    metrics = load("service.backtest.metrics")
    excess = _excess(load, common_factor_series)
    ci, effective_n = metrics.block_bootstrap(
        excess, block_length=cfg_inference["block_length"],
        n_bootstrap=cfg_inference["n_bootstrap"], seed=cfg_inference["seed"])

    assert isinstance(ci, tuple) and len(ci) == 2
    assert ci[0] <= ci[1]
    assert isinstance(effective_n, int)
    assert effective_n <= cfg_inference["n_time_blocks"], "有效样本 = 时间块数（design §4.1）"
    assert effective_n < len(excess), "有效样本必须远小于名义样本（否则仍在用 iid）"


def test_tc_r06_02_default_inference_requires_block_sampling(load, common_factor_series):
    """TC-R06-02（R6 Scenario2）：不指定块长/重采样次数无法调用 → 默认不可能静默用 iid。"""
    metrics = load("service.backtest.metrics")
    excess = _excess(load, common_factor_series)

    with pytest.raises(TypeError):
        metrics.block_bootstrap(excess)  # 块长与重采样次数是必填关键字参数（design §4.1 签名）
