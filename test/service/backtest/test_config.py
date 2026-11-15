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


def test_app_example_is_canonical_and_has_no_unconfirmed_numbers():
    """T2-fix-4：契约源 = config/app.example.yaml；键齐全、数值留空。"""
    path = Path(__file__).resolve().parents[3] / "config" / "app.example.yaml"
    section = yaml.safe_load(path.read_text(encoding="utf-8"))["backtest"]
    for key in (
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
        "shrink",
        "burn_scope",
        "burn_counts_as_second",
        "exception_approver",
        "k_components",
        "custom_allowed",
        "k_cost_per_window",
    ):
        assert key in section, f"config/app.example.yaml backtest 缺键 {key}"
    assert section["commission"] == {"rate": None, "min": None}
    assert section["stamp_tax"]["rate"] is None
    assert section["transfer_fee"] == {"rate": None, "included": None}
    assert section["slippage_tiers"] == []
    assert section["liquidity_cap"] == []
    assert section["max_delay_days"] is None
    assert section["min_events"] is None
    assert section["block_length"] is None
    assert section["n_bootstrap"] is None
