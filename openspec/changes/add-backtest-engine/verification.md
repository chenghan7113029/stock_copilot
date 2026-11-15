# 验证报告：add-backtest-engine

- 变更：`openspec/changes/add-backtest-engine/`
- 波次：T5（t14）
- 验证人：qa
- 验证时间：2026-11-15 18:10
- 代码基线：`a6db7842c68dfa29ccde84a326a3f5ed07fe8721`（`git rev-parse HEAD` 输出）；工作树：`git status --porcelain` 仅本报告未跟踪
- 环境：Windows / Python 3.14.3 / pytest 9.0.3 / ruff 0.15.17；`openspec.cmd`；matplotlib 未安装
- 验证对象：committed HEAD（含 t13 / t17 / t21 三次实现对齐；design 已含 t15/t18 契约裁决）

> **证据纪律**：每条证据写成「命令 + 退出码 + 关键输出 / 测试节点 id」，数字与 sha 均复制自命令输出。

## 1. 结论（t14 基线；终稿见 §10）

> **终稿结论见 §10「复验（t20）」**：本节保留 t14 基线结论原文（append-only 精神），**未改动**。

**结论（t14 基线）**：不通过

**依据**：全量 `python -m pytest -q -m "not network and not akshare_legacy"` → **24 failed / 1018 passed / 35 deselected（exit 1）**。24 条红**全部**在 QA 套件 `test/qa/backtest/`；engineer 套件 987 passed，仅 2 条 e2e 因本地 sqlite schema 漂移红（本 change 未改 `src/dao`）。红点分三类：① **QA 夹具未跟上 T2-fix-4/5 契约**（broker 类缺 `limit_up_price/limit_down_price/avg_amount` 8 条、calibration 缺 `block_length` 3 条、labels 缺第三档特征 3 条、CLI 配置缺 `backtest:` 段 2 条、取 id 顺序 1 条、attribution 入参形状 1 条、空观测语义 1 条）；② **契约仍有 3 处未落字**（universe `provider` 协议、空观测表达、gate 判据缺失 vs 跳级优先级）；③ 2 条 e2e 为环境/存量 DB。**不是台子做错**：R1–R19 的 engineer 单测 987/987 绿。修完 §7 的 F1–F9 并复跑后转「通过」。

## 2. 验收标准逐条核对

### 2.1 T3 acceptance（任务契约原文）

> **前置说明（F11）**：T3 的 8 条 acceptance **原文未落盘**（`.agent-teams/add-backtest-engine/team.json` 的 t3/t17 无 `acceptance`；`tasks.md` 无 8 条清单）。为不「复述设计当验证」，本节用**交付物上的 8 条可机检闸门**逐条核对并标注来源；captain 补给原文后按原文重排。

| # | 验收闸门（来源） | 命令 | 退出码 | 关键输出 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 19 Requirement 均有实现 + 测试（spec + design §4.2） | 见 §5 | — | 19/19 有 engineer `test/service/backtest/` 覆盖；56/56 Scenario 有 QA 节点 | 通过 |
| 2 | T2.1–T2.20 全勾（`tasks.md`） | `grep -c '^- \[x\]'` / `'^- \[ \]'` | 0 | `23` / `0` | 通过 |
| 3 | engineer 套件全绿 | `python -m pytest -q test --ignore=test/qa` | 1 | `2 failed, 987 passed`；两条 e2e：`sqlite3.OperationalError: no such column: stock_snapshots.industry` | 未通过（环境，F10） |
| 4 | QA 56 条可收集 | `python -m pytest -q test/qa/backtest --collect-only` | 0 | `56 tests collected` | 通过 |
| 5 | QA 套件全绿 | `python -m pytest -q test/qa/backtest` | 1 | `24 failed, 32 passed` | 未通过（F1–F7） |
| 6 | ruff 不新增错误（captain 口径） | `python -m ruff check .` | 1 | `Found 38 errors`，全为存量基线文件；本 change 路径 **0** | 通过（基线 39 → 38，新增 0；本 change 另修掉既有 `src/apps/cli.py` I001） |
| 7 | 语法可编译 | `python -m compileall -q src test` | 0 | 无输出 | 通过 |
| 8 | change 规格自洽 | `openspec.cmd validate add-backtest-engine --strict` | 0 | `Change 'add-backtest-engine' is valid` | 通过 |

### 2.2 proposal 成功标准 / 失败标准

