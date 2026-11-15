"""proposal 成功标准 S1–S5 与 §2.3 退出码 E1–E3 的落位说明（本文件不放测试函数）。

为何没有测试函数：本套件按验收口径落 **56 条 Scenario 级 TC**（`test-design.md` §1.2）。
proposal 标准级 / 退出码级的断言**已被下列 Scenario 用例覆盖并折叠**，避免重复执行同一契约：

- TC-SC-01 校准题可复现（exit 0 + corrected_p）
  → `test_known_answer_calibration.py::test_tc_r18_01_passed_calibration_unlocks_research`
  （`passed=True`、`ci[1] < 0`、`K >= 1`、`corrected_p`、`calibration.json`）
- TC-SC-02 台账可审计（一条命令导出）
  → `test_prereg_ledger.py::test_tc_r02_02_tampered_ledger_row_rejected`（篡改被拒）
  + `test_out_of_sample_burn.py::test_tc_r04_01_first_use_marks_burnt_and_exports`（导出/`burnt`）
- TC-SC-03 样本外只烧一次可机检
  → `test_out_of_sample_burn.py::test_tc_r04_02_second_out_of_sample_request_rejected`
- TC-SC-04 成本与撮合可手算复算
  → `test_cost_hand_calc.py::test_tc_r07_01_cost_components_match_hand_calc`
  + `test_seal_rollover.py::test_tc_r08_01_limit_up_seal_defers_to_next_tradable_day`
  + `test_seal_rollover.py::test_tc_r08_04_suspended_day_skipped`
- TC-SC-05 无未来函数可证伪
  → `test_no_future_function.py::test_tc_r10_02_future_data_raises`
  + `test_no_future_function.py::test_tc_r10_03_signal_is_pure_and_io_free`
  + `test_financial_timing.py::test_tc_r11_01_annual_report_visible_only_after_announcement`
- E1 门禁失败 → 退出码 2
  → `test_known_answer_calibration.py::test_tc_r18_02_failed_calibration_blocks_output`
  （库层异常 + `calibration.json` passed=False + 执行行 FAILED；CLI 退出码 2 由 T5 端到端复跑）
- E2 参数/数据错误 → 退出码 1
  → `test_prereg_ledger.py::test_tc_r01_02_missing_preregistration_rejected`
  + `test_prereg_ledger.py::test_tc_r01_03_uncommitted_preregistration_rejected`
- E3 成功 → 退出码 0
  → `test_known_answer_calibration.py::test_tc_r18_01_passed_calibration_unlocks_research`
  （`assert_calibrated` 不抛 = 解锁）

**盲测声明**：本文件只依据 `test-design.md` §2.1/§2.3、`proposal.md` 成功标准、`design.md` §6.3 退出码；
未读 `src/service/backtest/`、`test/service/backtest/`。
"""

from __future__ import annotations

FOLDED_SUCCESS_CRITERIA = ("TC-SC-01", "TC-SC-02", "TC-SC-03", "TC-SC-04", "TC-SC-05")
FOLDED_EXIT_CODES = ("TC-EXIT-01", "TC-EXIT-02", "TC-EXIT-03")
