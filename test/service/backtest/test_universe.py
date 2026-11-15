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
    # tier_count=5（生产口径）时 3 只标的按分位落 0/1/3 档
    assert result["a"].tiers["market_cap_tier"] == 0
    assert result["c"].tiers["market_cap_tier"] == 3
    assert result["a"].effective_range == ("2020-04-01", "2020-06-30")


def test_recompute_does_not_rewrite_history(cfg):
    features = {
        "a": {"market_cap": 1.0},
        "b": {"market_cap": 2.0},
        "c": {"market_cap": 3.0},
    }
    first = assign_groups(list(features), "2020-06-30", features, cfg=cfg)
    assign_groups(list(features), "2021-06-30", features, cfg=cfg)
    assert first["c"].tiers["market_cap_tier"] == 3
    assert first["c"].effective_range == ("2020-04-01", "2020-06-30")
    assert quarter_range("2021-06-30") == ("2021-04-01", "2021-06-30")


class SpyProvider:
    """T2-fix-6 `UniverseProvider` 协议夹具（记录调用，便于断言时点/scope）。"""

    def __init__(self, constituents=("000001", "000002"), delisted=(), st=(), *, calls=None):
        self._constituents = tuple(constituents)
        self._delisted = tuple(delisted)
        self._st = set(st)
        self.calls = calls if calls is not None else []

    def historical_constituents(self, as_of, scope):
        self.calls.append(("constituents", as_of, scope))
        return self._constituents

    def delisted_codes(self, as_of):
        self.calls.append(("delisted", as_of))
        return self._delisted

    def st_status(self, code, as_of):
        self.calls.append(("st", code, as_of))
        return code in self._st


def test_build_universe_excludes_delisted_and_asks_point_in_time_st():
    calls = []
    provider = SpyProvider(
        constituents=("000001", "000002", "000003"),
        delisted=("000002",),
        st=("000003",),
        calls=calls,
    )
    members = build_universe("2019-07-01", "all_a", provider=provider)
    assert members == ("000001", "000003")  # 退市股剔除；当时 ST 股仍计入（R12）
    assert ("constituents", "2019-07-01", "all_a") in calls
    assert ("st", "000003", "2019-07-01") in calls, "ST 必须按时点查询，不得回填"


def test_build_universe_keeps_code_before_delisting():
    before = SpyProvider(constituents=("000001", "600001"), delisted=())
    assert "600001" in build_universe("2018-06-29", "all_a", provider=before)
    after = SpyProvider(constituents=("000001", "600001"), delisted=("600001",))
    assert "600001" not in build_universe("2019-07-01", "all_a", provider=after)


def test_build_universe_empty_constituents_is_legal():
    """T2-fix-6：名单可得但确实为空 → 空 tuple（不是缺口）。"""
    provider = SpyProvider(constituents=())
    assert build_universe("2020-01-02", "csi300", provider=provider) == ()


def test_build_universe_provider_unavailable_reports_gap():
    class UnavailableProvider:
        def historical_constituents(self, as_of, scope):
            raise BacktestDataGapError("历史成分不可得")

        def delisted_codes(self, as_of):
            raise BacktestDataGapError("退市名单不可得")

        def st_status(self, code, as_of):
            raise BacktestDataGapError("ST 状态不可得")

    with pytest.raises(BacktestDataGapError):
        build_universe("2020-01-02", "all_a", provider=UnavailableProvider())


def test_build_universe_missing_protocol_methods_reports_gap():
    with pytest.raises(BacktestDataGapError) as exc:
        build_universe("2020-01-02", "all_a", provider=object())
    assert "historical_constituents" in str(exc.value)


def test_build_universe_delisted_unavailable_reports_gap():
    class HalfProvider(SpyProvider):
        def delisted_codes(self, as_of):
            raise BacktestDataGapError("退市名单缺失；影响范围：R12")

    with pytest.raises(BacktestDataGapError) as exc:
        build_universe("2020-01-02", "all_a", provider=HalfProvider())
    assert "R12" in str(exc.value)


def test_build_universe_st_lookup_required_for_every_included_code():
    class NoSt(SpyProvider):
        def st_status(self, code, as_of):
            raise BacktestDataGapError(f"{code} ST 不可得")

    with pytest.raises(BacktestDataGapError):
        build_universe("2020-01-02", "all_a", provider=NoSt(constituents=("000001",)))


def test_five_tiers_two_dimensions_makes_25_groups(cfg):
    """Q6 落值：tier_count=5（Owner 二次确认「5 档」）；5×5=25 组。"""
    codes = [f"{index:06d}" for index in range(25)]
    features = {
        code: {"market_cap": float(index), "dividend_yield": float(index % 5)}
        for index, code in enumerate(codes)
    }
    result = assign_groups(codes, "2021-06-30", features, cfg=cfg)
    tier_keys = {key for assignment in result.values() for key in assignment.tiers}
    assert tier_keys == {"market_cap_tier", "dividend_tier"}
    assert all(0 <= tier <= 4 for assignment in result.values() for tier in assignment.tiers.values())
    combinations = {
        (assignment.tiers["market_cap_tier"], assignment.tiers["dividend_tier"])
        for assignment in result.values()
    }
    assert len(combinations) == 25  # 5 档 × 5 档