| # | 标准 | 是否达成 | 证据 |
| --- | --- | --- | --- |
| S1 | 校准题可复现（跌破 MA60 显著跑输 + K + 校正后 p） | **未达成** | 真实全 A 数据前置缺口（A1 后复权 / A4 退市ST、Q4 费率未定）；仅合成验证判定链：engineer `test/service/backtest/test_calibration.py` 6 项绿；QA `TC-R18-01/02/03` 红（F2：`cfg_cost` 缺 `block_length`）。结论级断言留待数据波 |
| S2 | 台账可审计（一条命令导出 6 类字段 + 改预注册被拒） | **部分达成** | engineer `test_registry.py::test_export_ledger_13_fields_and_statement_from_prereg` 绿（13 字段）；`statement` 仍走占位（`test_export_ledger_missing_prereg_uses_placeholder`），对应 R1 评审遗留 R1-02「statement 无数据源」**未闭合**；QA `TC-R02-02` 绿 |
| S3 | 样本外只烧一次可机检 | 达成 | QA `TC-R04-02` PASSED；engineer `test_registry.py::test_out_of_sample_burn_once_and_rejection_traced` / `test_burn_marker_is_idempotent_for_same_experiment` 绿 |
| S4 | 成本与撮合可手算复算（封板 + 停牌样例） | **部分达成** | engineer `test_broker.py::test_cost_four_components_hand_calc` / `test_limit_up_seal_rolls_over` / `test_suspended_day_skipped` 绿；QA `TC-R07-01/02/04`、`TC-R08-01..04` 红（F1 夹具） |
| S5 | 无未来函数可证伪 + 财务按公告日 | 达成 | QA `TC-R10-02` PASSED（价格/财务双路）、`TC-R11-01/02` PASSED；engineer `test_data.py::test_build_point_in_time_rejects_future_bar` / `test_financial_alignment_by_ann_date` 绿 |
| F1 | 把策略结论写成本 change 交付物 | 未违反 | 无「止损有效/MA60 应卖」类断言；engineer `test_calibration.py::test_failure_wording_never_blames_strategy` 绿 |
| F2 | 未过校准却输出研究结论 / 解释成策略无效 | 未违反 | `test_calibration.py::test_calibration_failure_blocks_output` 绿（库层 raise；CLI exit 2） |
| F3 | 预注册可事后改 / K 不报或补记 | 未违反 | `test_registry.py::test_tampered_row_rejected` / `test_duplicate_experiment_id_rejected` 绿；QA `TC-R02-02/03` 绿（`TC-R02-01` 红为夹具用法，F5） |
| F4 | 前复权 / 报告期当公告日 / 今日成分 / 剔除退市 | **部分未验证（风险）** | 前复权、公告日已阻（QA `TC-R09-01`、`TC-R11-*` 绿）；**生存偏差 R12 未验证**：`TC-R12-01..04` 红，根因 `provider` 协议缺失（F8），非实现放行 |
| F5 | 日内止损 / T+0 / 涨停一定买到 / 跌停一定卖掉 | 未违反（实现侧） | `test_broker.py::test_t1_rejected_same_batch` / `test_limit_up_seal_rolls_over` 绿；QA 4 条红为夹具（F1） |
| F6 | 挑区间/切点/分组 + 软标签进分组 | 未违反（实现侧） | `test_universe.py` 9 项绿（软标签/未来分组拒绝）；QA `TC-R15-01..03` 红（F3） |
| F7 | LLM 生成或修改任何数值 | 未违反 | `grep -rn 'openai\|llm' src/service/backtest src/data_provider/backtest` → 空输出；成本/统计期望值由独立算式给出 |
| F8 | 越界改文件（`openspec/specs/` / `docs/mrd/` / 伪造锚点） | 未违反 | 本 change 全部提交文件集合与 `openspec/specs/`、`docs/mrd/` 交集为空（§8 命令） |

## 3. 测试执行

| 套件 | 命令 | 结果 | 备注 |
| --- | --- | --- | --- |
| engineer `test/` | `python -m pytest -q test --ignore=test/qa` | **2 failed / 987 passed / 32 deselected（exit 1）** | 仅 e2e 两条（F10 环境） |
| QA `test/qa/backtest/` | `python -m pytest -q test/qa/backtest` | **24 failed / 32 passed（exit 1）**；collect：56，exit 0 | 负向/对抗（盲测），红点见 §7 |
| 全量 | `python -m pytest -q -m "not network and not akshare_legacy"` | **24 failed / 1018 passed / 35 deselected（exit 1）** | 35 deselect = `akshare_legacy` |
| 静态检查 | `python -m ruff check .` | exit 1 | `Found 38 errors`；本 change 路径 0；口径 = 不修基线、不记失败、不跳过 |
| 语法检查 | `python -m compileall -q src test` | exit 0 | 无输出 |

## 4. 负向与边界用例（真实执行于 2026-11-15 18:10）

| # | 场景 | 输入 | 期望 | 实际（命令 + 退出码 + 关键输出） | 结论 |
| --- | --- | --- | --- | --- | --- |
| TC-R09-01 | 前复权被拒 | load_price_series(adjust='qfq') | InvalidAdjustModeError | `passed` | PASSED |
| TC-R10-02 | 未来函数越界 | PointInTimeSnapshot 含 t+1 bar / 未来可见财务 | FutureDataError | `passed` | PASSED |
| TC-R04-02 | 样本外二次使用 | 同实验二次 assert_not_burnt | RegistryImmutableError + 烧毁标记唯一 | `passed` | PASSED |
| TC-R05-02 | 缺 K 判不可采信 | ExperimentRecord(K=None) | verdict=INCONCLUSIVE | `passed` | PASSED |
| TC-R02-02 | 台账篡改被拒 | 改写 NDJSON 的 K 后 get | RegistryCorruptedError | `passed` | PASSED |
| TC-R08-01 | 封板顺延 | t+1 一字涨停 | FAILED_LIMIT_SEAL → 次日成交 | `failed`：D:\workspace\stock_copilot\src\service\backtest\broker.py:367: common.exceptions.BacktestDataGapError: 000001 2020-01-07 缺涨跌停价，封板判定不可做（R8） | FAILED |
| TC-R08-03 | T+1 拒当日卖 | t 日买、同日卖 | REJECTED_T1 | `failed`：D:\workspace\stock_copilot\src\service\backtest\broker.py:367: common.exceptions.BacktestDataGapError: 000001 2020-01-07 缺涨跌停价，封板判定不可做（R8） | FAILED |
| TC-R08-04 | 停牌跳过 | t+1 停牌 | SKIPPED_SUSPENDED → 复牌日成交 | `failed`：D:\workspace\stock_copilot\src\service\backtest\broker.py:367: common.exceptions.BacktestDataGapError: 000001 2020-01-07 缺涨跌停价，封板判定不可做（R8） | FAILED |

## 5. 规格一致性（19 R / 56 Scenario → 覆盖测试）

