"""R12 生存偏差：退市、ST 与历史成分（TC-R12-01..04）。

锚点：spec R12；design §4.1（T2-fix-6）：
- `UniverseProvider` Protocol：`historical_constituents(as_of, scope)` / `delisted_codes(as_of)` /
  `st_status(code, as_of)`；
- `build_universe(as_of, scope, *, provider)`：合并历史成分 + 退市（退市日前计入）+ 当时 ST（按时点、不回填）；
- 数据源**不可得** → `BacktestDataGapError`（不静默剔除）；**可得但确实为空** → 空 tuple（合法，不是缺口）。
"""

from __future__ import annotations

import pytest


class SpyProvider:
    """按 design §4.1 协议实现的三方法 provider，记录每次调用参数（用于「不得用今日回看」断言）。"""

    def __init__(self, *, constituents, delisted=None, st=None):
        self._constituents = constituents
        self._delisted = delisted or {}
        self._st = st or {}
        self.calls: list[tuple] = []

    def historical_constituents(self, as_of, scope):
        self.calls.append(("historical_constituents", as_of, scope))
        value = self._constituents(as_of, scope) if callable(self._constituents) else self._constituents
        return tuple(value)

    def delisted_codes(self, as_of):
        self.calls.append(("delisted_codes", as_of))
        value = self._delisted.get(as_of, ())
        return tuple(value)

    def st_status(self, code, as_of):
        self.calls.append(("st_status", code, as_of))
        flag = self._st.get(code)
        return bool(flag(as_of)) if callable(flag) else bool(flag)


def _calls(provider, method):
    return [call for call in provider.calls if call[0] == method]


def test_tc_r12_01_delisted_stock_counted_before_delisting(load):
    """TC-R12-01（R12 Scenario1）：退市股在退市日**之前**计入，退市后不计（同一 provider 两个时点）。"""
    universe_mod = load("service.backtest.universe")
    provider = SpyProvider(
        constituents=["000001", "600001"],
        delisted={"2018-06-29": (), "2020-06-30": ("600001",)},  # 600001 于 2019 年退市
    )

    before = universe_mod.build_universe("2018-06-29", "all_a", provider=provider)
    after = universe_mod.build_universe("2020-06-30", "all_a", provider=provider)

    assert "600001" in before, "退市前必须计入（生存偏差）"
    assert "600001" not in after, "退市后不得计入"
    assert "000001" in before and "000001" in after
    assert [call[1] for call in _calls(provider, "delisted_codes")] == ["2018-06-29", "2020-06-30"], \
        "退市名单必须按当时时点取（不得用今日名单回看）"


def test_tc_r12_02_st_status_is_point_in_time(load):
    """TC-R12-02（R12 Scenario2）：ST 按 `st_status(code, as_of)` 逐票按时点判定；ST 不剔除（R12）。"""
    universe_mod = load("service.backtest.universe")
    provider = SpyProvider(
        constituents=["000001", "600002"],
        st={"600002": lambda as_of: as_of >= "2016-01-01"},  # 600002 自 2016 年 ST，2024 才摘帽
    )

    members = universe_mod.build_universe("2016-06-30", "all_a", provider=provider)

    st_calls = _calls(provider, "st_status")
    assert st_calls, "必须逐票查询 ST 状态"
    assert all(call[2] == "2016-06-30" for call in st_calls), "ST 必须按时点查询（不得用今日标签回填）"
    assert {call[1] for call in st_calls} == {"000001", "600002"}
    assert "600002" in members, "ST 只标注、不剔除（R12）"
    assert "000001" in members


def test_tc_r12_03_historical_index_constituents(load):
    """TC-R12-03（R12 Scenario3）：用 2016 年沪深 300 的**历史成分**，不用当前成分。"""
    universe_mod = load("service.backtest.universe")
    historical = ("600001", "600009")
    today = ("300750", "688981")

    def _constituents(as_of, scope):
        return historical if as_of.startswith("2016") else today

    provider = SpyProvider(constituents=_constituents)
    members = universe_mod.build_universe("2016-06-30", "csi300", provider=provider)

    assert tuple(members) == historical, "必须使用历史时点成分（R12 Scenario3）"
    assert "300750" not in members, "不得把今日成分回填到 2016"
    assert _calls(provider, "historical_constituents") == [
        ("historical_constituents", "2016-06-30", "csi300")]


def test_tc_r12_04_missing_lists_report_gap(load, models):
    """TC-R12-04（R12 Scenario4）：数据源不可得 → BacktestDataGapError（不静默剔除）；
    可得但确实为空 → 空 tuple（合法，非缺口，T2-fix-6）。"""
    universe_mod = load("service.backtest.universe")

    class _Missing:
        pass  # 三方法全缺 → 不可得

    with pytest.raises(models.BacktestDataGapError) as exc:
        universe_mod.build_universe("2019-12-31", "all_a", provider=_Missing())
    message = str(exc.value)
    assert "剔除" not in message, "缺口不得降级为「剔除」（R12 Scenario4）"
    assert "不可得" in message or "缺口" in message

    class _Raising:
        def historical_constituents(self, as_of, scope):
            raise models.BacktestDataGapError("退市名单缺失：影响 R12 生存偏差")

        def delisted_codes(self, as_of):
            raise models.BacktestDataGapError("退市名单缺失：影响 R12 生存偏差")

        def st_status(self, code, as_of):
            raise models.BacktestDataGapError("ST 名单缺失：影响 R12 生存偏差")

    with pytest.raises(models.BacktestDataGapError):
        universe_mod.build_universe("2019-12-31", "all_a", provider=_Raising())

    empty = SpyProvider(constituents=(), delisted={"2019-12-31": ()})
    assert universe_mod.build_universe("2019-12-31", "all_a", provider=empty) == (), \
        "可得但确实为空 → 空 tuple 合法，不是缺口（T2-fix-6）"
