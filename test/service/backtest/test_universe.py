"""T2.8 分组切点与成分 `universe.py`（季度重算，不回改历史）。"""

from __future__ import annotations

import pytest

from common.exceptions import BacktestDataGapError, MissingBacktestConfigError
from service.backtest.models import BacktestConfig
from service.backtest.universe import assign_groups, build_universe, quarter_range


def test_soft_label_rejected(cfg):
    with pytest.raises(Exception) as exc:
        assign_groups(
            ["000001"],
            "2020-06-30",
            {"000001": {"theme": 1.0}},
            cfg=cfg,
        )
    assert "软标签" in str(exc.value)


def test_result_label_rejected(cfg):
    with pytest.raises(Exception) as exc:
        assign_groups(
            ["000001"],
            "2020-06-30",
            {"000001": {"future_return": 0.2}},
            cfg=cfg,
        )
    assert "结果标签" in str(exc.value)


def test_cut_basis_missing_rejected(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(**{"cut_basis": None}), base_dir=tmp_path)
    with pytest.raises(MissingBacktestConfigError):
        assign_groups(["000001"], "2020-06-30", {"000001": {"market_cap": 1.0}}, cfg=cfg)


def test_non_quarterly_recompute_rejected(tmp_path, config_factory):
    cfg = BacktestConfig.from_config(config_factory(**{"recompute_freq": "monthly"}), base_dir=tmp_path)
    with pytest.raises(Exception) as exc:
        assign_groups(["000001"], "2020-06-30", {"000001": {"market_cap": 1.0}}, cfg=cfg)
    assert "季度" in str(exc.value)


def test_quarterly_tiers_and_effective_range(cfg):
    features = {
        "a": {"market_cap": 1.0},
        "b": {"market_cap": 2.0},
        "c": {"market_cap": 3.0},
    }
    result = assign_groups(list(features), "2020-06-30", features, cfg=cfg)
    assert result["a"].tiers["market_cap_tier"] == 0
    assert result["c"].tiers["market_cap_tier"] == 2
    assert result["a"].effective_range == ("2020-04-01", "2020-06-30")


def test_recompute_does_not_rewrite_history(cfg):
    features = {
        "a": {"market_cap": 1.0},
        "b": {"market_cap": 2.0},
        "c": {"market_cap": 3.0},
    }
    first = assign_groups(list(features), "2020-06-30", features, cfg=cfg)
    assign_groups(list(features), "2021-06-30", features, cfg=cfg)
    assert first["c"].tiers["market_cap_tier"] == 2
    assert first["c"].effective_range == ("2020-04-01", "2020-06-30")
    assert quarter_range("2021-06-30") == ("2021-04-01", "2021-06-30")


def test_build_universe_includes_delisted_before_delist_date():
    class Provider:
        def load_members(self, as_of, spec):
            return ("000001", "000002", "000003")

        def load_flags(self, codes, as_of):
            return {
                "000001": {"delisted": False, "delist_date": None, "st": False},
                "000002": {"delisted": True, "delist_date": "2019-06-30", "st": True},
                "000003": {"delisted": True, "delist_date": "2021-06-30", "st": False},
            }

    before = build_universe("2019-05-31", {"kind": "all_a"}, provider=Provider())
    assert "000002" in before  # 退市日前计入，且当时 ST 保留
    after = build_universe("2019-07-01", {"kind": "all_a"}, provider=Provider())
    assert "000002" not in after  # 退市日之后不计入
    assert "000003" in after  # 尚未退市


def test_build_universe_missing_flags_reports_gap():
    class Provider:
        def load_members(self, as_of, spec):
            return ("000001",)

        def load_flags(self, codes, as_of):
            return {}

    with pytest.raises(BacktestDataGapError):
        build_universe("2020-01-02", {"kind": "all_a"}, provider=Provider())


def test_build_universe_without_source_reports_gap():
    class Provider:
        pass

    with pytest.raises(BacktestDataGapError):
        build_universe("2020-01-02", {"kind": "all_a"}, provider=Provider())