| Requirement | Scenario | QA 覆盖（节点 + 本次状态） | engineer 覆盖 |
| --- | --- | --- | --- |
| R1 | 预注册后正常执行 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r01_01_preregistered_run_records_commit_and_params`（PASSED） | `test/service/backtest/test_registry.py / test_cli_backtest.py` |
| R1 | 无预注册时拒绝执行 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r01_02_missing_preregistration_rejected`（FAILED） | `test/service/backtest/test_registry.py / test_cli_backtest.py` |
| R1 | 预注册只在工作区未提交 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r01_03_uncommitted_preregistration_rejected`（FAILED） | `test/service/backtest/test_registry.py / test_cli_backtest.py` |
| R2 | 每次执行追加一行 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r02_01_each_run_appends_one_row_with_unique_id`（FAILED） | `test/service/backtest/test_registry.py` |
| R2 | 修改已写入的台账行被拒绝 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r02_02_tampered_ledger_row_rejected`（PASSED） | `test/service/backtest/test_registry.py` |
| R2 | 改假设必须新开实验 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r02_03_assumption_change_requires_new_experiment`（PASSED） | `test/service/backtest/test_registry.py` |
| R3 | 默认三段切分 | `test/qa/backtest/test_segments.py::test_tc_r03_01_default_three_segments_reported`（PASSED） | `test/service/backtest/test_config.py` |
| R3 | 区间不在任何段内被拒 | `test/qa/backtest/test_segments.py::test_tc_r03_02_cross_segment_request_is_guarded`（PASSED） | `test/service/backtest/test_config.py` |
| R3 | 训练段可重复使用 | `test/qa/backtest/test_segments.py::test_tc_r03_03_training_segment_reusable`（PASSED） | `test/service/backtest/test_config.py` |
| R4 | 首次使用样本外并烧毁 | `test/qa/backtest/test_out_of_sample_burn.py::test_tc_r04_01_first_use_marks_burnt_and_exports`（PASSED） | `test/service/backtest/test_registry.py` |
| R4 | 第二次请求样本外被拒绝 | `test/qa/backtest/test_out_of_sample_burn.py::test_tc_r04_02_second_out_of_sample_request_rejected`（PASSED） | `test/service/backtest/test_registry.py` |
| R4 | 新实验拥有独立额度 | `test/qa/backtest/test_out_of_sample_burn.py::test_tc_r04_03_new_experiment_has_independent_quota`（PASSED） | `test/service/backtest/test_registry.py` |
| R5 | 报告 K 与校正后显著性 | `test/qa/backtest/test_multi_comparison.py::test_tc_r05_01_reports_k_and_corrected_significance`（PASSED） | `test/service/backtest/test_metrics.py` |
| R5 | 未报告 K 时禁止下结论 | `test/qa/backtest/test_multi_comparison.py::test_tc_r05_02_missing_k_is_inconclusive`（PASSED） | `test/service/backtest/test_metrics.py` |
| R5 | K 增大导致判定翻转 | `test/qa/backtest/test_multi_comparison.py::test_tc_r05_03_k_increase_flips_verdict`（PASSED） | `test/service/backtest/test_metrics.py` |
| R6 | 同组同涨同跌时按时间块计有效样本 | `test/qa/backtest/test_stat_inference.py::test_tc_r06_01_block_bootstrap_reports_effective_sample`（PASSED） | `test/service/backtest/test_metrics.py` |
| R6 | 默认推断不使用 iid 假设 | `test/qa/backtest/test_stat_inference.py::test_tc_r06_02_default_inference_requires_block_sampling`（PASSED） | `test/service/backtest/test_metrics.py` |
| R7 | 单笔成交成本可分项复算 | `test/qa/backtest/test_cost_hand_calc.py::test_tc_r07_01_cost_components_match_hand_calc`（FAILED） | `test/service/backtest/test_broker.py` |
| R7 | 小额成交触发最低佣金 | `test/qa/backtest/test_cost_hand_calc.py::test_tc_r07_02_small_trade_hits_minimum_commission`（FAILED） | `test/service/backtest/test_broker.py` |
| R7 | 费率配置缺失时拒绝执行 | `test/qa/backtest/test_cost_hand_calc.py::test_tc_r07_03_missing_fee_config_rejected`（PASSED） | `test/service/backtest/test_broker.py` |
| R7 | 流动性上限截断单笔金额 | `test/qa/backtest/test_cost_hand_calc.py::test_tc_r07_04_liquidity_cap_truncates_order`（FAILED） | `test/service/backtest/test_broker.py` |
| R8 | 一字涨停买不进顺延 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_01_limit_up_seal_defers_to_next_tradable_day`（FAILED） | `test/service/backtest/test_broker.py` |
| R8 | 跌停卖不出顺延 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_02_limit_down_seal_defers_sell`（FAILED） | `test/service/backtest/test_broker.py` |
| R8 | 当日买入当日卖出被拒绝 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_03_same_day_sell_rejected_by_t1`（FAILED） | `test/service/backtest/test_broker.py` |
| R8 | 停牌日跳过 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_04_suspended_day_skipped`（FAILED） | `test/service/backtest/test_broker.py` |
| R9 | 前复权请求被拒 | `test/qa/backtest/test_adjust.py::test_tc_r09_01_qfq_request_rejected`（PASSED） | `test/service/backtest/test_data.py` |
| R9 | 分红日无假跳空 | `test/qa/backtest/test_adjust.py::test_tc_r09_02_adjusted_series_has_no_fake_gap`（PASSED） | `test/service/backtest/test_data.py` |
| R9 | 输出记录口径元数据 | `test/qa/backtest/test_adjust.py::test_tc_r09_03_result_records_adjust_metadata`（PASSED） | `test/service/backtest/test_data.py` |
| R10 | 信号在 t 日、成交在 t+1 | `test/qa/backtest/test_no_future_function.py::test_tc_r10_01_signal_at_t_fill_from_t_plus_one`（FAILED） | `test/service/backtest/test_signal.py / test_data.py` |
| R10 | 越界访问抛错 | `test/qa/backtest/test_no_future_function.py::test_tc_r10_02_future_data_raises`（PASSED） | `test/service/backtest/test_signal.py / test_data.py` |
| R10 | 同输入同输出（纯函数可复现） | `test/qa/backtest/test_no_future_function.py::test_tc_r10_03_signal_is_pure_and_io_free`（PASSED） | `test/service/backtest/test_signal.py / test_data.py` |
| R11 | 年报在 4 月底之后才可见 | `test/qa/backtest/test_financial_timing.py::test_tc_r11_01_annual_report_visible_only_after_announcement`（PASSED） | `test/service/backtest/test_data.py` |
| R11 | 公告日缺失时回退并标注 | `test/qa/backtest/test_financial_timing.py::test_tc_r11_02_missing_ann_date_falls_back_and_flags`（PASSED） | `test/service/backtest/test_data.py` |
| R12 | 退市股在退市前仍被计入 | `test/qa/backtest/test_survivorship_bias.py::test_tc_r12_01_delisted_stock_counted_before_delisting`（FAILED） | `test/service/backtest/test_universe.py` |
| R12 | ST 状态按时点判定 | `test/qa/backtest/test_survivorship_bias.py::test_tc_r12_02_st_status_is_point_in_time`（FAILED） | `test/service/backtest/test_universe.py` |
| R12 | 历史成分与当前成分不同 | `test/qa/backtest/test_survivorship_bias.py::test_tc_r12_03_historical_index_constituents`（FAILED） | `test/service/backtest/test_universe.py` |
| R12 | 名单不可得时报缺口 | `test/qa/backtest/test_survivorship_bias.py::test_tc_r12_04_missing_lists_report_gap`（FAILED） | `test/service/backtest/test_universe.py` |
| R13 | 输出相对基准超额 | `test/qa/backtest/test_benchmark.py::test_tc_r13_01_event_study_reports_both_benchmarks`（PASSED） | `test/service/backtest/test_metrics.py` |
| R13 | 缺失基准时不出结论 | `test/qa/backtest/test_benchmark.py::test_tc_r13_02_missing_benchmark_is_inconclusive`（FAILED） | `test/service/backtest/test_metrics.py` |
| R13 | 归因四项齐全 | `test/qa/backtest/test_benchmark.py::test_tc_r13_03_attribution_has_four_factor_contributions`（FAILED） | `test/service/backtest/test_metrics.py` |
| R14 | 全期显著但仅一段贡献 | `test/qa/backtest/test_stability.py::test_tc_r14_01_single_year_contribution_marks_scope`（PASSED） | `test/service/backtest/test_metrics.py` |
| R14 | 分档样本不足时报警 | `test/qa/backtest/test_stability.py::test_tc_r14_02_small_tier_is_flagged_and_excluded`（PASSED） | `test/service/backtest/test_metrics.py` |
| R15 | 软标签被拒绝进入分组 | `test/qa/backtest/test_labels.py::test_tc_r15_01_soft_label_rejected`（FAILED） | `test/service/backtest/test_universe.py` |
| R15 | 用未来信息分组的请求被拒 | `test/qa/backtest/test_labels.py::test_tc_r15_02_future_grouping_rejected`（FAILED） | `test/service/backtest/test_universe.py` |
| R15 | 季度重算不回改历史 | `test/qa/backtest/test_labels.py::test_tc_r15_03_quarterly_recompute_never_rewrites_history`（FAILED） | `test/service/backtest/test_universe.py` |
| R16 | 单票样本少时向组均值收缩 | `test/qa/backtest/test_labels.py::test_tc_r16_01_thin_sample_shrinks_to_group_mean`（PASSED） | `test/service/backtest/test_metrics.py` |
| R16 | 拒绝输出绝对收益预测 | `test/qa/backtest/test_labels.py::test_tc_r16_02_no_absolute_return_prediction_field`（PASSED） | `test/service/backtest/test_metrics.py` |
| R17 | 条件成立后 20 / 60 日超额分布 | `test/qa/backtest/test_event_study.py::test_tc_r17_01_twenty_and_sixty_day_windows`（PASSED） | `test/service/backtest/test_metrics.py` |
| R17 | 事件数不足时不出结论 | `test/qa/backtest/test_event_study.py::test_tc_r17_02_insufficient_events_marks_insufficient_sample`（PASSED） | `test/service/backtest/test_metrics.py` |
| R17 | 允许结论为无信号 | `test/qa/backtest/test_event_study.py::test_tc_r17_03_no_signal_is_a_legal_conclusion`（PASSED） | `test/service/backtest/test_metrics.py` |
| R18 | 校准通过后允许出结论 | `test/qa/backtest/test_known_answer_calibration.py::test_tc_r18_01_passed_calibration_unlocks_research`（FAILED） | `test/service/backtest/test_calibration.py` |
| R18 | 校准不通过时封锁输出 | `test/qa/backtest/test_known_answer_calibration.py::test_tc_r18_02_failed_calibration_blocks_output`（FAILED） | `test/service/backtest/test_calibration.py` |
| R18 | 校准失败不得解释为策略无效 | `test/qa/backtest/test_known_answer_calibration.py::test_tc_r18_03_failure_never_framed_as_strategy_ineffective`（FAILED） | `test/service/backtest/test_calibration.py` |
| R19 | 未过回测不得进入影子运行 | `test/qa/backtest/test_gates.py::test_tc_r19_01_cannot_enter_shadow_without_backtest`（FAILED） | `test/service/backtest/test_gates.py` |
| R19 | 影子期未满不得启用实盘 | `test/qa/backtest/test_gates.py::test_tc_r19_02_shadow_period_too_short_blocks_live`（PASSED） | `test/service/backtest/test_gates.py` |
| R19 | 门禁状态可查询且唯一 | `test/qa/backtest/test_gates.py::test_tc_r19_03_gate_state_is_unique_and_queryable`（PASSED） | `test/service/backtest/test_gates.py` |

