"""T2.12/T2.13/T2.14 指标（EventObservation → 事件研究 / 推断 / 归因 / 池化 / 稳定性）。"""

from __future__ import annotations

import math

import pytest

from common.exceptions import BacktestError, MissingBacktestConfigError
from service.backtest.metrics import (
    attribution,
    block_bootstrap,
    compute_event_study,
    group_percentiles,
    insufficient_sample,
    multiple_testing_correction,
    partial_pooling,
    stability,
    window_excess,
)
from service.backtest.models import EventObservation, Verdict, WindowStats


def observation(code="000001", date="2016-06-01", kind="buy_and_hold", daily=-0.002, days=60):
    return EventObservation(
        code=code,
        event_date=date,
        condition_id="ma60_breakdown",
        benchmark_kind=kind,
        excess_returns=tuple(daily for _ in range(days)),
    )


def make_observations(count=5):
    items = []
    for index in range(count):
        for kind in ("buy_and_hold", "market_portfolio"):
            items.append(
                observation(
                    code=f"{index:06d}",
                    date=f"2016-{index + 1:02d}-01",
                    kind=kind,
                    daily=-0.002 - index * 0.0001,
                )
            )
    return items


def test_window_excess_is_cumulative_car():
    item = observation(daily=-0.01, days=60)
    assert window_excess(item, 20) == pytest.approx(-0.2)
    assert window_excess(item, 60) == pytest.approx(-0.6)


def test_event_study_windows_and_benchmarks(cfg):
    result = compute_event_study(make_observations(), cfg=cfg)
    assert set(result.windows) == {"20", "60"}
    for window in ("20", "60"):
        assert set(result.windows[window]) == {"buy_and_hold", "market_portfolio"}
        stats = result.windows[window]["buy_and_hold"]
        assert stats.n == 5
        assert stats.effective_n == math.ceil(5 / 5)
        assert set(stats.by_year) == {"2016"}
        assert stats.by_cap_tier == {}
    assert result.n_events == 5
    assert result.inference_method == "block_bootstrap"
    assert result.block_length == 5
    assert result.n_bootstrap == 200


def test_event_study_requires_block_params(tmp_path, config_factory):
    cfg = config_factory(**{"block_length": None})
    from service.backtest.models import BacktestConfig

    with pytest.raises(MissingBacktestConfigError):
        compute_event_study(
            make_observations(), cfg=BacktestConfig.from_config(cfg, base_dir=tmp_path)
        )


def test_event_study_empty_is_inconclusive_not_exception(cfg):
    """F7/T2-fix-6：空观测 → verdict=INCONCLUSIVE、windows={}、n_events=0，不抛异常。"""
    result = compute_event_study((), cfg=cfg)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.windows == {}
    assert result.n_events == 0


def test_event_study_non_empty_verdict_present(cfg):
    result = compute_event_study(make_observations(), cfg=cfg)
    assert result.verdict in (Verdict.VALID, Verdict.INVALID, Verdict.INCONCLUSIVE)


def test_insufficient_sample_flags(cfg):
    thin = [observation(days=60)]
    result = compute_event_study(thin, cfg=cfg)
    labels = insufficient_sample(result, cfg=cfg)
    assert labels
    assert any("20d" in label for label in labels)


def test_min_events_none_means_no_conclusion(cfg, tmp_path, config_factory):
    from service.backtest.models import BacktestConfig

    cfg_none = BacktestConfig.from_config(
        config_factory(**{"min_events": None}), base_dir=tmp_path
    )
    result = compute_event_study(make_observations(), cfg=cfg)
    assert insufficient_sample(result, cfg=cfg_none)


def test_block_bootstrap_reports_effective_n_and_is_deterministic():
    values = [-0.02, -0.03, -0.01, -0.02, -0.04, -0.02]
    first, effective_n = block_bootstrap(values, block_length=2, n_bootstrap=300, seed=0)
    second, _ = block_bootstrap(values, block_length=2, n_bootstrap=300, seed=0)
    assert effective_n == 3
    assert first == second
    assert first[0] <= first[1]


def test_multiple_testing_k_flips_verdict(cfg):
    k1 = multiple_testing_correction([0.01], 1, "bonferroni", cfg=cfg)[0]
    k50 = multiple_testing_correction([0.01], 50, "bonferroni", cfg=cfg)[0]
    assert k1 == pytest.approx(0.01)
    assert k50 == pytest.approx(0.5)
    assert k1 <= 0.05 < k50


def test_missing_k_cannot_be_corrected(cfg):
    with pytest.raises(BacktestError):
        multiple_testing_correction([0.01], None, "bonferroni", cfg=cfg)
    with pytest.raises(BacktestError):
        multiple_testing_correction([0.01], 0, "bonferroni", cfg=cfg)


