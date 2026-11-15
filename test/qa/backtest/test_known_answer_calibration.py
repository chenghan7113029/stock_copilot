"""R18 已知答案校准门禁（TC-R18-01..03）。

锚点：spec R18；design §4.1 `run_calibration(*, cfg, loader, registry) -> CalibrationResult`（扣成本；
loader 走 data.py 注入通道 `load_universe_codes` + `load_price_rows`）、`assert_calibrated(registry)`（库层 raise
`CalibrationFailedError`，**不断 SystemExit**）、「失败表达二分」（CLI 捕获后 `sys.exit(2)`）、
`write_calibration_result` 原子写 `<results_dir>/calibration.json`（失败 `passed=False` + `reason`）、§6.3；
校准口径按 T2-fix-5：`block_length/n_bootstrap` 来自 cfg、成本走 broker 四分量（Q4 缺即拒绝）。
"""

from __future__ import annotations

import json

import pytest


def test_tc_r18_01_passed_calibration_unlocks_research(load, models, cfg_calibration, calibration_loader,
                                                       registry, results_dir, alpha):
    """TC-R18-01（R18 Scenario1）：校准显著跑输（CI 上界 < 0）→ passed=True、K/校正后判定齐全、解锁。"""
    calibration = load("service.backtest.calibration")

    result = calibration.run_calibration(cfg=cfg_calibration, loader=calibration_loader, registry=registry)

    assert isinstance(result, models.CalibrationResult)
    assert result.ci is not None and result.ci[1] < 0, f"未复现显著跑输：{result.params} / {result.notes}"
    assert result.passed is True
    assert result.K is not None and result.K >= 1
    assert result.corrected_p is not None and result.corrected_p < alpha
    # 校准题是「跌破 MA60 卖出」这条规则：复现出显著跑输 ⇒ 该规则被判无效（Verdict.INVALID），
    # 同时台子因此「可信」(`passed=True`)；两者不矛盾（design §4.1 CalibrationResult.verdict 语义）
    assert result.verdict is models.Verdict.INVALID
    calibration.assert_calibrated(registry)  # 不抛 = 解锁研究输出
    payload = json.loads((results_dir / "calibration.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True


def test_tc_r18_02_failed_calibration_blocks_output(load, models, cfg_calibration, calibration_loader_no_signal,
                                                    registry, results_dir, run_rows, registry_path):
    """TC-R18-02（R18 Scenario2 + §2.3 E1）：校准未过 → 库层 raise；`calibration.json` passed=False；
    执行行 FAILED；退出码语义由 CLI 负责（=2），本用例不断 SystemExit。"""
    calibration = load("service.backtest.calibration")

    result = calibration.run_calibration(cfg=cfg_calibration, loader=calibration_loader_no_signal,
                                         registry=registry)

    assert result.passed is False
    assert result.verdict is not models.Verdict.VALID
    with pytest.raises(models.CalibrationFailedError) as exc:  # 库层异常，不是 SystemExit
        calibration.assert_calibrated(registry)
    assert getattr(exc.value, "reason", None) is not None
    payload = json.loads((results_dir / "calibration.json").read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload.get("reason")
    assert any(row["status"] == "failed" for row in run_rows(registry_path)), "校准失败必须落执行行"


def test_tc_r18_03_failure_never_framed_as_strategy_ineffective(load, cfg_calibration,
                                                                calibration_loader_no_signal, registry):
    """TC-R18-03（R18 Scenario3）：校准失败不得表述为「MA60 无效 / 策略无效」，只能是「台子不可信」。"""
    calibration = load("service.backtest.calibration")

    result = calibration.run_calibration(cfg=cfg_calibration, loader=calibration_loader_no_signal,
                                         registry=registry)
    blob = json.dumps(dict(result.__dict__), ensure_ascii=False, default=str)

    for banned in ("MA60 无效", "策略无效", "止损无效", "应该卖"):
        assert banned not in blob, f"校准失败不得写成策略结论：{banned}"
    assert result.direction in ("显著跑输", "未复现")