**汇总**：56/56 Scenario 有 QA 节点（可收集、可溯源 `TC-Rxx-yy`）；本次 **32 PASSED / 24 FAILED**。19/19 Requirement 有 engineer `test/service/backtest/` 覆盖。

## 6. 未覆盖项与风险

- **真实全 A 校准（S1/R18）**：后复权全 A、退市/ST 名单、Q4 费率、Q5 封板口径缺（A1/A4/Q4/Q5）→ 只能合成验证，proposal S1 本波不可判定。
- **R12 生存偏差**：`provider` 协议未定义（F8）；退市/ST/历史成分依赖真实数据源。
- **R3 跨段拒绝入口**：design 只给 `BacktestConfig.segments`（必须键）与 `Segment` 枚举，未定义「横跨段请求」校验入口；QA 只断配置不变量（`TC-R03-02` PASSED）。
- **R14 牛熊震荡维度**：KQ-7 未答复 → 该维度「口径未定」不参与判定（`TC-R14-01/02` PASSED，仅覆盖分年度/分市值档）。
- **R16 收缩强度**：KQ-3 未答复 → 只用夹具显式 `shrink`（`TC-R16-01` PASSED）。
- **R18 校准判据**：KQ-1（次新股）/KQ-5（显著）未答复 → 校准口径按 spec 固定值，notes 标注。
- **多档 `liquidity_cap`**：无 adv 数据源 → 多档直接报缺口（design「撮合机制第 5 条」），只测单档。
- **e2e 两条**：本地 sqlite `stock_snapshots.industry` 缺列；本 change 未改 `src/dao`（§8 越界自检）→ 环境/存量 DB 偏差（F10）。
- **图表**：matplotlib 未安装，本 change out of scope。