def test_attribution_beta_from_market_benchmark():
    returns = {
        "rule": [0.01, 0.02, -0.01, 0.03, 0.0],
        "market_portfolio": [0.005, 0.01, -0.005, 0.015, 0.0],
    }
    factors = {
        "size": [0.2, -0.1, 0.0, 0.1, -0.2],
        "value": [0.1, 0.0, -0.1, 0.2, 0.05],
        "momentum": [0.3, 0.1, -0.2, 0.0, 0.1],
    }
    result = attribution(returns, factors)
    assert result.verdict is Verdict.VALID
    assert set(result.exposures) == {"beta", "size", "value", "momentum"}
    assert set(result.contributions) == {"beta", "size", "value", "momentum"}
    assert result.beta == pytest.approx(2.0, abs=1e-9)
    assert result.unexplained is not None and math.isfinite(result.unexplained)


def test_attribution_identity_sum_plus_unexplained_equals_mean_rule():
    """T2-fix-6：Σcontributions + unexplained == mean(rule)。"""
    returns = {
        "rule": [0.01, -0.02, 0.015, 0.0, -0.005],
        "market_portfolio": [0.005, -0.01, 0.007, 0.0, -0.002],
    }
    factors = {
        "size": [0.2, -0.1, 0.0, 0.1, -0.2],
        "value": [0.1, 0.0, -0.1, 0.2, 0.05],
        "momentum": [0.3, 0.1, -0.2, 0.0, 0.1],
    }
    result = attribution(returns, factors)
    mean_rule = sum(returns["rule"]) / len(returns["rule"])
    assert sum(result.contributions.values()) + result.unexplained == pytest.approx(
        mean_rule, abs=1e-12
    )


def test_attribution_requires_three_factor_keys():
    returns = {"rule": [0.01], "market_portfolio": [0.01]}
    with pytest.raises(MissingBacktestConfigError) as exc:
        attribution(returns, {"size": [1.0]})
    assert "value" in str(exc.value)


def test_attribution_without_market_portfolio_is_inconclusive():
    returns = {"rule": [0.01, 0.02]}
    factors = {"size": [1.0, 1.0], "value": [1.0, 1.0], "momentum": [1.0, 1.0]}
    result = attribution(returns, factors)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.beta is None
    assert result.unexplained is None
    assert "beta" not in result.exposures
    assert set(result.contributions) == {"size", "value", "momentum"}


def test_attribution_requires_rule_series():
    with pytest.raises(BacktestError):
        attribution(
            {"market_portfolio": [0.01]},
            {"size": [1.0], "value": [1.0], "momentum": [1.0]},
        )


def test_attribution_length_mismatch_rejected():
    with pytest.raises(BacktestError):
        attribution(
            {"rule": [0.01, 0.02], "market_portfolio": [0.01]},
            {"size": [1.0, 1.0], "value": [1.0, 1.0], "momentum": [1.0, 1.0]},
        )


def test_partial_pooling_requires_shrink():
    with pytest.raises(MissingBacktestConfigError):
        partial_pooling([1.0], 2.0, shrink=None)


def test_partial_pooling_and_percentiles():
    assert partial_pooling([1.0, 3.0], 2.0, shrink=0.5) == (1.5, 2.5)
    assert group_percentiles([10.0, 20.0, 30.0]) == (0.0, 0.5, 1.0)


def year_stats(mean, ci, n=100):
    from service.backtest.models import WindowStats

    return WindowStats(n=n, mean=mean, median=mean, std=0.02, ci=ci, effective_n=n // 5)


def test_stability_scope_note_single_year(cfg):
    from service.backtest.models import EventStudyResult

    result = EventStudyResult(
        verdict=Verdict.VALID,
        windows={
            "60": {
                "market_portfolio": WindowStats(
                    n=300,
                    mean=-0.02,
                    median=-0.02,
                    std=0.02,
                    ci=(-0.03, -0.01),
                    effective_n=60,
                    by_year={
                        "2015": year_stats(-0.05, (-0.08, -0.02)),
                        "2016": year_stats(0.0, (-0.01, 0.01)),
                    },
                    by_cap_tier={"0": year_stats(-0.02, (-0.03, -0.01))},
                )
            }
        },
        n_events=300,
        inference_method="block_bootstrap",
    )
    stability_result = stability(result, cfg=cfg)
    assert "仅在 2015 年有效" in stability_result.scope_note
    assert "市场状态口径未定" in stability_result.scope_note
    assert stability_result.by_market_state == {}


def test_compute_event_study_signature_has_no_benchmarks_param():
    import inspect

    from service.backtest import metrics

    parameters = inspect.signature(metrics.compute_event_study).parameters
    assert set(parameters) == {"observations", "cfg"}


def test_gate_machine_signature_matches_contract():
    import inspect

    from service.backtest.gates import GateStateMachine

    parameters = inspect.signature(GateStateMachine.__init__).parameters
    assert set(parameters) == {"self", "registry", "cfg"}
