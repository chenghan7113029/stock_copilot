"""R17 事件研究为 MVP 主交付（TC-R17-01..04）。

锚点：spec R17；design §4.1（T2-fix-4 后）`EventObservation`（逐日超额载体，长度 = max(window)）、
`load_event_observations(signals, benchmarks, *, loader, cfg)`、`compute_event_study(observations, *, cfg)`、
`min_events`（必须键：事件数下限）、`EventStudyResult.windows[window][benchmark_kind]`、§4.2 R17
「事件数不足 → 样本不足」「允许结论为无信号」。
"""

from __future__ import annotations

import json

import pytest


def test_tc_r17_01_twenty_and_sixty_day_windows(load, make_observations, cfg_event):
    """TC-R17-01（R17 Scenario1）：输出 20/60 日两窗口 × 双基准的完整 WindowStats。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(), cfg=cfg_event)

    assert set(result.windows) >= {"20", "60"}
    assert result.n_events > 0
    assert result.inference_method == "block_bootstrap"
    assert result.block_length == cfg_event.block_length
    assert result.n_bootstrap == cfg_event.n_bootstrap
    for window in ("20", "60"):
        for stats in result.windows[window].values():
            assert stats.n >= 0
            assert stats.median is not None and stats.std is not None
            assert stats.ci[0] <= stats.ci[1]


def test_tc_r17_02_insufficient_events_marks_insufficient_sample(load, models, make_observations, cfg_event):
    """TC-R17-02（R17 Scenario2）：有效事件数低于 `min_events` → 标「样本不足」，不给有效/无效判定。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(count=3), cfg=cfg_event)

    thin = result.windows["20"]["buy_and_hold"]
    assert thin.n < cfg_event.min_events, "夹具前置：事件数必须低于配置下限 min_events"
    assert result.n_events == thin.n
    # T2-fix-6：`EventStudyResult.verdict` 是契约字段；全样本不足 → INCONCLUSIVE（不得判有效）
    assert result.verdict is models.Verdict.INCONCLUSIVE, "事件数不足 → INCONCLUSIVE（R17 Scenario2）"


def test_tc_r17_03_no_signal_is_a_legal_conclusion(load, models, make_observations, cfg_event):
    """TC-R17-03（R17 Scenario3）：CI 含 0 且校正后不显著 → 结论「无信号」同样计入台账与 K。"""
    metrics = load("service.backtest.metrics")
    result = metrics.compute_event_study(make_observations(daily_excess=0.0), cfg=cfg_event)
    stats = result.windows["60"]["market_portfolio"]

    assert stats.ci[0] <= 0.0 <= stats.ci[1], "零超额序列的 CI 必须包含 0（否则夹具失效）"
    record = models.ExperimentRecord(
        experiment_id="hyp-001-0001", hypothesis_id="hyp-001", params={},
        segment=models.Segment.VALIDATION, K=1, verdict=models.Verdict.INCONCLUSIVE,
        metrics={"n": stats.n, "mean": stats.mean}, prereg_commit="deadbeef",
        data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
        timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None)
    assert record.verdict is models.Verdict.INCONCLUSIVE
    assert record.K == 1, "无信号结论同样计入 K（spec R17 Scenario3）"


class _FlatPriceLoader:
    """零触发夹具：**故意只提供价格通道**，不带事件收益取数方法。

    区分力自证（R2-01 锁定）：旧实现（零事件先校验 loader/benchmark 再报缺口）在只有价格通道时
    必然抛 `BacktestDataGapError`；现契约要求零触发是**合法无信号**、在取数之前短路返回空观测。
    因此只要实现回退，`test_tc_r17_04` 的 `code == 0` 与 `"数据缺口" not in stderr` 即会红。
    """

    def __init__(self, closes):
        self._closes = list(closes)

    def load_price_rows(self, codes, start, end, adjust):
        dates = _flat_dates(start, end)
        rows = [{"trade_date": day, "open": px, "high": px, "low": px, "close": px,
                 "amount": 1e8, "avg_amount": 1e8,
                 "limit_up_price": round(px * 1.1, 2), "limit_down_price": round(px * 0.9, 2),
                 "suspended": False, "delisted": False, "st": False}
                for day, px in zip(dates, self._closes)]
        return {code: list(rows) for code in codes}


def _flat_dates(start: str, end: str) -> list[str]:
    import datetime as dt

    day = max(dt.date.fromisoformat(str(start)), dt.date(2020, 1, 2))
    stop = dt.date.fromisoformat(str(end))
    out = []
    while day <= stop and len(out) < 400:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += dt.timedelta(days=1)
    return out


def test_tc_r17_04_zero_trigger_cli_reaches_inconclusive_exit_0(load, models, cfg_raw, cfg_event,
                                                                cli_runner, registry_path, results_dir,
                                                                tmp_path, monkeypatch):
    """TC-R17-04（R17 Scenario3 / R2-01 锁定）：规则零触发 = 合法「无信号」→ CLI 退出码 0、
    结果行 `verdict=inconclusive / windows={} / n_events=0`，**不得**抛 `BacktestDataGapError`；
    而数据通道不可得（非零事件）仍必须抛缺口（两种语义不得混同）。
    """
    apps_cli = load("apps.cli")
    data = load("service.backtest.data")

    prereg_dir = tmp_path / "config" / "backtest" / "preregistrations"
    prereg_dir.mkdir(parents=True, exist_ok=True)
    (prereg_dir / "hid.yaml").write_text(json.dumps({
        "hypothesis_id": "hid",
        "statement": "跌破 MA60 后 60 日跑输买入持有",
        "params": {"ma": 60, "K": 1, "codes": ["000001"],
                   "start": "2020-01-01", "end": "2020-12-31"},
        "metrics": ["mean_excess"],
        "segments": ["validation"],
        "benchmarks": ["buy_and_hold"],
        "correction_method": "bonferroni",
        "k_definition": "规则×参数网格",
        "created_at": "2026-01-01T00:00:00",
    }), encoding="utf-8")
    monkeypatch.setattr(apps_cli, "_prereg_commit", lambda path: "deadbeef")
    monkeypatch.setattr(apps_cli, "build_backtest_loader",
                        lambda cfg: _FlatPriceLoader([10.0] * 260))

    result = cli_runner(["run", "--hypothesis", "hid"])

    assert result.returncode == 0, result.stderr
    assert "数据缺口" not in result.stderr and "预注册缺失" not in result.stderr
    assert "inconclusive" in result.stdout.lower()

    rows = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]
    results = [row for row in rows if row["row_type"] == "result"]
    assert len(results) == 1
    assert results[0]["verdict"] == "inconclusive"
    metrics = results[0]["metrics"]
    assert metrics["event_study"]["verdict"] == "inconclusive"
    assert metrics["event_study"]["windows"] == {}
    assert metrics["event_study"]["n_events"] == 0
    assert metrics["n_observations"] == 0
    assert metrics["corrected_p"] is None
    assert (results_dir / "hid-0001.json").exists(), "零触发也必须落结果 JSON"

    # 对照：**非零事件**但数据通道不可得 → 仍必须报缺口（不得静默降级为「无信号」）
    signal = models.EventSignal(condition_id="ma60_breakdown", event_date="2020-06-01")
    benchmark = models.Benchmark(kind="buy_and_hold", label="买入持有")
    with pytest.raises(models.BacktestDataGapError):
        data.load_event_observations([signal], [benchmark],
                                     loader=_FlatPriceLoader([10.0] * 260), cfg=cfg_event)