## 7. 失败项记录（结构化 finding）

| finding id | 严重度 | 问题 | 要求修复（requiredFix） | 位置 | 阻塞归档 |
| --- | --- | --- | --- | --- | --- |
| F1 | high | QA broker 类 `PriceBar` 缺 `limit_up_price/limit_down_price` 与 `avg_amount`，实现按设计 `BacktestDataGapError`，8 条红 | 改 `test/qa/backtest/conftest.py` 的 `make_bar`：默认 `limit_up=round(close*1.1,2)`、`limit_down=round(close*0.9,2)`、`avg_amount=amount`（封板用例保留显式一字板价）；复跑 `python -m pytest -q test/qa/backtest -k "R07 or R08 or R10"` 应全绿 | `test/qa/backtest/conftest.py:198`；`test_cost_hand_calc.py:27/49/71`、`test_seal_rollover.py:20/38/52/67`、`test_no_future_function.py:15` | 是 |
| F2 | high | QA 校准 3 条用 `cfg_cost`（缺 `block_length/n_bootstrap`）→ `MissingBacktestConfigError` | conftest 增 `cfg_calibration`（`CFG_REQUIRED+CFG_BROKER+CFG_EVENT`），三条用例改用它；复跑 `test_known_answer_calibration.py` | `test/qa/backtest/conftest.py:49`、`test_known_answer_calibration.py:20/38/60` | 是 |
| F3 | high | QA 分组 `_features` 只 2 档（缺 `volatility_tier`），实现先报「缺分组特征」，3 条红 | 补 `volatility_tier`，键名对齐 `market_cap_tier/dividend_tier/volatility_tier`；软标签/未来分组用例先补齐特征再断言拒绝文案 | `test/qa/backtest/test_labels.py:22` | 是 |
| F4 | high | `cli_runner` 写裸 dict，缺顶层 `backtest:` 段；CLI 报「缺少 backtest: 段」，2 条红 | 改成 `json.dumps({"backtest": cfg_raw})` | `test/qa/backtest/conftest.py:273` | 是 |
| F5 | medium | `TC-R02-01` 连续两次 `next_experiment_id` 得同一 id → 二次 `append` 抛 `RegistryImmutableError` | 循环内「取 id → append」；断言两行 id 递增 | `test/qa/backtest/test_prereg_ledger.py:80` | 否 |
| F6 | medium | QA attribution 仍按旧签名传 `benchmarks` 位置参；T2-fix-5 已定 `attribution(returns: dict, factors)`（键 `rule`/`market_portfolio`），1 条红 | 改 `test_tc_r13_03` 传 `{"rule": [...], "market_portfolio": [...]}` + `factors` 三键；缺基准分支断 `result.verdict is INCONCLUSIVE`（不抛） | `test/qa/backtest/test_benchmark.py:55` | 是 |
| F7 | medium | `compute_event_study(())` 空观测：实现抛 `BacktestError`（metrics.py:251），spec R13 S2 只要求「不可判定」；QA `TC-R13-02` 期望空窗口 → 红 | architect 在 design §4.1 加一句「空观测 → 抛 `BacktestError`、不得出结论」；QA 改断 `pytest.raises(BacktestError)` + 不产生结果行 | `src/service/backtest/metrics.py:251`；`test/qa/backtest/test_benchmark.py:31` | 是（需裁决） |
| F8 | medium | universe `provider` 协议未定义（§4.1 只写 `provider`），实现要求对象方法 `load_members(...)`；R12 4 条红 | architect 在 §4.1 写明 `provider` 协议（方法名/入参/返回，如 `load_members(as_of) -> {members, delisted, st}`）；QA 夹具按协议改 spy provider | `openspec/changes/add-backtest-engine/design.md:542`；`test/qa/backtest/test_survivorship_bias.py:24/38/53/66` | 是（需裁决） |
| F9 | medium | 「判据缺失→`MissingBacktestConfigError`」与「跳级→`GateSkipError`」在 `BACKTEST_PENDING→SHADOW_RUNNING` 同时成立，优先级未定；实现先判边 → QA `TC-R19-01` 红 | architect 在 §4.1 补一句优先序（先判 `gate_criteria` 存在性 or 先判合法边）；QA 按裁定调断言顺序 | `src/service/backtest/gates.py:179`；`test/qa/backtest/test_gates.py:14` | 是（需裁决） |
| F10 | low | 2 条 e2e 红：本地 sqlite `no such column: stock_snapshots.industry`（存量 DB schema 漂移）；本 change 未改 `src/dao` | captain 定口径：记为环境/存量偏差，归档前重建本地 DB 后复跑两条 e2e 应绿 | `test/e2e/test_value_data_pipeline.py:104`、`test/e2e/test_tushare_pipeline.py` | 否 |
| F11 | low | T3 的 8 条 acceptance 原文未落盘（team.json t3/t17 无 `acceptance`；tasks.md 无清单），只能以可机检闸门替代 | captain 把 T3 acceptances 补进 `tasks.md`「T3 实现记录」或 team.json；下轮按原文复核 | `openspec/changes/add-backtest-engine/tasks.md:186` | 否 |
| F12 | low | 验证期间 HEAD 连变（`d9c860a`→`c0f0507`→`a6db784`），同命令两次结果不同（25/32 failed）→ 基线不冻结 | 归档前先 `git status` 干净并冻结 HEAD，再重跑 §8 全部命令；本报告数字绑定 a6db7842c68dfa29ccde84a326a3f5ed07fe8721 | — | 否（归档必重跑） |
| F13 | low | `verification.md` 原为 engineer 的 T3 逐条证据（t13，基线 `0cc6f85`，96 行）；按角色契约本文件归 QA（T5），已被本次 8 章报告覆盖；旧证据仅存于 git 历史 | 保留历史不影响归档，但建议 engineer 把 T2.1–T2.20 逐条证据迁到 `tasks.md`「T3 实现记录」或独立 `evidence-t3.md`（本波不改，避免越界）；captain 若要求保留可指定文件 | `openspec/changes/add-backtest-engine/verification.md`（`git show HEAD~1:...` 可查旧版） | 否 |

