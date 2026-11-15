"""T2.2 `BacktestConfig` 装载器（缺键即拒绝 + 落盘路径可注入）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from common.exceptions import MissingBacktestConfigError
from service.backtest.config import resolve_backtest_config
from service.backtest.models import BacktestConfig


def test_from_config_rejects_missing_cost_keys(tmp_path, config_factory):
    raw = config_factory()
    del raw["commission"]
    del raw["stamp_tax"]
    del raw["slippage_tiers"]
    with pytest.raises(MissingBacktestConfigError) as exc:
        BacktestConfig.from_config(raw, base_dir=tmp_path)
    message = str(exc.value)
    assert "commission.rate" in message
    assert "stamp_tax.sell_rate" in message
    assert "slippage_tiers" in message


def test_from_config_rejects_null_cost_values(tmp_path, config_factory):
    raw = config_factory(**{"commission.rate": None})
    with pytest.raises(MissingBacktestConfigError):
        BacktestConfig.from_config(raw, base_dir=tmp_path)


def test_results_dir_injectable(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(
        config_factory(results_dir=str(tmp_path / "out"), registry_store_path=str(tmp_path / "r.ndjson")),
        base_dir=tmp_path,
    )
    assert cfg.results_dir == tmp_path / "out"
    assert cfg.registry_store_path == tmp_path / "r.ndjson"


def test_relative_paths_resolve_against_base_dir(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    assert cfg.results_dir == tmp_path / "results"
    assert cfg.registry_store_path == tmp_path / "registry.ndjson"


def test_require_treats_none_and_empty_as_missing(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    with pytest.raises(MissingBacktestConfigError):
        cfg.require("calibration.horizon_days.not_a_key")
    empty = BacktestConfig.from_config(
        config_factory(**{"liquidity_cap": []}), base_dir=tmp_path, require_pipeline=False
    )
    with pytest.raises(MissingBacktestConfigError):
        empty.require("liquidity_cap")


def test_resolve_backtest_config_prefers_explicit_path(tmp_path, config_factory):
    explicit = tmp_path / "custom.yaml"
    explicit.write_text(
        yaml.safe_dump({"backtest": config_factory()}), encoding="utf-8"
    )
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
    assert cfg.registry_store_path == tmp_path / "registry.ndjson"


def test_resolve_backtest_config_missing_file(tmp_path):
    with pytest.raises(MissingBacktestConfigError):
        resolve_backtest_config(None, cwd=tmp_path)


def test_segments_property_reports_three_non_overlapping_ranges(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(), base_dir=tmp_path)
    from service.backtest.models import Segment

    segments = cfg.segments
    assert set(segments) == {Segment.TRAIN, Segment.VALIDATION, Segment.OUT_OF_SAMPLE}
    assert segments[Segment.TRAIN] == ("2015-01-01", "2020-12-31")
    assert segments[Segment.TRAIN][1] < segments[Segment.VALIDATION][0]
    assert segments[Segment.VALIDATION][1] < segments[Segment.OUT_OF_SAMPLE][0]


def test_segments_missing_rejected(tmp_path, config_factory):
    raw = config_factory()
    raw.pop("segments")
    cfg = BacktestConfig.from_config(raw, base_dir=tmp_path, require_pipeline=False)
    with pytest.raises(MissingBacktestConfigError):
        cfg.segments


def test_app_yaml_backtest_section_has_no_unconfirmed_numbers():
    """验收：`config/app.yaml` 的 `backtest:` 段只有键与空值（无费率/税率/滑点数值）。"""
    path = Path(__file__).resolve().parents[3] / "config" / "app.yaml"
    if not path.exists():  # pragma: no cover - 本地文件被 gitignore
        pytest.skip("config/app.yaml 不存在（gitignore 的运行配置）")
    section = yaml.safe_load(path.read_text(encoding="utf-8"))["backtest"]
    assert section["commission"] == {"rate": None, "min": None}
    assert section["stamp_tax"] == {"sell_rate": None}
    assert section["transfer_fee"] == {"included": None, "rate": None}
    assert section["slippage_tiers"] == []
    assert section["liquidity_cap"] == []
    assert section["alpha"] is None
    assert section["block_length"] is None
    assert section["n_bootstrap"] is None
    assert section["max_delay_days"] is None
