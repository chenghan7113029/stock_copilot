"""proposal 失败标准 / 反目标 F1–F8 的落位说明（本文件不放测试函数）。

为何没有测试函数：反目标属「出现即失败」的证伪项，多数**就是**对应 Requirement 的负向 Scenario，
已在 56 条 TC 中以负向用例落地（不重复造用例）：

- F1 把策略结论写成本 change 交付物
  → `test_known_answer_calibration.py::test_tc_r18_03_failure_never_framed_as_strategy_ineffective`
  （禁词扫描：MA60 无效 / 策略无效 / 止损无效 / 应该卖）
- F2 未过校准却输出研究结论
  → `test_known_answer_calibration.py::test_tc_r18_02_failed_calibration_blocks_output`
- F3 预注册可事后改 / K 不报或补记
  → `test_prereg_ledger.py::test_tc_r02_02_tampered_ledger_row_rejected`
  + `test_multi_comparison.py::test_tc_r05_02_missing_k_is_inconclusive`
- F4 前复权 / 报告期当公告日 / 今日成分回看 / 剔除退市
  → `test_adjust.py::test_tc_r09_01_qfq_request_rejected`
  + `test_financial_timing.py`（TC-R11-01/02）
  + `test_survivorship_bias.py::test_tc_r12_02_st_status_is_point_in_time`
  + `test_survivorship_bias.py::test_tc_r12_04_missing_lists_report_gap`
- F5 日内止损 / T+0 / 涨停一定买到 / 跌停一定卖掉
  → `test_seal_rollover.py`（TC-R08-01..04）
  + `test_no_future_function.py::test_tc_r10_01_signal_at_t_fill_from_t_plus_one`
- F6 挑区间/切点/分组 + 软标签进分组
  → `test_labels.py`（TC-R15-01..03）
  + `test_segments.py::test_tc_r03_02_cross_segment_request_is_guarded`
- F7 LLM 生成或修改任何数值
  → `test_stat_inference.py` / `test_cost_hand_calc.py` / `test_multi_comparison.py`
  的确定性数值断言（期望值由独立算式给出，非 LLM 产物）
- F8 越界改文件
  → 由 T5 在 `verification.md` 用 `git show --name-only` / `git diff --name-only` 取证（非 pytest 断言）

**盲测声明**：只依据 `test-design.md` §2.2、`proposal.md`「失败标准/反目标」与 spec 的负向 Scenario；
未读 `src/service/backtest/`、`test/service/backtest/`。
"""

from __future__ import annotations

FOLDED_ANTI_GOALS = tuple(f"TC-AG-{index:02d}" for index in range(1, 9))