## 8. 复现说明

```bash
git rev-parse HEAD                 # 期望 a6db7842c68dfa29ccde84a326a3f5ed07fe8721
git status --porcelain             # 期望为空（本报告除外）
python -m pytest -q -m "not network and not akshare_legacy"   # 期望 exit 0（当前 24 failed）
python -m pytest -q test --ignore=test/qa                     # 期望 exit 0（e2e 需本地 DB schema 正常）
python -m pytest -q test/qa/backtest                          # 期望 exit 0（当前 24 failed）
python -m ruff check .             # 期望只余基线存量错误（本 change 路径 0）
python -m compileall -q src test   # 期望 exit 0
openspec.cmd validate add-backtest-engine --strict            # 期望 exit 0
# 越界自检（本 change 全部提交；期望空输出）
git log --format=%H --grep=add-backtest-engine | while read c; do git show --name-only --format='' $c; done | sort -u | grep -E '^openspec/specs/|^docs/mrd/'
```

## 9. Case 复现核对 + 记 trace

**不适用**：`proposal.md` 未声明「Case 复现锚点」（本 change 交付台子能力，不是某个 case 的功能实现），故本波**不写** `docs/cases/<case>/traces.yaml`，也不手写「复现进度」表。若后续把「跌破 MA60」校准题作为首个 case，则在数据前置补齐后由 T5 补 trace（`kind: reproduction`、`layer: number`）。

---

## 10. 复验（t20）——终稿

- 复验时间：2026-11-15 18:19
- 复验基线：`8c7f855a398b101217f87b24330447c35944b9aa`（`git rev-parse HEAD`；开始时记录、结束时复核一致；`git status --porcelain` 为空）
- 复验对象：t19（QA 夹具修复 8c7f855）+ t21（实现对齐 a6db784）；F7/F8 的 architect 裁决（t22）**尚未落盘**
- 测量窗口：本条记录写入时 `git status` 为空；**提交后**工作区出现 `M openspec/changes/add-backtest-engine/design.md`（t22 正在编辑，未提交）——本报告全部数字绑定 `8c7f855`，未混入 t22 变更（F12 纪律：不混两个基线）

### 10.1 终稿结论

**结论**：不通过（可复审）

**依据**：全量 `python -m pytest -q -m "not network and not akshare_legacy"` → **5 failed / 1037 passed / 35 deselected（exit 1）**，相对 t14 基线 **24 failed / 1018 passed** 已消除 **19 条**红点、新增通过 19 条。剩余 5 条红**全部**在 QA 套件，且**不是实现缺陷**：4 条 `TC-R12-01..04` 等 F8（universe `provider` 协议）裁决、1 条 `TC-R13-02` 等 F7（空观测语义）裁决——两项裁决由 architect t22 负责、当前 HEAD 无对应提交。engineer 套件 987/987 绿（仅 2 条 e2e 为本地 DB 环境红，captain 已裁定 F10=环境偏差）。**条件**：F7/F8 裁决落盘 → 我补 5 条夹具（spy provider + 空观测断言）→ 冻结 HEAD 复跑；预计 1 轮内转「通过」。本结论**不是**「差不多」，5 条红点均有 finding 与 requiredFix（§10.6）。

### 10.2 修复前后对比（同一命令族）

| 套件 | t14 基线（a6db784） | t20 复验（8c7f855a398b101217f87b24330447c35944b9aa） | 变化 |
| --- | --- | --- | --- |
| 全量 `-m "not network and not akshare_legacy"` | 24 failed / 1018 passed / 35 deselected（exit 1） | **5 failed / 1037 passed / 35 deselected（exit 1）** | −19 failed / +19 passed |
| engineer `test --ignore=test/qa` | 2 failed / 987 passed（exit 1） | **2 failed / 987 passed（exit 1）** | 无变化（仅 e2e 环境，F10） |
| QA `test/qa/backtest` | 24 failed / 32 passed（exit 1） | **5 failed / 51 passed（exit 1）** | −19 failed / +19 passed |
| QA `--collect-only` | 56 collected（exit 0） | **56 collected（exit 0）** | 不变 |
| `ruff check .` | 38 errors（基线 39；本 change 新增 0） | **38 errors（基线 39；本 change 新增 0）** | 不变 |
| `compileall -q src test` | exit 0 | **exit 0** | 不变 |
| `validate add-backtest-engine --strict` | exit 0 | **exit 0（`Change 'add-backtest-engine' is valid`）** | 不变 |

### 10.3 t14 基线 findings 逐条去向

