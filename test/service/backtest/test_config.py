"""T2.2 `BacktestConfig` 装载器（T2-fix-4 全量 schema：必须键/待 Q 键/形状/落盘注入）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from common.exceptions import MissingBacktestConfigError
from service.backtest.config import resolve_backtest_config
from service.backtest.models import (
    BacktestConfig,
    CommissionSpec,
    GateCriteria,
    Segment,
    SlippageTierSpec,
)

MUST_KEYS = ("segments", "windows", "max_delay_days", "min_events")


@pytest.mark.parametrize("key", MUST_KEYS)
def test_must_key_missing_rejected(key, tmp_path, config_factory):
    raw = config_factory()
    raw.pop(key)
    with pytest.raises(MissingBacktestConfigError) as exc:
        BacktestConfig.from_config(raw, base_dir=tmp_path)
    assert key in str(exc.value)


def test_segments_must_be_three(tmp_path, config_factory):
    with pytest.raises(MissingBacktestConfigError):
        BacktestConfig.from_config(
            config_factory(**{"segments": ["train", "validation"]}), base_dir=tmp_path
        )


def test_windows_custom_rejected_until_answered(tmp_path, config_factory):
    with pytest.raises(MissingBacktestConfigError) as exc:
        BacktestConfig.from_config(config_factory(**{"windows": [20, 60, 120]}), base_dir=tmp_path)
    assert "Q8" in str(exc.value)
    allowed = BacktestConfig.from_config(
        {
            **config_factory(),
            "windows": [20, 60, 120],
            "custom_allowed": True,
        },
        base_dir=tmp_path,
    )
    assert allowed.windows == (20, 60, 120)


def test_paths_injectable_and_relative_to_base(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    assert cfg.results_dir == tmp_path / "results"
    assert cfg.registry_store_path == tmp_path / "registry.ndjson"
    absolute = BacktestConfig.from_config(
        config_factory(results_dir=str(tmp_path / "out"), registry_store_path=str(tmp_path / "r.ndjson")),
        base_dir=tmp_path,
    )
    assert absolute.results_dir == tmp_path / "out"
    assert absolute.registry_store_path == tmp_path / "r.ndjson"


def test_cost_specs_parsed(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    assert cfg.commission == CommissionSpec(rate=2.5e-4, min=5.0)
    assert cfg.stamp_tax is not None and cfg.stamp_tax.side == "sell"
    assert cfg.transfer_fee is not None and cfg.transfer_fee.included is False
    assert cfg.slippage_tiers == (
        SlippageTierSpec(amount_lower=0.0, amount_upper=1_000_000.0, bps=10.0),
    )
    assert cfg.liquidity_cap is not None and cfg.liquidity_cap[0].adv_tier == "tier-1"


def test_unanswered_values_stay_none(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(
            **{
                "commission": {"rate": None, "min": None},
                "stamp_tax": {"side": "sell", "rate": None},
                "transfer_fee": {"rate": None, "included": None},
                "cut_basis": None,
                "tier_count": None,
                "block_length": None,
                "n_bootstrap": None,
                "shrink": None,
                "max_delay_days": None,
                "min_events": None,
            }
        ),
        base_dir=tmp_path,
    )
    assert cfg.commission is None
    assert cfg.stamp_tax is None
    assert cfg.transfer_fee is None
    assert cfg.cut_basis is None
    assert cfg.tier_count is None
    assert cfg.block_length is None
    assert cfg.shrink is None
    assert cfg.max_delay_days is None
    assert cfg.min_events is None


def test_gate_criteria_parsed(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    assert isinstance(cfg.gate_criteria, GateCriteria)
    assert cfg.gate_criteria.shadow == {"min_months": 6, "max_months": 12, "clock": "natural_month"}


def test_gate_criteria_missing_is_none(tmp_path, config_factory):
    raw = config_factory()
    raw.pop("gates")
    cfg = BacktestConfig.from_config(raw, base_dir=tmp_path)
    assert cfg.gate_criteria is None


def test_segments_field_is_three_enums(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    assert cfg.segments == (Segment.TRAIN, Segment.VALIDATION, Segment.OUT_OF_SAMPLE)


def test_resolve_backtest_config_prefers_explicit_path(tmp_path, config_factory):
    explicit = tmp_path / "custom.yaml"
    explicit.write_text(yaml.safe_dump({"backtest": config_factory()}), encoding="utf-8")
    cfg = resolve_backtest_config(explicit, cwd=tmp_path)
    assert cfg.source_path == explicit
    assert cfg.results_dir == tmp_path / "results"


def test_resolve_backtest_config_defaults_to_cwd(tmp_path, config_factory):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yaml").write_text(
        yaml.safe_dump({"backtest": config_factory()}), encoding="utf-8"
    )
    cfg = resolve_backtest_config(None, cwd=tmp_path)
    assert cfg.source_path == config_dir / "app.yaml"


def test_resolve_backtest_config_missing_file(tmp_path):
    with pytest.raises(MissingBacktestConfigError):
        resolve_backtest_config(None, cwd=tmp_path)


EXAMPLE_PATH = Path(__file__).resolve().parents[3] / "config" / "app.example.yaml"
REQUIRED_KEYS = (
    "results_dir",
    "registry_store_path",
    "segments",
    "windows",
    "max_delay_days",
    "min_events",
    "commission",
    "stamp_tax",
    "transfer_fee",
    "slippage_tiers",
    "liquidity_cap",
    "limit_pct",
    "seal_definition",
    "suspend_source",
    "cut_basis",
    "tier_count",
    "recompute_freq",
    "min_group_size",
    "gates",
    "block_length",
    "n_bootstrap",
    "burn_scope",
    "burn_counts_as_second",
    "exception_approver",
    "k_components",
    "custom_allowed",
    "k_cost_per_window",
)


def example_section() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))["backtest"]


def test_app_example_has_all_schema_keys():
    section = example_section()
    for key in REQUIRED_KEYS:
        assert key in section, f"config/app.example.yaml backtest 缺键 {key}"


def test_owner_values_landed_with_correct_units():
    """§9.3 落值：单位必须正确（0.01254% = 1.254e-4，不是 0.01254，也不是 0.05%）。"""
    section = example_section()
    rate = section["commission"]["rate"]
    assert rate == pytest.approx(1.254e-4)
    assert rate == pytest.approx(0.01254 / 100)
    assert rate != pytest.approx(0.01254), "百分比未换算成小数"
    assert rate != pytest.approx(0.0005), "佣金不是旧值 0.05%"
    assert section["commission"]["min"] == 5
    assert section["stamp_tax"] == {"side": "sell", "rate": 0.001}
    assert section["transfer_fee"] == {"rate": 0.00001, "included": True}
    tiers = section["slippage_tiers"]
    assert [(tier["amount_lower"], tier["amount_upper"], tier["bps"]) for tier in tiers] == [
        (0, 100_000_000, 20),
        (100_000_000, 500_000_000, 10),
        (500_000_000, None, 5),
    ]
    assert section["liquidity_cap"] == [{"adv_tier": "adv20", "max_participation": 0.01}]
    assert section["limit_pct"] == {
        "board": 0.10,
        "st": 0.05,
        "star_chinext": 0.20,
        "bj": 0.30,
    }
    assert section["block_length"] == 20
    assert section["n_bootstrap"] == 1000
    assert section["windows"] == [20, 60]
    assert section["custom_allowed"] is True
    assert section["k_cost_per_window"] == 1
    assert section["k_components"] == ["params", "cut_point", "window"]
    assert section["burn_scope"] == "hypothesis"
    assert section["burn_counts_as_second"] == []
    assert section["exception_approver"] == "Owner"
    assert section["cut_basis"] == "all_a_cross_section"
    assert section["tier_count"] == 5  # Owner 二次确认「5 档」（5×5=25 组）
    assert section["recompute_freq"] == "quarterly"
    assert section["min_group_size"] == 30
    assert section["limit_pct"] == {
        "board": 0.10,
        "st": 0.05,
        "star_chinext": 0.20,
        "bj": 0.30,
    }
    assert section["seal_definition"]
    assert section["suspend_source"]
    assert "shrink" not in section, "未实现键不得留成可配假象（TODO 注释）"
    assert "significance" not in section
    assert "calibration" not in section
    assert "stability" not in section
    assert section["gates"]["shadow"]["min_months"] == 3
    assert section["gates"]["shadow"]["max_months"] == 12
    assert section["gates"]["shadow"]["clock"] == "trading_day"


def test_example_config_loads_into_backtest_config(tmp_path):
    cfg = BacktestConfig.from_config(example_section(), base_dir=tmp_path)
    assert cfg.commission is not None
    assert cfg.commission.rate == pytest.approx(1.254e-4)
    assert cfg.stamp_tax is not None and cfg.stamp_tax.rate == 0.001
    assert cfg.transfer_fee is not None and cfg.transfer_fee.included is True
    assert cfg.slippage_tiers is not None
    assert cfg.slippage_tiers[-1].amount_upper is None
    assert cfg.liquidity_cap is not None and cfg.liquidity_cap[0].adv_tier == "adv20"
    assert cfg.shrink is None  # TODO 未实现 → 键已注释
    assert cfg.k_components == ("params", "cut_point", "window")
    assert cfg.gate_criteria is not None
    assert cfg.gate_criteria.shadow and cfg.gate_criteria.shadow["min_months"] == 3


def test_unimplemented_keys_are_commented_with_todo():
    """未实现键必须注释为 TODO（不留可配假象），并指向 IMPROVEMENTS。"""
    text = EXAMPLE_PATH.read_text(encoding="utf-8")
    for key in ("shrink", "significance", "calibration", "stability"):
        active_lines = [
            line
            for line in text.splitlines()
            if line.strip().startswith(f"{key}:")
        ]
        assert active_lines == [], f"{key} 不应作为可配键出现"
        assert "TODO 未实现" in text
        assert "docs/improvements/IMPROVEMENTS.md" in text


def test_example_config_missing_must_key_still_rejects(tmp_path):
    section = example_section()
    section.pop("segments")
    with pytest.raises(MissingBacktestConfigError):
        BacktestConfig.from_config(section, base_dir=tmp_path)


def test_example_config_missing_cost_rejected_at_consumption(tmp_path):
    """Q4 成本键缺失：配置可装载（待 Q 形状），但消费处（撮合/校准）必须拒绝。"""
    from service.backtest.broker import CostCalculator

    section = example_section()
    section.pop("commission")
    cfg = BacktestConfig.from_config(section, base_dir=tmp_path)
    assert cfg.commission is None
    with pytest.raises(MissingBacktestConfigError):
        CostCalculator.from_config(cfg)
