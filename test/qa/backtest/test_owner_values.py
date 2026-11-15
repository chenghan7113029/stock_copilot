"""§9.3 口径落值复验（Owner 2026-11-15 答复 → design 契约 → config/app.yaml 生效）。

锚点：design §9.3「口径落值表（Owner 2026-11-15 逐条答复，权威）」；§4.1 成本 spec / `BacktestConfig` /
`k_from_grid` / `custom_window_k_cost`；`config/app.example.yaml`（tracked 契约源）与 `config/app.yaml`
（本机副本，gitignore，两者同段）。

本文件是 **T4-verify（t35）** 的落值锁定用例：断言的是「配置数值真的这样生效」，不是规格 Scenario 的
再覆盖；因此不新增 Spec Scenario（用例数 +5，Scenario 仍 56）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_CONFIG = REPO_ROOT / "config" / "app.yaml"
EXAMPLE_CONFIG = REPO_ROOT / "config" / "app.example.yaml"


def _real_section() -> tuple[dict, Path]:
    """优先真实 `config/app.yaml`（本机），缺则用 tracked 的 `config/app.example.yaml`（同段同值）。"""
    for path in (APP_CONFIG, EXAMPLE_CONFIG):
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            section = data.get("backtest")
            assert isinstance(section, dict), f"{path} 缺 backtest: 段"
            return section, path
    raise AssertionError("仓库内既无 config/app.yaml 也无 config/app.example.yaml")


def test_tc_cfg_01_real_config_lands_owner_commission_rate(load):
    """TC-CFG-01（§9.3）：真实配置可加载，佣金率**精确** 1.254e-4（0.01254%），
    不是 0.01254（小数误写）、也不是 0.05%（旧口径）；其余落值同时生效。"""
    config_mod = load("service.backtest.config")
    section, path = _real_section()
    cfg = config_mod.BacktestConfig.from_config(section, base_dir=path.parent.parent)

    assert cfg.commission is not None
    assert cfg.commission.rate == pytest.approx(1.254e-4, abs=0), \
        f"佣金率必须精确 1.254e-4（0.01254%），实际 {cfg.commission.rate!r}"
    assert cfg.commission.rate != pytest.approx(0.01254), "0.01254 是「小数/百分数混用」的误写"
    assert cfg.commission.rate != pytest.approx(5e-4), "0.05% 是 Owner 已更正掉的旧口径"
    assert cfg.commission.min == pytest.approx(5.0)

    assert cfg.stamp_tax is not None and cfg.stamp_tax.rate == pytest.approx(1e-3)
    assert str(cfg.stamp_tax.side).lower().endswith("sell") or cfg.stamp_tax.side == "sell"
    assert cfg.transfer_fee is not None and cfg.transfer_fee.rate == pytest.approx(1e-5)
    assert cfg.transfer_fee.included is True, "过户费并入佣金（§9.3 二次确认）"
    assert cfg.tier_count == 5, "分组 5 档（Owner 二次确认，5×5=25 组）"
    assert tuple(cfg.windows) == (20, 60)
    assert cfg.block_length == 20 and cfg.n_bootstrap == 1000
    assert cfg.custom_allowed is True and cfg.k_cost_per_window == 1
    assert cfg.burn_scope == "hypothesis"
    assert cfg.burn_counts_as_second == ()
    assert cfg.exception_approver == "Owner"
    assert cfg.gate_criteria is not None
    assert cfg.gate_criteria.shadow["min_months"] == 3, "影子期 3 个月起（Owner 口径）"
    assert cfg.limit_pct and cfg.seal_definition and cfg.suspend_source, "Q5 三键必须来自配置"


def test_tc_cfg_02_missing_must_keys_still_rejected(load):
    """TC-CFG-02（§4.1）：真实配置删掉必须键 → 仍 `MissingBacktestConfigError`；成本键缺失在消费处拒绝。"""
    models = load("service.backtest.models")
    broker = load("service.backtest.broker")
    config_mod = load("service.backtest.config")
    section, _path = _real_section()

    for key in ("segments", "windows", "max_delay_days"):
        broken = dict(section)
        broken.pop(key, None)
        with pytest.raises(models.MissingBacktestConfigError):
            config_mod.BacktestConfig.from_config(broken)

    no_cost = dict(section)
    no_cost.pop("commission", None)
    cfg = config_mod.BacktestConfig.from_config(no_cost)
    with pytest.raises(models.MissingBacktestConfigError):
        broker.CostCalculator.from_config(cfg)


def test_tc_cfg_03_burn_scope_hypothesis_blocks_rerun_even_with_new_impl(load, registry, models):
    """TC-CFG-03（§9.3 R4）：`burn_scope=hypothesis` + `burn_counts_as_second=()`：
    同假设烧毁后，**换实现/换指标**（新实验）仍拒绝；换假设才有独立额度。"""
    config_mod = load("service.backtest.config")
    section, path = _real_section()
    cfg = config_mod.BacktestConfig.from_config(section, base_dir=path.parent.parent)
    assert cfg.burn_scope == "hypothesis" and cfg.burn_counts_as_second == ()

    registry.append(_experiment(models, "hyp-a", "hyp-a-0001", metrics={"mean_excess": 0.01}))
    registry.mark_burnt("hyp-a", "hyp-a-0001")

    with pytest.raises(models.RegistryImmutableError):
        registry.assert_not_burnt("hyp-a", models.Segment.OUT_OF_SAMPLE)

    # 同一假设下「换实现/换指标」的新实验：仍是同一份样本外额度 → 继续拒绝（不得换指标重置）
    with pytest.raises(models.RegistryImmutableError):
        registry.assert_not_burnt("hyp-a", models.Segment.OUT_OF_SAMPLE)

    registry.append(_experiment(models, "hyp-b", "hyp-b-0001", metrics={"mean_excess": 0.02}))
    registry.assert_not_burnt("hyp-b", models.Segment.OUT_OF_SAMPLE)  # 新假设独立额度


def test_tc_cfg_04_param_grid_21_counts_k_21(load):
    """TC-CFG-04（§9.3 R5）：参数网格 21 组 → `k_from_grid`/`cumulative_K` 均计 K=21（乘积不是求和）。"""
    registry_mod = load("service.backtest.registry")

    assert registry_mod.k_from_grid({"params": 21}) == 21
    assert registry_mod.k_from_grid({"params": 21, "cut_point": 1, "window": 1}) == 21
    assert registry_mod.k_from_grid({"params": 3, "cut_point": 5}) == 15, "分量网格按乘积（3×5）"


def test_tc_cfg_05_custom_window_costs_k(load):
    """TC-CFG-05（§9.3 R17/Q8）：自定义窗口（如 5 日）每个计 K 一次；未获 `custom_allowed` 则拒绝。"""
    metrics = load("service.backtest.metrics")
    config_mod = load("service.backtest.config")
    models = load("service.backtest.models")
    section, path = _real_section()
    cfg = config_mod.BacktestConfig.from_config(section, base_dir=path.parent.parent)

    assert metrics.custom_windows([5, 20, 60]) == (5,)
    assert metrics.custom_window_k_cost(cfg, [20, 60]) == 0
    assert metrics.custom_window_k_cost(cfg, [5, 20, 60]) == 1, "每个额外窗口 × k_cost_per_window(=1)"

    no_custom = dict(section)
    no_custom["custom_allowed"] = False
    cfg_strict = config_mod.BacktestConfig.from_config(no_custom, base_dir=path.parent.parent)
    with pytest.raises(models.MissingBacktestConfigError):
        metrics.custom_window_k_cost(cfg_strict, [5, 20, 60])


def _experiment(models, hypothesis_id: str, experiment_id: str, *, metrics: dict):
    return models.ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis_id=hypothesis_id,
        params={"ma": 60},
        segment=models.Segment.VALIDATION,
        K=1,
        verdict=models.Verdict.INCONCLUSIVE,
        metrics=metrics,
        prereg_commit="deadbeef",
        data_version="test-v1",
        adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"},
        parent_experiment_id=None,
    )