| finding | t14 内容 | t20 去向 | 证据 |
| --- | --- | --- | --- |
| F1（high） | QA `PriceBar` 缺涨跌停价/`avg_amount` → 8 红 | **已消除** | t19 改 `conftest.py::make_bar` 默认 `limit_up_price/limit_down_price/avg_amount`；`TC-R07-01/02/04`、`TC-R08-01..04`、`TC-R10-01` 全部 PASSED |
| F2（high） | 校准用例缺 `block_length/n_bootstrap` → 3 红 | **已消除** | `cfg_calibration` + `_CalibrationAdapter`；`TC-R18-01/02/03` PASSED |
| F3（high） | 分组 `_features` 缺 `volatility_tier` → 3 红 | **已消除** | 维度名对齐 `market_cap/dividend_yield/volatility`；`TC-R15-01/02/03` PASSED |
| F4（high） | `cli_runner` 未包 `backtest:` 段 → 2 红 | **已消除** | `{"backtest": cfg_raw}`；`TC-R01-02/03` PASSED |
| F5（medium） | `TC-R02-01` 取 id 顺序 | **已消除** | 循环内「取 id → append」；PASSED |
| F6（medium） | attribution 旧签名/入参 | **已消除** | `returns={"rule","market_portfolio"}` + 恒等式；`TC-R13-03` PASSED |
| F7（medium） | 空观测：实现 raise vs spec「不可判定」 | **仍存在（待 t22 裁决）** | `TC-R13-02` FAILED：`BacktestError: 事件研究无观测：不得产出结论（R17）`；裁决后我改断 `pytest.raises(BacktestError)` 或实现改返回不可判定 |
| F8（medium） | universe `provider` 协议未定义 | **仍存在（待 t22 裁决）** | `TC-R12-01..04` FAILED：`BacktestDataGapError: universe provider 缺 load_members`；裁决后补 spy provider（`load_members` + `load_flags`） |
| F9（medium） | gate「判据缺失」vs「跳级」优先序 | **已消除（用例层）** | t19 改走**合法边** `BACKTEST_PENDING→BACKTEST_PASSED` 触发 `MissingBacktestConfigError`，跳级仍断 `GateSkipError`；`TC-R19-01` PASSED。design 文本优先序仍建议 t22 补一句（不影响验收） |
| F10（low） | 2 条 e2e：本地 sqlite `no such column: stock_snapshots.industry` | **维持（captain 裁环境偏差）** | `git diff --stat ba609a0..HEAD -- src/dao` 空（本 change 未改 dao）；e2e 仍红（本地库缺列），记 `IMPROVEMENTS` |
| F11（low） | T3 8 条 acceptance 原文未落盘 | **部分消除** | captain 已让 architect 在 tasks.md「附录 A」登记；**本轮核查 tasks.md 尚无「附录 A」**（t22 未执行）→ 仍引用 §2.1 的可机检闸门口径，待附录落盘后按原文重排 |
| F12（low） | 验证期 HEAD 连变 | **受控** | 本轮先记 `8c7f855a398b101217f87b24330447c35944b9aa`、`git status` 干净、结束时复核一致（见 §10.9） |
| F13（low） | `verification.md` 归属（旧 T3 证据） | **接受（不回滚）** | captain 确认本文件归 T5；旧 T3 证据可用 `git show c9ba19b~1:openspec/changes/add-backtest-engine/verification.md` 取 |

### 10.4 T3 acceptance 8 条（复跑）

| # | 闸门 | 命令 | 退出码 | 关键输出 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 19 Requirement 有实现 + 测试 | 见 §10.6 + §5 | — | 19/19 有 engineer 覆盖；56/56 有 QA 节点 | 通过 |
| 2 | T2.1–T2.20 全勾 | `grep -c '^- \[x\]' tasks.md` / `'^- \[ \]'` | 0 | `23` / `0` | 通过 |
| 3 | engineer 套件全绿 | `python -m pytest -q test --ignore=test/qa` | 1 | `2 failed, 987 passed`（仅 2 条 e2e 环境，F10 已裁） | 通过（按 captain F10 口径） |
| 4 | QA 56 条可收集 | `--collect-only` | 0 | `56 tests collected` | 通过 |
| 5 | QA 套件全绿 | `python -m pytest -q test/qa/backtest` | 1 | `5 failed, 51 passed`（F7/F8 待裁） | **未通过（待 t22）** |
| 6 | ruff 不新增 | `python -m ruff check .` | 1 | `Found 38 errors`；本 change 路径 0 | 通过（基线 39→38，新增 0） |
| 7 | 语法可编译 | `python -m compileall -q src test` | 0 | 无输出 | 通过 |
| 8 | change 规格自洽 | `openspec.cmd validate add-backtest-engine --strict` | 0 | `Change 'add-backtest-engine' is valid` | 通过 |

### 10.5 proposal 成功/失败标准（复验）

| # | 标准 | t14 | t20 复验 | 证据 |
| --- | --- | --- | --- | --- |
| S1 | 校准题可复现（显著跑输 + K + 校正后 p） | 未达成 | **部分达成（机制已绿）** | `TC-R18-01` PASSED（49 事件、CI(−0.018,−0.009)、p≈1.5e-9；`passed=True`）+ engineer `test_calibration.py` 6 绿；**真实全 A 仍因 A1/A4/Q4/Q5 数据缺口不可复现** |
| S2 | 台账可审计（导出 6 类字段 + 改预注册被拒） | 部分达成 | 部分达成 | engineer `test_export_ledger_13_fields_and_statement_from_prereg` 绿；`statement` 仍走占位（R1-02 未闭合，非本 change 范围）；`TC-R02-02` PASSED |
| S3 | 样本外只烧一次可机检 | 达成 | 达成 | `TC-R04-02/03` PASSED；engineer burn 幂等/独立额度绿 |
| S4 | 成本与撮合可手算复算 | 部分达成 | **达成** | `TC-R07-01/02/04`、`TC-R08-01..04`、`TC-R10-01` 全 PASSED；engineer `test_broker.py` 13 绿（含手算/封板/停牌/T+1/流动性） |
| S5 | 无未来函数可证伪 + 公告日 | 达成 | 达成 | `TC-R10-02/03`、`TC-R11-01/02` PASSED；engineer `test_data.py` 绿 |
| F1 | 把策略结论写成交付物 | 未违反 | 未违反 | 无结论式断言；`test_calibration.py::test_failure_wording_never_blames_strategy` 绿 |
| F2 | 未过校准却出结论/解释成策略无效 | 未违反 | 未违反 | `TC-R18-02/03` PASSED（库层 raise + 禁词扫描） |
| F3 | 预注册可事后改 / K 不报 | 未违反 | 未违反 | `TC-R02-02/03` PASSED；engineer registry 篡改/重复 id/缺字段 绿 |
| F4 | 前复权/报告期/今日成分/剔除退市 | 部分未验证 | **部分未验证（保持）** | 前复权 `TC-R09-01`、公告日 `TC-R11-*` PASSED；**生存偏差 `TC-R12-*` 仍红（F8 未裁）**——不放行、如实保留 |
| F5 | 日内/T+0/涨停买得到 | 未违反 | 未违反 | `TC-R08-03`（T+1 拒绝）、`TC-R08-01`（封板顺延）PASSED |
| F6 | 挑区间切点/软标签入组 | 未违反 | 未违反 | `TC-R15-01/02/03` PASSED；engineer `test_universe.py` 绿 |
| F7 | LLM 改数值 | 未违反 | 未违反 | `grep -rn 'openai\|llm' src/service/backtest src/data_provider/backtest` 空；成本/统计均由独立算式复核 |
| F8 | 越界改文件 | 未违反 | 未违反 | 本 change 全部提交与 `openspec/specs/`、`docs/mrd/` 交集为空（§10.9 命令） |

### 10.6 规格一致性（复验：19 R / 56 Scenario）

- **19/19 Requirement** 有 engineer `test/service/backtest/` 覆盖（映射同 §5 表，未变）。
- **56/56 Scenario** 有 QA 节点（`--collect-only` 56）；本次 **51 PASSED / 5 FAILED**：
  - `TC-R12-01` / `TC-R12-02` / `TC-R12-03` / `TC-R12-04` → F8（provider 协议，t22）
  - `TC-R13-02` → F7（空观测语义，t22）
- 除上述 5 条外，其余 51 条逐条见 §5 表（本次状态以 §10.7 汇总为准）。**未覆盖项**：见 §6（真实全 A 校准、R12 真实名单、R3 跨段入口、KQ-7/KQ-3/KQ-1/KQ-5、多档 liquidity、图表）。

### 10.7 负向与边界用例（复验真实执行）

| # | 场景 | 节点 | 退出码 | 关键输出 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 前复权拒绝 | `test/qa/backtest/test_adjust.py::test_tc_r09_01_qfq_request_rejected` | 0 | `1 passed` | PASSED |
| 2 | 未来函数越界 | `test/qa/backtest/test_no_future_function.py::test_tc_r10_02_future_data_raises` | 0 | `1 passed` | PASSED |
| 3 | 样本外二次 | `test/qa/backtest/test_out_of_sample_burn.py::test_tc_r04_02_second_out_of_sample_request_rejected` | 0 | `1 passed` | PASSED |
| 4 | 缺 K 不可采信 | `test/qa/backtest/test_multi_comparison.py::test_tc_r05_02_missing_k_is_inconclusive` | 0 | `1 passed` | PASSED |
| 5 | 台账篡改 | `test/qa/backtest/test_prereg_ledger.py::test_tc_r02_02_tampered_ledger_row_rejected` | 0 | `1 passed` | PASSED |
| 6 | 封板顺延 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_01_limit_up_seal_defers_to_next_tradable_day` | 0 | `1 passed` | PASSED |
| 7 | T+1 拒绝当日卖 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_03_same_day_sell_rejected_by_t1` | 0 | `1 passed` | PASSED |
| 8 | 停牌跳过 | `test/qa/backtest/test_seal_rollover.py::test_tc_r08_04_suspended_day_skipped` | 0 | `1 passed` | PASSED |
| 9 | 缺 gate 判据 | `test/qa/backtest/test_gates.py::test_tc_r19_01_cannot_enter_shadow_without_backtest` | 0 | `1 passed`（合法边触发 `MissingBacktestConfigError`） | PASSED |
| 10 | 缺 `avg_amount` | `test/service/backtest/test_broker.py::test_missing_avg_amount_reports_gap` | 0 | `1 passed` | PASSED |
| 11 | 缺费率配置 | `test/qa/backtest/test_cost_hand_calc.py::test_tc_r07_03_missing_fee_config_rejected` | 0 | `1 passed` | PASSED |

### 10.8 ruff 基线（复验）

`python -m ruff check .` → **Found 38 errors**（exit 1）：全部为存量基线文件（`scripts/` 5、`src/` 13、`test/` 10 等，非本 change 产物）；本 change 路径（`src/service/backtest/`、`src/data_provider/backtest/`、`src/apps/cli.py`、`test/service/backtest/`、`test/data_provider/backtest/`、`test/apps/test_cli_backtest.py`、`test/qa/backtest/`）**0 命中**。基线 39 → 现 38（本 change 还修掉既有 `src/apps/cli.py` I001）。口径：不修基线、不记失败、不跳过。

### 10.9 复现说明（t20 版）

```bash
git rev-parse HEAD                 # 期望 8c7f855a398b101217f87b24330447c35944b9aa（本次开始时记录、结束时一致）
git status --porcelain             # 期望为空
python -m pytest -q -m "not network and not akshare_legacy"   # 当前 5 failed / 1037 passed（目标 exit 0）
python -m pytest -q test --ignore=test/qa                     # 当前 2 failed / 987 passed（e2e 环境，F10）
python -m pytest -q test/qa/backtest                          # 当前 5 failed / 51 passed
python -m pytest -q test/qa/backtest --collect-only           # 56 collected
python -m ruff check .                                        # 38 errors（本 change 新增 0）
python -m compileall -q src test                              # exit 0
openspec.cmd validate add-backtest-engine --strict            # exit 0
# 越界自检（期望空输出）
git log --format=%H --grep=add-backtest-engine | while read c; do git show --name-only --format='' $c; done | sort -u | grep -E '^openspec/specs/|^docs/mrd/'
git diff --stat ba609a0..HEAD -- src/dao                      # 期望空（F10 证据）
```

### 10.10 复验需要的外部动作（阻塞转「通过」）

1. **architect（t22）** 裁 F7（空观测：`BacktestError` 还是返回不可判定）与 F8（universe `provider` 协议：`load_members(as_of, spec)` + `load_flags(members, as_of)` 的入参/返回形状）；并在 `tasks.md` 附录 A 落 T3 acceptance 原文（F11）。
2. **QA（下一轮 T4-fix-3）** 按裁决补最后 5 条：`test_survivorship_bias.py` 的 spy provider（实现 `load_members`/`load_flags`）与 `TC-R13-02` 的空观测断言（`pytest.raises` 或返回不可判定）。
3. **captain** 冻结 HEAD（F12）后派 T5 复审；预计全量转 exit 0，结论改「通过」。
4. **F10**：2 条 e2e 维持「既有环境偏差」（captain 已裁），重建 e2e 库种子记 `IMPROVEMENTS`，不阻塞本 change。
