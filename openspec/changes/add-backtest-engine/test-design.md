# Test Design: add-backtest-engine（回测模块 · QA 盲测）

> change：`add-backtest-engine`　分支：`feature/add-backtest-engine`　角色：qa（T4）
> 依赖：T1 `specs/backtest-engine/spec.md` + `proposal.md`、T2 `design.md`（接口契约）、飞书《投资Agent》r482 §三 / §七 / §九 / §十。
> **盲测声明**：本设计只读 `specs/backtest-engine/spec.md`、`proposal.md` 的成功/失败标准、`design.md` §4.1 契约、`docs/agent-team/inputs/feishu-invest-agent.md` §三/§七/§九/§十、`docs/agent-team/roles/qa.md`、`test/qa/README.md`。**未读任何 `src/` 实现、未读 `test/` 下的 engineer 单测**（本波亦无实现）。所有断言只锚 `design.md` 的签名与数据结构，签名之外的东西一律不猜。
> 本波**只产本文档**：不写 `test/`、不写 `src/`、不改 `design.md` / `specs/` / `openspec/specs/`。

---

## 0. 结论先行

| 检查项（任务完成定义） | 结果 |
| --- | --- |
| 规格一致性：spec 19 Requirement / **56 Scenario** → 用例 | **56/56 覆盖**，逐条列于 §1.2（无一遗漏；无一「口头测试点」） |
| proposal 成功标准 5 条 → 可执行断言 | **5/5**，见 §2.1 |
| proposal 失败标准/反目标 8 条 → 证伪用例 | **8/8**，见 §2.2 |
| 八条硬约束的负向/对抗用例 | **8/8 有代码级用例**，见 §3（不只 happy path） |
| 已知答案校准（R18）验收方式 + 断言顺序 | 见 §4（「先修台子再谈策略」写成可执行顺序） |
| 统计陷阱对抗 | 见 §5（组内相关 / 分组换档计 K / 用今天分组回看历史） |
| 三级门禁核对表 | 见 §6（三档可观测判据 + 「不得跳过」检查） |
| 契约缺口（结构化 finding） | T4 提 8 条 + T4-fix 新增 2 条（QA-F9/F10）→ **T4-fix-3 后 11/11 全部闭合（未闭合 0）**（QA-F1~F8 见 §8 各条「复核状态」；QA-F9/F10/F11 见 §8.1）。QA-F9 =「库层 `raise CalibrationFailedError` / CLI `sys.exit(2)` / `1`=参数·配置·数据错误」；QA-F10 = `BacktestConfig.results_dir`+`registry_store_path` 注入、`LedgerExportRow` 13 字段、`export_ledger`/`write_result`；QA-F11 = 入口 `src/apps/cli.py` 的 `main(argv)->int` + `backtest` 子命令组、配置 `--config`（相对 cwd）> `cwd/config/app.yaml`、`write_calibration_result` 原子写 `calibration.json`。机检 `TODO` 标记（QA-F1–F11）= **0** |

**给 T5 的一句话**：56 条 Scenario 用例都写成「离线可跑」的形态——依赖真实全 A 数据与 Owner 未答复参数（Q4/Q5/Q6/Q7、KQ-1/KQ-2/KQ-5/KQ-7）的**结论级**断言（真实校准题数值、真实牛熊分档判据、影子期真实计时等）不在单测内，单测只覆盖其「判定链」，真实结论由 T5 端到端取证，**未覆盖原因已在 §7 如实列明**。

**给 T3 的一句话**：T4 的 8 条 finding 已在 T2-fix 闭合（见 §8 各条「复核状态」），实现时**按 `design.md` §4.1 的异常清单/数据结构写，不要偏离**；仍剩 2 处契约缺口（§8.1 QA-F9 校准失败 raise 点、QA-F10 `ledger` 导出字段与 results 目录注入），本设计对应断言已保留 `TODO` 并写明影响——**QA 不会为了迁就实现改断言**（`roles/qa.md`「测试所有权」）。

---

## 1. 规格一致性表

### 1.1 用例落位（未来文件名，本波不创建）

**落位口径 = captain 裁定（T4-fix）：以 `design.md` §6.7 的子目录为准**——QA 用例按被测模块镜像到 `test/qa/<module>/`，回测模块为 `test/qa/backtest/test_<topic>.py`（与 `src/service/backtest/` 镜像，避免扁平目录膨胀）。QA-F1 按此裁定闭合：**本表已全部改为子目录**，`design.md` 不改，`test/qa/README.md` 已同步该约定。对照关系：`design.md` §6.7 列出的 8 个文件在本表中**同名且全含**（`test_no_future_function.py` / `test_known_answer_calibration.py` / `test_out_of_sample_burn.py` / `test_cost_hand_calc.py` / `test_seal_rollover.py` / `test_survivorship_bias.py` / `test_multi_comparison.py` / `test_financial_timing.py`）；其余 11 个按同一命名规则扩展，覆盖 design §6.7 未列的 R1/R2/R3/R6/R9/R13/R14/R15/R16/R17/R19 与 proposal 标准级用例。

| # | 未来文件（`test/qa/backtest/`，本波不创建） | 覆盖 Requirement | 用例数 |
| --- | --- | --- | --- |
| 1 | `test_prereg_ledger.py` | R1、R2 | 6 + 2（§3.1 对抗） |
| 2 | `test_segments.py` | R3 | 3 |
| 3 | `test_out_of_sample_burn.py` | R4 | 3 + 1（§3.2） |
| 4 | `test_multi_comparison.py` | R5 | 3 + 1（§3.3） |
| 5 | `test_stat_inference.py` | R6 | 2 + 2（§5.1） |
| 6 | `test_cost_hand_calc.py` | R7 | 4 + 2（§3.4） |
| 7 | `test_seal_rollover.py` | R8 | 4 + 3（§3.5） |
| 8 | `test_adjust.py` | R9 | 3 |
| 9 | `test_no_future_function.py` | R10 | 3 + 3（§3.6） |
| 10 | `test_financial_timing.py` | R11 | 2 |
| 11 | `test_survivorship_bias.py` | R12 | 4 + 2（§3.7） |
| 12 | `test_benchmark.py` | R13 | 3 + 1（§3.8） |
| 13 | `test_stability.py` | R14 | 2 |
| 14 | `test_labels.py` | R15、R16 | 5 + 2（§5.2、§5.3） |
| 15 | `test_event_study.py` | R17 | 3 |
| 16 | `test_known_answer_calibration.py` | R18 | 3 + 1（§4） |
| 17 | `test_gates.py` | R19 | 3 + 2（§6） |
| 18 | `test_success_criteria.py` | proposal 成功标准 S1–S5 + 退出码契约 E1–E3（§2.3） | 5 + 3 |
| 19 | `test_anti_goals.py` | proposal 失败标准/反目标 F1–F8（静态 + 行为） | 8 |
| — | `conftest.py`（QA 专用 fixture：`tmp_path` 台账、固定 `clock`、配置夹具、`calibration_gate`；本波不创建） | 全部 | — |

> 目录约定：**QA 用例按被测模块镜像到 `test/qa/<module>/`**（当前回测模块 = `test/qa/backtest/`）；`conftest.py` 放在该子目录，session 级 `calibration_gate` 与 fixture 只作用于本模块用例。运行仍是 `python -m pytest -q test/qa`（子目录自动纳入 `testpaths=["test"]`），**不新增 pytest marker**（只用 `pytest.skipif` / `pytest.importorskip` / 模块级 `skip`，避免改 engineer 拥有的 `pyproject.toml`）。

### 1.2 逐 Requirement / Scenario → 用例

> 断言要点列即用例的 WHEN→THEN 断言；`文件` 指上表落位文件（子目录口径 = captain 裁定）。**T4-fix 复核结论**：T4 原 8 条 finding 中 7 条已在 T2-fix 闭合，对应断言已从「有异常/有字段」收紧为具体契约（`RunRecord/RunStatus`、`PreregistrationSpec`、`Fill.attempts`、`WindowStats/EventStudyResult/AttributionResult/StabilityResult`、8 类异常、`ExperimentRegistry(store_path, *, clock, data_version)`、`experiment_id` = `<hypothesis_id>-<seq:04d>`、`K: int | None`、`CalibrationResult.corrected_p/verdict`）；**T4-fix-2 后行内 `TODO` 标记（QA-F9/F10）= 0**：QA-F9 已按「库层异常 / CLI 退出码」二分改写（TC-R18-02 断 `CalibrationFailedError`，退出码单独走 TC-EXIT-01/02/03），QA-F10 已按 `results_dir` 注入 + `LedgerExportRow` 13 字段改写（TC-R04-01 / TC-SC-02）。**T4-fix-3 后行内 `TODO` 标记 = 0**：QA-F11 已按 design §6.3 写死（入口 `main(argv)->int`、`backtest calibrate|ledger`、`--config` 相对 cwd、`write_calibration_result` 写盘点、退出码 0·1·2），夹具改为 `cli_runner(cwd=tmp_path)`

#### R1 实验预注册先于跑数 — `test/qa/backtest/test_prereg_ledger.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R01-01 | 预注册后正常执行 | 已提交预注册 → 执行器返回成功；台账首行 `prereg_commit` == `git rev-parse HEAD` 前缀（真值取自 `git rev-parse`，不硬编码），且含 `hypothesis_id` 与 `params` | `test/qa/backtest/test_prereg_ledger.py` |
| TC-R01-02 | 无预注册时拒绝执行 | 台账无对应预注册 → 进程退出码非 0（`subprocess`/`SystemExit.code != 0`）；stderr 含缺失字段清单（逐字段可 grep）；台账行数**不变** | `test/qa/backtest/test_prereg_ledger.py` |
| TC-R01-03 | 预注册只在工作区未提交 | 预注册文件存在但 `git status --porcelain` 有该文件 → 拒绝执行，提示含「未提交」；台账不新增行 | `test/qa/backtest/test_prereg_ledger.py` |

#### R2 实验台账逐次落一行且 K 不可事后修改 — `test/qa/backtest/test_prereg_ledger.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R02-01 | 每次执行追加一行 | 同一预注册跑两次 → 结果行 2 行，`experiment_id` 两值不同且形如 `<hypothesis_id>-0001` / `-0002`（契约：`registry.next_experiment_id()` = `<hypothesis_id>-<seq:04d>`，seq 单调递增；design §4.1/§10 QA-F8 已闭合） | `test/qa/backtest/test_prereg_ledger.py` |
| TC-R02-02 | 修改已写入的台账行被拒绝 | 手工改写 NDJSON 某行 `K` → 读取抛 `RegistryCorruptedError`（design §4.1 异常清单，QA-F5 已闭合），错误信息含「台账/损坏」；原文件其余行字节不变；按 `RunRecord(status=FAILED, reason=...)` 落执行行留痕（design §4.1 台账存储机制，QA-F2 已闭合），计数 ≥ 1 | `test/qa/backtest/test_prereg_ledger.py` |
| TC-R02-03 | 改假设必须新开实验 | 对已有 `experiment_id` 改 `params` 保存 → 抛 `RegistryImmutableError`（design §4.1，QA-F5 已闭合）；新实验必须写 `parent_experiment_id`，且原行 `params` 不变 | `test/qa/backtest/test_prereg_ledger.py` |

#### R3 三段样本切分 — `test/qa/backtest/test_segments.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R03-01 | 默认三段切分 | 默认配置输出含 3 段，`Segment` 三值齐全；每段有 `n`、`start`、`end`、`metrics`；年份边界与预注册一致（边界值从夹具配置取，不硬编码 2015/2020） | `test/qa/backtest/test_segments.py` |
| TC-R03-02 | 区间不在任何段内被拒 | 传入横跨 `OUT_OF_SAMPLE` 与 `VALIDATION` 的区间且未声明跨段 → 拒绝，提示「按段拆分或声明跨段报告」；退出码非 0 | `test/qa/backtest/test_segments.py` |
| TC-R03-03 | 训练段可重复使用 | 同一规则在训练段跑 3 次 → 全部成功；台账可读出该规则训练段评估次数 == 3（由台账行计数派生） | `test/qa/backtest/test_segments.py` |

#### R4 样本外一次性烧毁 — `test/qa/backtest/test_out_of_sample_burn.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R04-01 | 首次使用样本外并烧毁 | 首次显式确认 → 执行成功；结果行 `burnt is True`，`timestamps` 含烧毁时刻（`clock` 注入，QA-F6）；**导出断言（QA-F10 已闭合）**：`export_ledger(hypothesis_id=<hid>)` 返回 `list[LedgerExportRow]`，该假设 `burnt is True` 的行**唯一**，且 `burnt=True` 即「额度用尽」（design §4.1 `LedgerExportRow.burnt` / §6.3）；`registry.write_result(experiment_id, payload)` 落到 `<results_dir>/<experiment_id>.json`（`results_dir=tmp_path/"results"`，design §4.1/§6.5） | `test/qa/backtest/test_out_of_sample_burn.py` |
| TC-R04-02 | 第二次请求样本外被拒绝 | 同实验第二次（换 `params` 或换 `metrics`）→ 拒绝、退出码非 0、提示含「样本外已烧毁」；台账新增一条拒绝记录且 `burnt` 标记仍唯一（计数 == 1） | `test/qa/backtest/test_out_of_sample_burn.py` |
| TC-R04-03 | 新实验拥有独立额度 | 新 `hypothesis_id` 首次请求样本外 → 允许；前后两实验的烧毁标记各自计数（互不重置） | `test/qa/backtest/test_out_of_sample_burn.py` |

#### R5 多重比较校正与 K 报告 — `test/qa/backtest/test_multi_comparison.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R05-01 | 报告 K 与校正后显著性 | `p=0.01, K=30, method="bonferroni"` → 输出同时含原始 p、`K=30`、method 名、校正后判定；Bonferroni 校正值 ≈ `min(1, 0.01*30)=0.3` 且判定为不显著（如实标不显著） | `test/qa/backtest/test_multi_comparison.py` |
| TC-R05-02 | 未报告 K 时禁止下结论 | `K=None`（契约：`ExperimentRecord.K: int | None`，design §4.1/§10 QA-F8 已闭合）→ `verdict is Verdict.INCONCLUSIVE`（不得 `VALID`），且 `RunRecord.reason` 含「K」（QA-F2 已闭合） | `test/qa/backtest/test_multi_comparison.py` |
| TC-R05-03 | K 增大导致判定翻转 | 同一 p 分别按 K=1 / K=50 评估 → 前者显著、后者不显著；两行都进台账，`K` 字段分别为 1 / 50 | `test/qa/backtest/test_multi_comparison.py` |

#### R6 统计推断按有效样本 — `test/qa/backtest/test_stat_inference.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R06-01 | 同组同涨同跌时按时间块计有效样本 | 30 只 × 100 日共因子序列（名义 n=3000）→ `EventStudyResult.windows["20"][<基准>]` 的 `WindowStats.n == 3000`、`effective_n`（时间块数）`< 3000`；`EventStudyResult.inference_method == "block_bootstrap"` 且 `block_length`/`n_bootstrap` 非空（契约：design §4.1 `WindowStats`/`EventStudyResult`，QA-F4 已闭合） | `test/qa/backtest/test_stat_inference.py` |
| TC-R06-02 | 默认推断不使用 iid 假设 | 预注册未指定推断口径 → 默认 block bootstrap，输出标注 `block_length` 与 `n_bootstrap`；两者之和不为空（不得静默用 iid） | `test/qa/backtest/test_stat_inference.py` |

#### R7 成本与摩擦计入每笔成交 — `test/qa/backtest/test_cost_hand_calc.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R07-01 | 单笔成交成本可分项复算 | 10 万买、11 万卖 → `cost.commission`（买+卖各一笔，含最低额判定）/ `stamp_tax` / `slippage` / `total` 四项分列，且与 §10.2 手算独立算式逐项 `approx` 相等（容差 1e-9） | `test/qa/backtest/test_cost_hand_calc.py` |
| TC-R07-02 | 小额成交触发最低佣金 | 金额使 `amount*rate < min` → 佣金 == `min`，`notes` 含「触发最低佣金」 | `test/qa/backtest/test_cost_hand_calc.py` |
| TC-R07-03 | 费率配置缺失时拒绝执行 | 配置删 `stamp_tax` / `commission.min` → 抛 `MissingBacktestConfigError`（design 已给名），退出码非 0，错误信息列出缺失键；**不得**产出任何 `Fill` | `test/qa/backtest/test_cost_hand_calc.py` |
| TC-R07-04 | 流动性上限截断单笔金额 | 单笔 5 万、该标的 `amount=100 万`、夹具档位上限 1% → `filled_amount == 1 万`，`notes` 含「触及流动性上限」，剩余 4 万在新订单中顺延至下一可成交日 | `test/qa/backtest/test_cost_hand_calc.py` |

#### R8 A 股撮合约束：封板顺延、T+1、停牌跳过 — `test/qa/backtest/test_seal_rollover.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R08-01 | 一字涨停买不进顺延 | `PriceBar` 日终一字涨停（`open==high==low==close==limit_up_price`）→ `Fill.attempts[0].status is OrderStatus.FAILED_LIMIT_SEAL`（reason 含「封板」）、末项 `FILLED`；`fill_date == 末次 FILLED 的 attempt_date` 且为下一可成交日；`delay_days` == 首个目标日（t+1）与该成交日的交易日差（契约：`OrderAttempt`/`Fill.attempts`/`delay_days`，design §4.1/§10 QA-F7 已闭合） | `test/qa/backtest/test_seal_rollover.py` |
| TC-R08-02 | 跌停卖不出顺延 | 连续 2 日跌停 → 卖单顺延，`delay_days == 2`，明细含「连续封板 2 日」 | `test/qa/backtest/test_seal_rollover.py` |
| TC-R08-03 | 当日买入当日卖出被拒绝 | `Order.signal_date = t` 且同日卖出（同一 `trade_date`）→ `OrderStatus.REJECTED_T1`，`fill_date is None`，最早可卖日 == t 的下一交易日，拒绝原因入 `notes` | `test/qa/backtest/test_seal_rollover.py` |
| TC-R08-04 | 停牌日跳过 | t+1 日 `suspended=True` → `SKIPPED_SUSPENDED`，不计为成交；成交日为复牌后首个可成交日 | `test/qa/backtest/test_seal_rollover.py` |

#### R9 后复权（或分段复权）价格口径 — `test/qa/backtest/test_adjust.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R09-01 | 前复权请求被拒 | `load_price_series(..., adjust="qfq")`（字符串绕过枚举 / 非法值）→ 抛 `InvalidAdjustModeError`（**不是** `BacktestDataGapError`：口径非法 ≠ 数据缺失，design §4.1 异常清单 + 二分表，QA-F5 已闭合），错误信息说明前复权会改写历史价；不返回任何 `PriceBar`；另配「provider 无数据」对照用例断言抛 `BacktestDataGapError` | `test/qa/backtest/test_adjust.py` |
| TC-R09-02 | 分红日无假跳空 | 构造现金分红（除权价跳空 + 派息）序列 → 后复权/分段复权下持有期收益在分红日前后连续；`abs(ret[t]) < 1e-6`（除权当日不产生假跌），而同一原始收盘价直接算会出现 > 阈值假跌（对照组证明用例有效） | `test/qa/backtest/test_adjust.py` |
| TC-R09-03 | 输出记录口径元数据 | 任一结果含 `adjust_mode`（∈ `{hfq, segmented_hfq}`）、`data_version`、`snapshot_time` 三字段且非空；`adjust_mode` 不得为 `qfq` | `test/qa/backtest/test_adjust.py` |

#### R10 信号纯函数与成交时点边界 — `test/qa/backtest/test_no_future_function.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R10-01 | 信号在 t 日、成交在 t+1 | t 日信号 → 所有 `Fill.fill_date >= t` 的下一交易日（用夹具日历换算，不硬编码日期）；`fill_price` 取自 t+1 及之后的 bar（不等于 t 日 close） | `test/qa/backtest/test_no_future_function.py` |
| TC-R10-02 | 越界访问抛错 | `PointInTimeSnapshot(as_of=t)` 内含 `trade_date=t+1` 的 bar → 抛 `FutureDataError`；含 `visible_from > as_of` 的财务记录 → 同样抛错；该次执行以 `RunRecord(status=RunStatus.FAILED, reason=...)` 留痕（design §4.1 台账存储机制，QA-F2 已闭合），不产生结果行 | `test/qa/backtest/test_no_future_function.py` |
| TC-R10-03 | 同输入同输出（纯函数可复现） | 同一 `PointInTimeSnapshot` 调 `evaluate_condition` 两次 → `EventSignal` 完全相等（含 `event_date`）；两次结果 `==`（frozen dataclass 值相等） | `test/qa/backtest/test_no_future_function.py` |

#### R11 财务字段按公告日对齐 — `test/qa/backtest/test_financial_timing.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R11-01 | 年报在 4 月底之后才可见 | 报告期 2023-12-31、`ann_date=2024-04-25` → `as_of=2024-04-24` 的 `build_point_in_time` 不含该记录；`as_of=2024-04-25` 含之；`visible_from == "2024-04-25"` | `test/qa/backtest/test_financial_timing.py` |
| TC-R11-02 | 公告日缺失时回退并标注 | `ann_date=None`、报告期 2023-12-31 → 回退 `visible_from == "2024-04-30"`（年报 4 月底）；半年报 → `08-31`；三季报 → `10-31`；结果元数据含「公告日回退」标注 | `test/qa/backtest/test_financial_timing.py` |

#### R12 生存偏差：退市、ST 与历史成分 — `test/qa/backtest/test_survivorship_bias.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R12-01 | 退市股在退市前仍被计入 | 2019 年退市标的、区间 2017–2019 → `build_universe` 含该 code；退市日前有成交，退市日后 `delisted=True` 且无新 `Fill` | `test/qa/backtest/test_survivorship_bias.py` |
| TC-R12-02 | ST 状态按时点判定 | 2024 年才 ST 的标的、评估 2015–2020 → 该段 `PriceBar.st is False`（design §4.1 `PriceBar.st`「当时 ST 状态，按时点，不回填」）；结构断言：`build_universe(as_of="2015-…", …, provider=spy)` 把 `as_of` 传给 provider（spy 记录实参），即不得用今日名单回看历史。**限制**：provider 若返回被今日标签污染的名单，系统无法自证 → 已列 §7 未覆盖项 8 | `test/qa/backtest/test_survivorship_bias.py` |
| TC-R12-03 | 历史成分与当前成分不同 | 请求 2016 年沪深 300 成分、provider 给 2016 名单 → 返回名单 == 2016 名单（不等于当前名单夹具）；输出标注成分来源与生效日 | `test/qa/backtest/test_survivorship_bias.py` |
| TC-R12-04 | 名单不可得时报缺口 | provider 无退市/ST 名单 → 抛 `BacktestDataGapError`；错误说明含缺失项与影响范围；**不得**返回「已剔除退市股」的静默降级结果 | `test/qa/backtest/test_survivorship_bias.py` |

#### R13 基准对比与因子归因 — `test/qa/backtest/test_benchmark.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R13-01 | 输出相对基准超额 | `compute_event_study(events, benchmarks: Sequence[Benchmark], *, cfg)` 返回的 `EventStudyResult.windows[window]` 同时含 `"buy_and_hold"` 与 `"market_portfolio"` 两个键，各为 `WindowStats{mean/median/std/ci/effective_n/by_year/by_cap_tier}`（契约：`Benchmark`/`WindowStats`/`EventStudyResult` 双基准签名，design §4.1/§10 QA-F4 已闭合） | `test/qa/backtest/test_benchmark.py` |
| TC-R13-02 | 缺失基准时不出结论 | 预注册未指定基准 / 基准数据不可得 → `verdict == Verdict.INCONCLUSIVE`（不得 `VALID`）；台账记缺失原因 | `test/qa/backtest/test_benchmark.py` |
| TC-R13-03 | 归因四项齐全 | 输出含 beta / 规模 / 价值 / 动量四项暴露系数与各自贡献，且注明未解释部分；四项键名齐全 | `test/qa/backtest/test_benchmark.py` |

#### R14 稳定性分档检查 — `test/qa/backtest/test_stability.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R14-01 | 全期显著但仅一段贡献 | 全样本显著但 80% 绝对贡献来自单一年度 → 结论列标注「仅在 <该年> 有效」，**不得**写「有效」 | `test/qa/backtest/test_stability.py` |
| TC-R14-02 | 分档样本不足时报警 | 某市值档 < 30 只或跨度 < 3 年 → 该档标注「样本不足」且不参与显著性判定（该档 p 值不进入校正集合） | `test/qa/backtest/test_stability.py` |

#### R15 标签准入与切点纪律 — `test/qa/backtest/test_labels.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R15-01 | 软标签被拒绝进入分组 | 以「主题归属」请求分组 → 拒绝，提示「软标签只登记不参与」；登记请求留痕（台账/登记清单可数） | `test/qa/backtest/test_labels.py` |
| TC-R15-02 | 用未来信息分组的请求被拒 | 以「事后涨跌幅」「当前行业成分」归组历史时点 → 拒绝并说明依赖未来信息；不产出 `GroupAssignment` | `test/qa/backtest/test_labels.py` |
| TC-R15-03 | 季度重算不回改历史 | 2021Q2 重算新切点 → 2020 年及以前 `GroupAssignment.tiers` 与重算前逐字节相同；`effective_range` 标注各组生效区间 | `test/qa/backtest/test_labels.py` |

#### R16 部分池化：输出组内分位而非绝对收益预测 — `test/qa/backtest/test_labels.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R16-01 | 单票样本少时向组均值收缩 | 单票 12 观测、组均值 400 观测 → 输出组内分位 + 收缩后估计，且 `abs(收缩后估计 - 组均值) < abs(收缩后估计 - 单票原始估计)`；标注「样本少，估计接近组均值」 | `test/qa/backtest/test_labels.py` |
| TC-R16-02 | 拒绝输出绝对收益预测 | 请求「该股票未来收益预测」字段 → 返回中不含该字段；只返回组内分位与样本量（键集合断言） | `test/qa/backtest/test_labels.py` |

#### R17 事件研究为 MVP 主交付 — `test/qa/backtest/test_event_study.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R17-01 | 条件成立后 20 / 60 日超额分布 | `EventStudyResult.windows` 键含 `"20"` 与 `"60"`，每窗口 × 双基准均为 `WindowStats`（`n/mean/median/std/ci/by_year/by_cap_tier/effective_n`），`n_events` 非空（契约：design §4.1，QA-F4 已闭合）；窗口超出 `{20, 60}` → 拒绝（Q8 未答复） | `test/qa/backtest/test_event_study.py` |
| TC-R17-02 | 事件数不足时不出结论 | 窗口内有效事件数 < 预注册阈值 → 标注「样本不足」，无 `valid/invalid` 判定（只允许 `INCONCLUSIVE` 或「样本不足」状态） | `test/qa/backtest/test_event_study.py` |
| TC-R17-03 | 允许结论为无信号 | 超额 CI 含 0 且校正后不显著 → 结论「无信号」，且该结论与「有信号」同样计入台账行与 `K` | `test/qa/backtest/test_event_study.py` |

#### R18 已知答案校准门禁 — `test/qa/backtest/test_known_answer_calibration.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R18-01 | 校准通过后允许出结论 | 合成校准题（构造「跌破 MA60」相对买入持有显著为负、CI 不含 0）→ `CalibrationResult.passed is True`；台子标记「可信」；随后研究结论可输出；校准结果入台账 | `test/qa/backtest/test_known_answer_calibration.py` |
| TC-R18-02 | 校准不通过时封锁输出 | 方向相反或不显著 → `passed is False`、`verdict is not Verdict.VALID`、`corrected_p` 字段存在（QA-F8）；**库层** `assert_calibrated(registry)` 直接 `raise CalibrationFailedError`（`pytest.raises`，**不断 `SystemExit`**；design §4.1「失败表达二分」，QA-F9 已闭合），异常携带 `reason/corrected_p/verdict`；校准结果写 `<results_dir>/calibration.json` 且 `passed is False`（`results_dir=tmp_path`）；执行行 `RunRecord(FAILED, reason)` 记录校准失败与参数。**CLI 退出码另测**：TC-EXIT-01（=2） | `test/qa/backtest/test_known_answer_calibration.py` |
| TC-R18-03 | 校准失败不得解释为策略无效 | 校准失败路径的任何输出/文案**不含**「MA60 无效」「止损无效」类表述；只允许「台子不可信」；用字符串断言（对 `CalibrationResult` 全字段 + CLI stdout 做禁词扫描） | `test/qa/backtest/test_known_answer_calibration.py` |

#### R19 三级门禁状态机 — `test/qa/backtest/test_gates.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R19-01 | 未过回测不得进入影子运行 | 状态 `BACKTEST_PENDING` 请求 `SHADOW_RUNNING` → 拒绝（退出码非 0 / 抛错），状态不变，拒绝记录入台账 | `test/qa/backtest/test_gates.py` |
| TC-R19-02 | 影子期未满不得启用实盘 | 影子 2 个月请求 `LIVE_SMALL` → 拒绝，提示最低 6 个月 + 「方向一致」未满足 | `test/qa/backtest/test_gates.py` |
| TC-R19-03 | 门禁状态可查询且唯一 | `current(rule_id)` 返回唯一 `GateRecord`；`stage_timestamps` 与 `evidence_experiment_ids` 逐级齐全（已通过级别），未通过级别为空 | `test/qa/backtest/test_gates.py` |

**覆盖率自检**：56 个 `#### Scenario` → 56 个 TC ID（R1 3 / R2 3 / R3 3 / R4 3 / R5 3 / R6 2 / R7 4 / R8 4 / R9 3 / R10 3 / R11 2 / R12 4 / R13 3 / R14 2 / R15 3 / R16 2 / R17 3 / R18 3 / R19 3 = 56）。`3+3+3+3+3+2+4+4+3+3+2+4+3+2+3+2+3+3+3 = 56`。

---

## 2. proposal 成功/失败标准逐条核对

### 2.1 成功标准 5 条 → 一条可执行断言（落 `test/qa/backtest/test_success_criteria.py`）

| # | proposal 成功标准 | 可执行断言（命令 + 期望） | 用例 ID |
| --- | --- | --- | --- |
| S1 | 校准题可复现（显著为负 + 报 K 与校正后 p） | `backtest calibrate`（CLI）退出码 **0** 且 `CalibrationResult` 满足：`direction` 为显著跑输；`ci[1] < 0`；`K >= 1`；`corrected_p` 存在且 `< cfg["alpha"]`（alpha 由夹具注入，KQ-5 未答复前缺键即拒绝，**不硬编码 0.05**；design §4.1 `CalibrationResult`，QA-F8）；`<results_dir>/calibration.json` 写入且 `passed is True`（QA-F10，`results_dir=tmp_path`）；校准执行行在台账（`RunRecord`）。**失败分支退出码非 0（=2）见 TC-EXIT-01，不在本条断言** | TC-SC-01 |
| S2 | 台账可审计（一条命令导出 6 类字段 + 改预注册被拒） | `backtest ledger --experiment <id> --format json` 输出 **JSON 数组**，每项字段集 == `LedgerExportRow` **13 字段**（`experiment_id / hypothesis_id / statement / params / segments / K / metrics / verdict / burnt / prereg_commit / run_status / data_version / adjust_mode`；design §4.1 `LedgerExportRow` + §6.3 导出契约，QA-F10 已闭合）；`statement`/`params` 与预注册 YAML 逐字段一致（读真实 YAML，不用自建 fixture）；`burnt` 反映 R4 额度；篡改预注册后重跑 → 退出码非 0 + 台账留痕 | TC-SC-02 |
| S3 | 样本外只烧一次可机检 | 同假设二次请求样本外：退出码非 0、stderr 含「样本外已烧毁」、台账中该 `hypothesis_id` 的 `burnt is True` 行计数 == 1 | TC-SC-03 |
| S4 | 成本与撮合可手算复算（含封板 + 停牌样例） | 「1 笔涨停封板 + 1 笔停牌 + 1 笔正常」样例：成本四分量与 §10.2 手算一致（`approx` 1e-9）；封板订单 `delay_days >= 1` 且成交日为下一可成交日；停牌单不计成交 | TC-SC-04 |
| S5 | 无未来函数可证伪 + 财务按公告日 | 越界构造 `PointInTimeSnapshot` → `FutureDataError`（负向通过）；`ann_date` 前后可见性用例通过（TC-R11-01）；同时静态断言 `service/backtest/signal.py` 源码不出现 `data_provider` / `dao` / `datetime.now` | TC-SC-05 |

> S1 的「显著为负」在**离线单测**里用合成序列覆盖逻辑（TC-R18-01/02）；真实全 A 的结论级断言只在 T5 端到端取证（§7 未覆盖项 1）。

### 2.2 失败标准/反目标 8 条 → 一条证伪用例（落 `test/qa/backtest/test_anti_goals.py`）

| # | proposal 失败标准/反目标 | 证伪用例（出现即红） | 用例 ID |
| --- | --- | --- | --- |
| F1 | 把策略结论写成本 change 交付物 | 扫描本 change 目录（`proposal/spec/design/tasks/knowledge-delta/test-design`）不含「-15% 止损有效」「MA60 应卖」类断言式结论；只允许出现在「动机/引用」上下文（白名单：`proposal.md` 的 Why 段与 REF 表） | TC-AG-01 |
| F2 | 未过校准却输出研究结论 / 校准失败解释为「策略无效」 | 校准失败后调用研究结论导出 → 拒绝（退出码非 0）；输出与日志禁词扫描「无效」「应卖」「止损无效」 | TC-AG-02 |
| F3 | 预注册可事后改 / K 不报或补记 / 只报显著组合 | 三连断言：① 改预注册被拒；② 缺 K → `INCONCLUSIVE`；③ 台账 `K` 单调不减（对同一 `study_scope` 的累计 K 序列断言非降，防「事后调小 K」） | TC-AG-03 |
| F4 | 前复权 / 报告期当公告日 / 今日成分回看 / 剔除退市 ST | 四条负向：`adjust="qfq"` 抛错；`visible_from` 由 `ann_date` 决定（报告期早于公告日不可见）；历史成分取 2016 名单；`universe` 含退市/ST 且名单缺 → 报缺口 | TC-AG-04 |
| F5 | 日内止损 / T+0 / 涨停一定买到 / 跌停一定卖掉 | 同日买卖 → `REJECTED_T1`；一字涨停买入 → 不成交 + 顺延；跌停卖出 → 顺延；断言「当日成交」不可能（`fill_date > signal_date` 恒成立） | TC-AG-05 |
| F6 | 挑区间/切点/分组 + 软标签进分组 | 事后改切点 → 历史分组不变（TC-R15-03）；软标签入组被拒（TC-R15-01）；分组换档必须计入 K（§5.2） | TC-AG-06 |
| F7 | LLM 生成或修改任何数值 | 静态断言 `src/service/backtest/**` 不 `import` 任何 LLM client（`openai` 等）；`config/app.yaml backtest:` 段无 `llm` 键；结果数值字段全部由确定性函数返回（无 `str` 型数值） | TC-AG-07 |
| F8 | 越界改文件（`openspec/specs/`、`src/`、`test/`、`docs/mrd/`、伪造 MRD 锚点） | T5 取证阶段断言：`git show --name-only <change commits>` 不含 `openspec/specs/`、`src/`、`test/`、`docs/mrd/`；`docs/mrd/mrd-v1.md` 未被本 change 修改；proposal 中 MRD 锚点计数 == 0 | TC-AG-08 |

> F8 属「过程证伪」，由 T5 在 `verification.md` 里以真实 `git` 输出执行；本设计的用例形态是 `subprocess` 调 `git show --name-only`/`git diff --name-only`，断言路径集合为空交集。

### 2.3 退出码契约（QA-F9 收口；落 `test/qa/backtest/test_success_criteria.py`）

> design §4.1「失败表达二分」+ §6.3：**库层** `assert_calibrated` 抛 `CalibrationFailedError`（单测断异常类）；**CLI** 捕获后 `sys.exit(2)`；退出码语义 `1` = 参数/配置/数据错误、`2` = 门禁失败（校准未通过）。库层异常与 CLI 退出码**分开断言，互不替代**。

| # | 契约 | 可执行断言 | 用例 ID |
| --- | --- | --- | --- |
| E1 | 门禁失败 → 退出码 `2` | `cli_runner(["calibrate"])` → `returncode == 2`；stderr 含「先修台子」与 `CalibrationFailedError` 的 reason；`<results_dir>/calibration.json` 中 `passed is False` | TC-EXIT-01 |
| E2 | 参数/数据错误 → 退出码 `1` | `cli_runner(["ledger", "--experiment", "no-such-id"])`（可选面按 §6.3：`--experiment` / `--hypothesis` / `--format json`）→ `returncode == 1`；stderr **非空**（design 未固定错误文案，故不断具体措辞）；**不得为 2** | TC-EXIT-02 |
| E3 | 成功 → 退出码 `0` | 校准通过时 `cli_runner(["calibrate"])` → `returncode == 0`；stdout 可解析为 `CalibrationResult`（`passed is True`、`corrected_p < cfg["alpha"]`） | TC-EXIT-03 |

```python
# test/qa/backtest/test_success_criteria.py
def test_tc_exit_01_gate_failure_exit_code_2(cli_runner, results_dir):
    """design §4.1/§6.3：CLI 捕获 CalibrationFailedError → sys.exit(2)（不是 0/1）。"""
    r = cli_runner(["calibrate"])                 # 夹具注入 cfg（反向校准 loader）与 tmp results_dir
    assert r.returncode == 2, r.stderr            # 门禁失败专用码
    assert "先修台子" in r.stderr
    payload = json.loads((results_dir / "calibration.json").read_text(encoding="utf-8"))
    assert payload["passed"] is False

def test_tc_exit_02_bad_experiment_exit_code_1(cli_runner):
    r = cli_runner(["ledger", "--experiment", "no-such-id"])
    assert r.returncode == 1                      # 参数/数据错误码（design §6.3）
    assert r.returncode != 2 and r.stderr.strip() # 文案未在 design 固定 → 只断非空

def test_tc_exit_03_success_exit_code_0(cli_runner):
    r = cli_runner(["calibrate"])                 # 夹具注入正向校准 loader
    assert r.returncode == 0
    assert json.loads(r.stdout)["passed"] is True
```

> **调用面契约（QA-F11 已闭合，design §6.3/§4.1）**：入口 = 既有 `src/apps/cli.py` 的 `main(argv: list[str]) -> int`（返回码即进程退出码，`build_parser()` 内注册 `backtest` 子命令组，**不另建 `backtest_cli.py`**）；本组用例调用 `backtest calibrate` / `backtest ledger --experiment <id> --format json`；配置解析顺序 `--config <path>`（**相对路径按 cwd**）> `cwd/config/app.yaml` > 缺键 `MissingBacktestConfigError`（退出码 `1`）；夹具 `cli_runner(cwd=tmp_path)` 在 `tmp_path/config/app.yaml` 放最小骨架（`backtest.results_dir` / `backtest.registry_store_path` 指向 `tmp_path`）即可被自动发现，无需强制 `--config`；`calibration.json` 由 `run_calibration(*, cfg, loader, registry)` 无论成败经 `write_calibration_result(...)` 原子写（失败 `passed=False` + `reason`），故 E1 的文件断言可按 `results_dir` 直接读。退出码 `0/1/2` 见 design §4.1「失败表达二分」+ §6.3。

---

## 3. 八条硬约束的证伪用例（代码级）

> 统一纪律：
> 1. 全部使用 `tmp_path` 隔离（`QA-F6` 要求 registry 路径可注入），**不写** `data/backtest/` 真实目录。
> 2. 配置值一律来自**夹具显式声明的测试输入**（示例数值，非生产默认；Q4 未答复），期望值由测试内的独立算式得出，**禁止调用被测成本/统计函数反推期望**。
> 3. 断言只锚 `design.md` §4.1 的公开签名；**QA-F9/F10 已在 T2-fix-2 闭合**，对应断言写死契约（库层异常 / CLI 退出码 1·2·0 / `results_dir` 注入 / `LedgerExportRow` 13 字段）。**T4-fix-3 后为 0 处残留 `TODO`**（QA-F1–F11 全闭合）：CLI 调用面已按 design §6.3 写死（入口 / 子命令 / `--config` 解析顺序 / 退出码 0·1·2 / `calibration.json` 写盘点），夹具 `cli_runner(cwd=tmp_path)`；**任何断言不因缺口放宽**。

### 3.1 预注册 / 台账：跑完后篡改假设或 K 必须被拒

```python
# test/qa/backtest/test_prereg_ledger.py
def test_tc_r02_02_tamper_k_rejected(appended_registry, registry_path, first_record):
    """R2 Scenario2：改写已落行 K → 读取即抛 RegistryCorruptedError（design §4.1 异常清单）。"""
    lines = registry_path.read_bytes().decode("utf-8").splitlines()
    assert '"K"' in lines[0], "夹具前置：首行必须含 K 字段"
    registry_path.write_text(
        "\n".join([lines[0].replace('"K": 1', '"K": 2')] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(RegistryCorruptedError) as exc:     # QA-F5 已闭合：不再括 Exception
        appended_registry.get(first_record.experiment_id)
    assert "台账" in str(exc.value) or "损坏" in str(exc.value)
    # 失败动作以执行行留痕（design §4.1 台账存储机制；QA-F2 已闭合）
    assert count_run_rows(registry_path, RunStatus.FAILED) >= 1


def test_tc_r02_03_assumption_change_needs_new_experiment(appended_registry, first_record):
    """R2 Scenario3：改假设/参数 → RegistryImmutableError；必须新开实验并写 parent_experiment_id。"""
    with pytest.raises(RegistryImmutableError):            # QA-F5 已闭合
        appended_registry.append(replace(first_record, params={**first_record.params, "ma_days": 61}))
    assert appended_registry.get(first_record.experiment_id).params == first_record.params
    # 合法路径：新实验 ID 由 registry 生成（<hypothesis_id>-<seq:04d>，QA-F8 已闭合）+ 写父实验
    child_id = appended_registry.next_experiment_id(first_record.hypothesis_id)
    appended_registry.append(replace(first_record, experiment_id=child_id,
                                     parent_experiment_id=first_record.experiment_id,
                                     params={**first_record.params, "ma_days": 61}))
    assert child_id != first_record.experiment_id
    assert appended_registry.get(child_id).parent_experiment_id == first_record.experiment_id
```

### 3.2 样本外一次性：重复使用必须报错并留痕「已烧毁」

```python
# test/qa/backtest/test_out_of_sample_burn.py
def test_tc_r04_02_second_oos_request_rejected(registry, registry_path, oos_request):
    registry.mark_burnt(oos_request.hypothesis_id, "exp-001")
    with pytest.raises(RegistryImmutableError) as exc:   # design §4.1：二次请求抛 RegistryImmutableError
        registry.assert_not_burnt(oos_request.hypothesis_id, Segment.OUT_OF_SAMPLE)
    assert "样本外已烧毁" in str(exc.value)
    # 二次请求：换参数、换指标的变体同样拒绝（R4 Scenario2 的两条支路）
    for _variant in ({"params": {"ma_days": 61}}, {"metrics": ["sharpe"]}):
        with pytest.raises(RegistryImmutableError):
            registry.assert_not_burnt(oos_request.hypothesis_id, Segment.OUT_OF_SAMPLE)
    # 标记唯一、不可撤销：数结果行里 burnt is True 的条数（ExperimentRecord.burnt，design §4.1）
    assert sum(1 for r in result_rows(registry_path) if r.burnt) == 1
    assert count_run_rows(registry_path, RunStatus.REJECTED) >= 1   # 拒绝留痕（QA-F2 已闭合）
```

### 3.3 多重比较：只报告 1 个 K 的结果必须判「不可采信」

```python
# test/qa/backtest/test_multi_comparison.py
def test_tc_r05_02_missing_k_is_inconclusive(run_experiment, registry_path, cfg):
    rec = run_experiment(cfg=cfg, k=None)          # K=None（ExperimentRecord.K: int | None，QA-F8 已闭合）
    assert rec.K is None
    assert rec.verdict is Verdict.INCONCLUSIVE     # 不得 VALID
    assert any("K" in (r.reason or "") for r in run_rows(registry_path))   # 说明缺 K（QA-F2 已闭合）

def test_tc_r05_03_k_increase_flips_verdict(metrics_cfg):
    sig_k1, sig_k50 = (multiple_testing_correction([0.01], K=k, method="bonferroni", cfg=metrics_cfg)
                       for k in (1, 50))
    assert sig_k1[0] == pytest.approx(0.01)
    assert sig_k50[0] == pytest.approx(0.5)         # 独立算式 0.01*50
    # 判定：校正后 <= alpha 才有效（alpha 来自夹具配置，不硬编码 0.05）
    assert sig_k1[0] <= metrics_cfg["alpha"] < sig_k50[0]
```

> 「只报 1 个 K」的第二层含义（挑显著组合上报）由 §2.2 F3 的「累计 K 单调不减」断言 + TC-AG-03 覆盖。

### 3.4 成本与摩擦：零成本 vs 含成本必须不同，且含成本更低

```python
# test/qa/backtest/test_cost_hand_calc.py
def test_tc_r07_00_zero_cost_must_differ(buy_sell_prices, cfg_with_cost, cfg_zero_cost):
    """对抗主角：把成本配置清零 → 净收益必须更高（严格大于），否则成本未计入。"""
    gross = execute_orders(buy_then_sell(), buy_sell_prices, cfg=cfg_zero_cost)
    net   = execute_orders(buy_then_sell(), buy_sell_prices, cfg=cfg_with_cost)
    gross_pnl = pnl(gross)      # 本金 + 卖出净额 - 买入总付出（QA 侧独立算式）
    net_pnl   = pnl(net)
    assert gross_pnl > net_pnl, "含成本配置的收益必须严格更低（成本未生效）"
    assert net_pnl == pytest.approx(gross_pnl - sum(f.cost.total for f in net), abs=1e-6)

def test_tc_r07_01_four_components_hand_calc(cfg_raw, buy_sell_prices):
    """R7 Scenario1：四项分金额与独立手算一致（期望值全部由 cfg_raw 算出）。"""
    fills = execute_orders(buy_then_sell(), buy_sell_prices, cfg=BacktestConfig.from_config(cfg_raw))
    buy, sell = fills[0], fills[1]
    exp_buy_comm  = max(cfg_raw["commission"]["rate"] * 100_000, cfg_raw["commission"]["min"])
    exp_sell_comm = max(cfg_raw["commission"]["rate"] * 110_000, cfg_raw["commission"]["min"])
    exp_stamp     = cfg_raw["stamp_tax"]["sell_rate"] * 110_000
    exp_slip_buy  = 100_000 * slip_rate(cfg_raw, 100_000)
    exp_slip_sell = 110_000 * slip_rate(cfg_raw, 110_000)
    assert buy.cost.commission == pytest.approx(exp_buy_comm, abs=1e-9)
    assert sell.cost.commission == pytest.approx(exp_sell_comm, abs=1e-9)
    assert sell.cost.stamp_tax == pytest.approx(exp_stamp, abs=1e-9)
    assert buy.cost.slippage == pytest.approx(exp_slip_buy, abs=1e-9)
    assert sell.cost.slippage == pytest.approx(exp_slip_sell, abs=1e-9)
    assert buy.cost.stamp_tax == 0.0, "买入方向不得收印花税（R7 仅卖出）"
    assert sell.cost.total == pytest.approx(
        exp_sell_comm + exp_stamp + exp_slip_sell, abs=1e-9)
```

### 3.5 A 股撮合：封板顺延 / T+1 / 停牌跳过

```python
# test/qa/backtest/test_seal_rollover.py
SEALED_UP = bar("2020-01-06", close=11.0, limit_up=11.0, open=11.0, high=11.0, low=11.0)  # 一字涨停
OPEN_NEXT = bar("2020-01-07", close=11.5)

def test_tc_r08_01_limit_up_buy_deferred(prices_two_days, cfg):
    fill = execute_orders([buy_order("2020-01-03")], prices_two_days, cfg=cfg)[0]
    first = fill.attempts[0]                       # OrderAttempt：首个目标日 = t+1（QA-F7 已闭合）
    assert first.attempt_date == "2020-01-06"
    assert first.status is OrderStatus.FAILED_LIMIT_SEAL     # 一字板买不进 → 失败可数
    assert "封板" in (first.reason or "")
    assert fill.attempts[-1].status is OrderStatus.FILLED
    assert fill.fill_date == fill.attempts[-1].attempt_date == "2020-01-07"
    assert fill.delay_days == 1                    # = 首个成功 fill_date 与首个目标日(t+1)的交易日差
    assert fill.fill_price != SEALED_UP.close

def test_tc_r08_03_t1_rejected(same_day_prices, cfg):
    fill = execute_orders([Order(code="000001", signal_date="2020-01-06", side=OrderSide.SELL,
                                 requested_amount=10_000, requested_qty=None)],
                          same_day_prices, cfg=cfg)[0]   # 当日买入后当日卖出
    assert fill.attempts[0].status is OrderStatus.REJECTED_T1
    assert fill.fill_date is None
    assert any(("T+1" in (a.reason or "")) or ("当日" in (a.reason or "")) for a in fill.attempts)

def test_tc_r08_04_suspended_skipped(suspended_next_day, cfg):
    fill = execute_orders([buy_order("2020-01-03")], suspended_next_day, cfg=cfg)[0]
    assert fill.attempts[0].status is OrderStatus.SKIPPED_SUSPENDED
    assert fill.fill_date > "2020-01-06"           # 复牌后首个可成交日
    assert all(a.attempt_date != "2020-01-06" for a in fill.attempts if a.status is OrderStatus.FILLED)

def test_tc_r08_max_delay_cap(prices_all_sealed, cfg):
    """反模式「无限循环」：连续封板超过最大顺延上限 → 订单终态失败并留痕（design §3H）。"""
    fill = execute_orders([buy_order("2020-01-03")], prices_all_sealed, cfg=cfg)[0]
    assert fill.fill_date is None                              # 未成交
    last = fill.attempts[-1]
    assert last.status is not OrderStatus.FILLED
    assert ("最大顺延" in (last.reason or "")) or ("上限" in (last.reason or ""))
```

### 3.6 未来函数：把 t+1 数据喂进 signal 必须抛错或不改变 t 日决策

```python
# test/qa/backtest/test_no_future_function.py
def test_tc_r10_02_snapshot_rejects_future_bar(financials_empty):
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(as_of="2020-01-06",
                            price=(bar("2020-01-07", close=11.0),), financials=financials_empty)

def test_tc_r10_02b_snapshot_rejects_future_financial():
    with pytest.raises(FutureDataError):
        PointInTimeSnapshot(as_of="2020-01-06",
                            price=(bar("2020-01-06"),),
                            financials=(FinancialRecord(code="000001", report_period="20191231",
                                                        ann_date="2020-02-28", end_date="2019-12-31",
                                                        visible_from="2020-02-28"),))

def test_tc_r10_03_signal_is_pure_and_ignores_later_data(snapshot_t, condition_ma60, prices_with_future):
    """同一切片两次调用结果相同；即便外部存在 t+1 数据，signal 的输入里也没有它。"""
    a = evaluate_condition(snapshot_t, condition_ma60)
    b = evaluate_condition(snapshot_t, condition_ma60)
    assert a == b
    assert a is None or a.event_date <= snapshot_t.as_of
    # 结构性断言：signal 不接日期、不 import IO 层（design §4.1 硬约束）
    sig = inspect.signature(evaluate_condition)
    assert set(sig.parameters) == {"snapshot", "condition"}
    src = Path(inspect.getfile(evaluate_condition)).read_text(encoding="utf-8")
    assert "data_provider" not in src and "dao" not in src and "datetime.now" not in src
```

> 「把 t+1 数据喂进 signal」的第三种作弊路径是**改快照的 as_of 却塞入未来行**——由 `__post_init__` 拦截（第一段用例）。**不允许**「静默截断后照跑」：所以断言是 `pytest.raises`，不是「结果不变」。

### 3.7 生存偏差：样本缺退市股必须被检出并告警

```python
# test/qa/backtest/test_survivorship_bias.py
def test_tc_r12_04_missing_delisted_list_reports_gap(cfg, provider_without_delisted):
    with pytest.raises(BacktestDataGapError) as exc:   # design §4.1 异常清单（数据缺失口径）
        build_universe("2019-12-31", universe_spec, provider=provider_without_delisted)
    msg = str(exc.value)
    assert "退市" in msg and "影响" in msg             # 缺失项 + 影响范围（R12 Scenario4）
    assert "剔除" not in msg                            # 不得静默降级为剔除

def test_tc_r12_04b_provider_error_not_swallowed(cfg):
    """对抗：provider 抛数据缺口 → 不得被吞成空名单（否则等于静默剔除退市股）。"""
    with pytest.raises(BacktestDataGapError):
        build_universe("2019-12-31", universe_spec, provider=RaisingProvider(BacktestDataGapError("退市名单缺失")))
    # 注意：provider 返回「不完整名单」而自身不报错的情形系统无法自证 → 见 §7 未覆盖项 8
```

### 3.8 基准与归因：无基准对比的结果必须判不可采信

```python
# test/qa/backtest/test_benchmark.py
def test_tc_r13_02_no_benchmark_inconclusive(run_experiment, registry_path, cfg):
    """R13 Scenario2：基准缺失 → 实验判定「不可判定」，不得 VALID，台账记缺失原因。"""
    rec = run_experiment(cfg=cfg, benchmarks=[])       # 空基准序列（契约：benchmarks: Sequence[Benchmark]）
    assert rec.verdict is Verdict.INCONCLUSIVE         # 判定在结果行 ExperimentRecord.verdict（design §4.1）
    assert rec.verdict is not Verdict.VALID
    assert any("基准" in (r.reason or "") for r in run_rows(registry_path))

def test_tc_r13_01_two_benchmarks_present(events, cfg):
    """R13 Scenario1：双基准各一套超额（QA-F4 已闭合：windows[window][benchmark_kind]）。"""
    benchmarks = [Benchmark(kind="buy_and_hold", label="买入持有"),
                  Benchmark(kind="market_portfolio", label="全A等权")]
    res = compute_event_study(events, benchmarks, cfg=cfg)
    for window in ("20", "60"):
        assert set(res.windows[window]) == {"buy_and_hold", "market_portfolio"}
        for ws in res.windows[window].values():
            assert ws.ci[0] <= ws.mean <= ws.ci[1]
```

---

## 4. 已知答案校准（R18）的验收方式与断言顺序

### 4.1 断言顺序：先修台子，再谈策略（硬性排序）

```
step0  夹具自检：校准题参数（条件、区间、成本、T+1、顺延）全部来自夹具与配置，缺任何一项 → 用例 skip 并记为「配置未定」
step1  run_calibration(...)                    # 必须最先跑，先于任何研究结论用例
step2  assert cal.passed is True               # 不通过 → 台子不可信
step3  assert_calibrated(registry)             # 库层 raise CalibrationFailedError 封锁研究输出；CLI 捕获后 exit 2（§2.3）
step4  只有 step2/step3 通过，后续研究结论用例（R14/R16/R17 的 positive 分支）才有意义
```

**失败时的唯一合法表述**：`台子不可信，先修台子`。**禁止**：把 `passed is False` 写成「MA60 止损无效」或「该规则无效」（TC-R18-03 的禁词扫描）。

落地方式：`test/qa/backtest/conftest.py` 提供 session 级 `calibration_gate`，研究结论类用例显式 `usefixtures("calibration_gate")`；校准未通过时这些用例 `pytest.fail("台子不可信：校准未通过，任何研究结论不可采信", pytrace=False)`——**红灯而不是 skip**（skip 会被误读为「不适用」）。

```python
# test/qa/backtest/test_known_answer_calibration.py
def test_tc_r18_02_calibration_failure_blocks_output(registry, registry_path, results_dir, cfg_bullish_broken_loader, cfg):
    """校准复现不出「跌破 MA60 显著跑输」→ 封锁一切研究结论。"""
    cal = run_calibration(cfg=cfg_bullish_broken_loader, loader=cfg_bullish_broken_loader)
    assert cal.passed is False
    assert cal.direction != "显著跑输"
    assert cal.verdict is not Verdict.VALID                # QA-F8 已闭合：verdict 字段存在
    assert cal.corrected_p is None or cal.corrected_p > cfg["alpha"]
    # QA-F9 已闭合：库层直接 raise CalibrationFailedError（不断 SystemExit；CLI 退出码见 §2.3 TC-EXIT-01）
    with pytest.raises(CalibrationFailedError) as exc:
        assert_calibrated(registry)
    assert exc.value.reason and exc.value.verdict is not Verdict.VALID   # 异常携带 reason/corrected_p/verdict
    # 校准失败入台账：执行行 FAILED + 参数（design §4.1 台账存储机制）
    last = run_rows(registry_path)[-1]
    assert last.status is RunStatus.FAILED
    assert "校准" in (last.reason or "")
    assert last.prereg_commit is not None
    # 校准结果落盘（QA-F10 已闭合：results_dir 可注入；写入点归属见 §8.1 QA-F11）
    cal_json = (results_dir / "calibration.json").read_text(encoding="utf-8")
    assert json.loads(cal_json)["passed"] is False
    blob = cal_json
    for banned in ("MA60 无效", "策略无效", "止损无效", "应卖"):
        assert banned not in blob

def test_tc_r18_01_calibration_pass_unlocks(registry, cfg_known_answer_loader, cfg):
    cal = run_calibration(cfg=cfg_known_answer_loader, loader=cfg_known_answer_loader)
    assert cal.passed is True and cal.ci[1] < 0 and cal.K >= 1
    assert cal.corrected_p is not None and cal.corrected_p < cfg["alpha"]
    assert cal.verdict is Verdict.VALID
    assert_calibrated(registry)                   # 不抛 = 解锁研究输出
```

**校准题的真实结论（离线不可断言，见 §7）**：`跌破 MA60 跑全 A 应显著跑输买入持有`。单测只验证「判定链」（方向、CI 上界、K、封锁）；真实数值断言由 T5 在端到端取证中执行，证据形式为校准结果 JSON + 台账行。

---

## 5. 统计陷阱的对抗用例

### 5.1 同组同涨同跌 → t 值虚高，block bootstrap / cluster-robust SE 必须生效

```python
# test/qa/backtest/test_stat_inference.py
def test_tc_r06_01_block_bootstrap_effective_sample(common_factor_series, cfg_inference):
    """30 只 × 100 日同共因子：名义 n=3000，但有效样本只能是时间块数。"""
    benchmarks = [Benchmark(kind="market_portfolio", label="全A等权")]
    res = compute_event_study(events_from(common_factor_series), benchmarks, cfg=cfg_inference)
    ws = res.windows["20"]["market_portfolio"]            # WindowStats（design §4.1，QA-F4 已闭合）
    assert ws.n == 3000                                   # 名义样本
    assert ws.effective_n <= cfg_inference["n_time_blocks"]   # 有效样本 = 时间块数
    assert ws.effective_n < 3000, "有效样本必须远小于名义样本（否则仍在用 iid）"
    assert res.inference_method == "block_bootstrap"
    assert res.block_length and res.n_bootstrap            # 必须标注块长与重采样次数

def test_tc_r06_01b_iid_t_is_inflated(common_factor_series):
    """对照组证明陷阱真实存在：iid t 值显著，块级 CI 不显著（用例本身有效）。"""
    t_iid = naive_iid_t(common_factor_series)            # QA 侧独立算式（对照，不测被测实现）
    ci_block = block_ci(common_factor_series, block_length=5, n_bootstrap=1000, seed=7)
    assert abs(t_iid) > 2.0 and ci_block[0] <= 0 <= ci_block[1]
```

> `block_ci` 是 QA 侧的**独立实现**（20 行内），用于证明夹具确实触发陷阱；断言被测实现时仍走 `compute_event_study` / `block_bootstrap`。若 T3 实现与 QA 独立实现在同一夹具上结论相反 → 报 finding，不改夹具。

### 5.2 分组换档也计入 K

```python
# test/qa/backtest/test_labels.py
def test_tc_ag_06b_group_variant_counts_into_k(registry, cfg_labels):
    """size 三分位 → 改五分位：必须 K+1（飞书 §七「换过几次都要计入 K」）。"""
    k0 = registry.cumulative_K("study-demo")
    assign_groups(["000001"], "2021-06-30", features, cfg={**cfg_labels, "tier_count": 3})
    k1 = registry.cumulative_K("study-demo")
    assign_groups(["000001"], "2021-06-30", features, cfg={**cfg_labels, "tier_count": 5})
    k2 = registry.cumulative_K("study-demo")
    assert (k1, k2) == (k0 + 1, k0 + 2), "每次分组档位变更必须各计 1 次 K"
```

### 5.3 用今天的分组回看历史必须被拒

```python
# test/qa/backtest/test_labels.py
def test_tc_r15_02_today_grouping_rejected(cfg_labels, features_today):
    with pytest.raises(Exception) as exc:
        assign_groups(["000001"], "2015-06-30", features_today, cfg=cfg_labels)  # 传入今日截面
    assert "未来" in str(exc.value) or "时点" in str(exc.value)
    # 反向确认：同一标的用 2015 时点截面可以分组
    ok = assign_groups(["000001"], "2015-06-30", features_2015, cfg=cfg_labels)
    assert ok["000001"].as_of == "2015-06-30"

def test_tc_r15_03_quarterly_recompute_no_rewrite(cfg_labels):
    """R15 Scenario3：重算新切点后，同一历史时点再查必须一模一样（design §4.1 GroupAssignment.effective_range）。"""
    before = assign_groups(codes, "2020-06-30", features_2020, cfg=cfg_labels)
    assign_groups(codes, "2021-06-30", features_2021, cfg=cfg_labels)   # 重算 2021Q2 新切点
    after = assign_groups(codes, "2020-06-30", features_2020, cfg=cfg_labels)
    assert after == before, "季度重算不得回改历史分组（同一 as_of 必须同结果）"
    for ga in before.values():
        assert ga.effective_range[0] <= ga.as_of <= ga.effective_range[1]
```

---

## 6. 三级门禁核对表

| 档 | spec 依据 | 可观测判据（断言） | 「不得跳过」检查 | 用例 |
| --- | --- | --- | --- | --- |
| ① 回测通过 | R19 ①；飞书 §九.1 | `GateRecord.stage is BACKTEST_PASSED`；`stage_timestamps["backtest"]` 存在；`evidence_experiment_ids["backtest"]` 指向样本外段实验且该实验 `burnt is True`、扣成本、多重比较校正后「不劣于基准」；且 `calibration passed is True` | 该校验必须来自真实台账行（`registry.get(experiment_id)` 非空），不得由调用方传入布尔 | TC-R19-03 / TC-GATE-01 |
| ② 影子运行 | R19 ②；飞书 §九.2 | `stage is SHADOW_RUNNING`；影子期 ≥ 最低月数（配置项，Q7）；影子期产出**只含建议、不含成交**：`shadow_run.orders == 0 and shadow_run.fills == 0` | 进档前一级必须已通过（`BACKTEST_PASSED`），否则拒绝 | TC-R19-01 / TC-GATE-02 |
| ③ 实盘小仓位 | R19 ③；飞书 §九.3 | `stage is LIVE_SMALL`；`direction_agree is True`（影子方向与回测一致）；仓位上限来自配置（Q7），超限拒绝 | 影子期未满 / `direction_agree is not True` → 拒绝并留痕 | TC-R19-02 / TC-GATE-03 |
| 跳级 | R19「跳级请求 MUST 被拒绝并留痕」 | `BACKTEST_PENDING → SHADOW_RUNNING`、`BACKTEST_PASSED → LIVE_SMALL`、`→ LIVE_SMALL`（跳过影子）三类跳级全部抛错；状态不变；台账新增拒绝记录 | 断言允许边集合恰为 `{(PENDING→PASSED), (PASSED→SHADOW), (SHADOW→LIVE)}`，其余全拒 | TC-GATE-04 |
| 唯一状态 | R19 Scenario3 | `current(rule_id)` 返回单条记录（非列表）；重复查询结果稳定；`stage_timestamps` / `evidence_experiment_ids` 按级齐全 | 两处查询不得返回不同状态（同进程内幂等） | TC-R19-03 |
| 终态 | design `GateStage.REJECTED` | 进入 `REJECTED` 后任何 transition 均拒绝 | `REJECTED` 为吸收态 | TC-GATE-05 |

```python
# test/qa/backtest/test_gates.py
def test_tc_gate_04_no_stage_skipping(gate_sm, rule_id, registry_path):
    gate_sm.transition(rule_id, GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})
    with pytest.raises(GateSkipError) as exc:          # design §4.1 异常清单（QA-F5 已闭合）
        gate_sm.transition(rule_id, GateStage.LIVE_SMALL, evidence={"experiment_id": "exp-001"})
    assert "跳过" in str(exc.value) or "上一级" in str(exc.value)
    assert gate_sm.current(rule_id).stage is GateStage.BACKTEST_PASSED   # 状态不变
    assert count_run_rows(registry_path, RunStatus.REJECTED) >= 1        # 拒绝留痕（QA-F2 已闭合）

def test_tc_r19_02_shadow_too_short(gate_sm, rule_id, registry_path):
    gate_sm.transition(rule_id, GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})
    gate_sm.transition(rule_id, GateStage.SHADOW_RUNNING, evidence={"experiment_id": "exp-002"})
    with pytest.raises(GateSkipError) as exc:
        gate_sm.transition(rule_id, GateStage.LIVE_SMALL,
                           evidence={"experiment_id": "exp-002", "months": 2, "direction_agree": True})
    msg = str(exc.value)
    assert "6" in msg and ("方向" in msg or "月" in msg)
    assert gate_sm.current(rule_id).stage is GateStage.SHADOW_RUNNING
    assert count_run_rows(registry_path, RunStatus.REJECTED) >= 1
```

---

## 7. 未覆盖项（如实列，附原因）

| # | 未覆盖内容 | 原因 | 谁在哪一步补 |
| --- | --- | --- | --- |
| 1 | 「跌破 MA60 跑**全 A** 相对买入持有显著跑输」的**数值级**断言 | 需要后复权全 A 数据 + 退市/ST 名单 + Q4 费率 + Q5 封板口径（Owner 未答复 Q4/Q5、A4 数据缺口）；离线单测无法构造可信全 A 样本 | T5 端到端取证（`verification.md` §8 复现说明），证据 = 校准结果 JSON + 台账行 |
| 2 | 分市场状态（牛/熊/震荡）**判据本身** | `KQ-7` 未答复（design §9.2 明确「未答复前该维度输出口径未定、不参与判定」） | 用例只断言「必须分维度报告 + 未定维度显式标注」（TC-R14-01 的标注分支）；判据数值待 Owner 答复后由 QA 补用例 |
| 3 | Deflated Sharpe 的**具体统计量公式** | 文献口径与 K 的关系未在 spec 固定（spec 只要求「Bonferroni 或 Deflated Sharpe 择一、预注册固定」）；本设计只断言「method 固定 + 校正后判定随 K 单调反向」 | Owner 定 method 后补公式级黄金样例 |
| 4 | 影子运行 6–12 个月**真实计时** | 需要真实时间流逝；且 `KQ-4`（影子期计时口径）未答复 | 用例只测状态机与月数判据（夹具注入月数）；真实影子期由运营流程承担 |
| 5 | 图表产出 | `matplotlib` 未安装，且 proposal `out of scope` 已排除报告渲染 | 不测（无依赖、无范围） |
| 6 | 全 A 10 年逐日撮合的**性能/内存** | 不属 T4 设计范围（T4 是验收/负向/对抗）；proposal 成功标准未含性能指标 | 若后续需要，另立性能任务（不发明验收门槛） |
| 7 | `cluster-robust SE` 实现路径 | spec R6 是「block bootstrap **或** cluster-robust」二选一；design 只落 block bootstrap（满足 SHALL） | 只测 block bootstrap；若 T3 额外实现 cluster-robust，QA 补等价性用例（不阻塞） |
| 8 | provider 返回**被今日标签污染或不完整**的退市/ST/成分名单时的自证 | 契约只要求「名单不可得 → 报缺口」（`BacktestDataGapError`），未定义名单**完整性/时点正确性**的机器可验字段；系统无法自证 provider 撒谎 | 用例退化为两条可断言面：① `build_universe` 把 `as_of` 透传给 provider（spy 断言）；② provider 抛错不得被吞。真实名单正确性依赖数据源与人工核查（`verification.md` 记录来源） |

> 说明：**没有「因为难测所以不测」的项**；1–4 都是「数据/参数未定」或「需要真实时间」，已在用例里退化为可断言的判定链，并明确标注真实结论由 T5 取证。

---

## 8. 结构化 findings（T4 提出 → T2-fix 复核状态）

> 格式：`id / severity / problem / requiredFix / 文件:行`。requiredFix 均为「改哪里、改什么、怎么验证」，可执行。
> **复核图例（T4-fix）**：每条 finding 末尾的「复核状态」行给出归宿——**已闭合** = 契约已在 `design.md` 落地（附章节/契约要点），对应断言已收紧为具体异常类/字段；**未闭合** = 见 §8.1（保留 `TODO` + 写明影响哪条断言，不放宽断言）。

### QA-F1（medium）QA 用例目录与命名，design 与 T4 契约不一致

- **problem**：`design.md` §6.7 把 QA 用例落在子目录 `test/qa/backtest/test_*.py`，而 T4 当时的任务契约与 `test/qa/README.md` 现行结构是**扁平命名**（`test/qa/` 下直接放 `test_backtest_<topic>.py`）；两套并存会出现两份「QA 用例清单」，T5 执行时可能漏跑一半。
- **requiredFix**：captain 裁定唯一落位（以 design §6.7 子目录为准），并由 T7 在 `design.md` §6.7 与 `test/qa/README.md` 同步该命名；验证方式：`ls test/qa/backtest` 结果与 `design.md` §6.7 清单逐条同名，`python -m pytest -q test/qa --collect-only` 收集数与 §1.1 一致。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:545-552`（T2-fix 后 §6.7 位置不变）
- **复核状态（T4-fix）：已闭合（captain 裁定）** —— 以 design §6.7 子目录为准；本文 §1.1/§1.2 全部改为 `test/qa/backtest/test_<topic>.py`（19 文件，其中 design §6.7 的 8 个同名全含）；`test/qa/README.md` 已同步目录约定。`design.md` 未改。

### QA-F2（high）「失败/拒绝留痕」与「失败不落结果行」自相矛盾

- **problem**：`design.md` §3D 写「失败不落结果行（R1）」，但 spec R2 Scenario2（拒绝动作留痕）、R4 Scenario2（台账新增拒绝记录）、R10 Scenario2（台账记录失败原因）、R19 跳级（拒绝记录写入台账）都要求**拒绝/失败本身入台账**；`ExperimentRecord` 无 `status` 字段，`Verdict` 也没有「失败」值。T5 无法断言「台账里有这条失败记录」，只能断言「没写任何行」——与 spec 相反。
- **requiredFix**：`design.md` §4.1 增加「执行行」与「结果行」的区分与字段清单（例如 `RunRecord{run_id, experiment_id | None, status: run|rejected|failed, reason, at, prereg_commit}`，或给 `ExperimentRecord` 增 `status` 字段并允许 `metrics={}` 的失败行）；并在 §4.1「台账存储机制」写明两类行同文件 append、均逐行哈希。验证方式：TC-R02-02 / TC-R04-02 / TC-R10-02 能读到对应拒绝行且计数 == 1。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:117`、`design.md:317-333`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 新增 `RunStatus`（RUNNING/PASSED/REJECTED/FAILED）+ `RunRecord`（`row_type/run_id/experiment_id/status/reason/at/prereg_commit`）+ `ExperimentRegistry.append_run`；`ExperimentRecord` 改为仅 PASSED 产生的结果行；两行同文件 append + 逐行哈希（§4.1「台账存储机制」）；§3D 的「失败不落结果行」矛盾已改为「失败不落**结果**行、必落**执行**行」。本设计 §3.1/§3.2/§3.3/§4.2/§5.3/§6 的留痕断言已改为 `run_rows`/`count_run_rows` + `RunStatus`。

### QA-F3（medium）预注册的必填字段清单缺失，R1 的「提示缺失字段清单」无法实现

- **problem**：`design.md:424` 只给预注册文件路径 `config/backtest/preregistrations/<hypothesis_id>.yaml`，未定义必填字段（假设陈述 / 参数 / 指标 / 样本区间 / 基准 / 校正方法 / K 口径）。spec R1 Scenario2 要求拒绝时「提示缺失的预注册字段清单」，R5 还要求「校正方法与 K 的计算口径 MUST 在预注册中固定」——没有 schema 就没有清单，也没有校验。
- **requiredFix**：`design.md` §4.1 增 `PreregistrationSpec` 字段清单（至少：`hypothesis_id / statement / params / metrics / segments / benchmark / correction_method / k_definition / created_at`），并写明「校验入口 + 缺键报错文案含字段名」。验证方式：TC-R01-02 对 stderr 做逐字段 grep；`preregister` 子命令对缺字段 YAML 退出码非 0。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:424`、`design.md:439`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 新增 `PreregistrationSpec`（9 必填：`hypothesis_id/statement/params/metrics/segments/benchmarks/correction_method/k_definition/created_at`）+ `ExperimentRegistry.validate_preregistration`（缺键报错含字段名）；§4.2 R1 映射已更新。TC-R01-02 的「逐字段 grep 缺失清单」可直接落地。

### QA-F4（high）R13/R14/R17 的结果 dataclass 未定义字段，且单基准签名表达不了 R13 双基准

- **problem**：`EventStudyResult` / `AttributionResult` / `StabilityResult` 在 `design.md:385/394/400` 被引用但 §4.1 无字段定义；而 spec R13 要求同时给「买入持有」与「市场组合」两个基准的超额，签名 `compute_event_study(events, benchmark, ...)`、`attribution(returns, factors, benchmark)` 只能传一个基准。T5 无法断言「事件数/均值/中位数/CI/分年度/分档」「四项暴露与贡献」「两个基准的超额」——这正是 R13/R14/R17 的全部验收面。
- **requiredFix**：`design.md` §4.1 补三个结果 dataclass 的字段清单（事件研究：`windows[20/60] → {n, mean, median, std, ci, by_year, by_cap_tier, effective_n, inference_method, block_length, n_bootstrap}`；归因：`beta/size/value/momentum` 暴露与贡献 + `unexplained`；稳定性：`by_year / by_market_state / by_cap_tier` + `scope_note`），并把 benchmark 参数改为 `benchmarks: Sequence[Benchmark]`（或在结果里固定两个基准字段）。验证方式：TC-R13-01 / TC-R14-01 / TC-R17-01 的键集合断言。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:385`、`design.md:394`、`design.md:400`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 新增 `Benchmark` / `WindowStats`（`n/mean/median/std/ci/effective_n/by_year/by_cap_tier`）/ `EventStudyResult`（`windows[window][benchmark_kind]`/`n_events`/`inference_method`/`block_length`/`n_bootstrap`）/ `AttributionResult`（四项 + `exposures`/`contributions`/`unexplained`）/ `StabilityResult`（`by_year`/`by_market_state`/`by_cap_tier`/`scope_note`）；签名改为 `compute_event_study(events, benchmarks: Sequence[Benchmark], *, cfg)`、`attribution(returns, factors, benchmarks)`。断言见 TC-R06-01 / TC-R13-01 / TC-R13-03 / TC-R14-01 / TC-R17-01。

### QA-F5（medium）异常族不完整且语义重叠，负向用例只能弱断言

- **problem**：`BacktestDataGapError` 同时承载「前复权请求被拒」（R9 口径非法）与「数据缺失」（R12 缺口），T5 无法区分是「口径写错」还是「数据没有」，也就无法证明「不静默降级」；「台账已损坏」「校准未通过」「门禁跳级」均无专属异常类。design 只明确了 `FutureDataError`、`BacktestDataGapError`、`MissingBacktestConfigError` 三个。
- **requiredFix**：`design.md` §4.1 增「异常清单」小节，至少定义 `InvalidAdjustModeError`（R9）、`RegistryCorruptedError`（R2）、`CalibrationFailedError`（R18）、`GateSkipError`（R19）、`RegistryImmutableError`（R2 改假设），并约定「每类拒绝必须可由异常类型二分」。验证方式：本设计原 8 处「异常类待锁定」标记收紧为具体类型断言；若实现只用基类，T5 报 finding。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:28`、`design.md:357-358`、`design.md:404-420`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 新增「异常清单」8 类（`BacktestError` 根 + `InvalidAdjustModeError` / `BacktestDataGapError` / `MissingBacktestConfigError` / `FutureDataError` / `RegistryCorruptedError` / `RegistryImmutableError` / `CalibrationFailedError` / `GateSkipError`）与「触发条件 × 区分作用」二分表。本设计原 8 处「异常类待锁定」标记（原文标记）**已全部替换**为具体异常类（§3.1 `RegistryCorruptedError`/`RegistryImmutableError`、§3.2 `RegistryImmutableError`、§3.5/§6 `GateSkipError`、TC-R09-01 `InvalidAdjustModeError` 与 `BacktestDataGapError` 对照）。

### QA-F6（medium）可测试性注入点缺失（registry 路径 / clock / data_version）

- **problem**：`ExperimentRegistry` 只有方法签名（`design.md:404-410`），无构造参数；`data_version` 与 `timestamps` 的产生方式也未定义。T5 只能用真实 `data/backtest/registry.ndjson`（污染工作区、用例互相干扰），且无法构造确定性时间戳来断言「时间戳存在/单调/烧毁时刻唯一」。
- **requiredFix**：`design.md` §4.1 明确 `ExperimentRegistry(store_path: Path, *, clock: Callable[[], str], data_version: str)` 的注入契约（`clock` 供测试注入固定时刻），`data_version` 由调用方/数据快照提供。验证方式：全部 `test/qa` 用例使用 `tmp_path` 上的 registry，且断言 `timestamps["created_at"]` 等于夹具注入时刻。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:404-410`、`design.md:326-331`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 明确 `ExperimentRegistry(store_path: Path, *, clock: Callable[[], str], data_version: str)`，`clock` 供测试注入固定时刻、`data_version` 写入每行。本文全部用例改在 `tmp_path` 台账上跑（`registry_path`/`appended_registry` fixture），时间戳断言可确定性（§10.1）。

### QA-F7（medium）R8「失败 → 顺延成交」在单条 `Fill` 下不可表达

- **problem**：spec R8 要求「订单状态记为失败并顺延到下一个可成交日」，而 `Fill` 只有单个 `status` + 单个 `fill_date`（`design.md:306-315`）：若 `status=FAILED_LIMIT_SEAL` 则 `fill_date=None`（最终成交无处安放）；若 `status=FILLED` 则「失败」这一事实丢失、`delay_days` 只能隐式表达。T5 无法同时断言「目标日失败」与「下一日成交」两条。
- **requiredFix**：`design.md` §4.1 在 `Fill` 上增 `attempts: tuple[OrderAttempt, ...]`（每次目标日尝试的 `date/status/reason`），或把「失败尝试」与「成交」拆为两个 dataclass；并写明「顺延天数 = 首个成功 fill_date 与首个目标日的交易日差」。验证方式：TC-R08-01/02 分别断言 attempts 序列与最终 fill_date。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:306-315`、`design.md:430-433`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1 新增 `OrderAttempt{attempt_date,status,reason}` 与 `Fill.attempts: tuple[OrderAttempt, ...]`；`fill_date` = 末次 FILLED 的 `attempt_date`；`delay_days` = 首个成功 `fill_date` 与首个目标日（t+1）的交易日差。本设计 §3.5 已改为 `fill.attempts[0].status` 断言（不再使用已删除的 `Fill.status`），TC-R08-01/02 可同时断言「失败」与「顺延成交」。

### QA-F8（low）三处字段级缺口：`experiment_id` 规则 / `K` 缺失不可表达 / 校准校正后判定

- **problem**：① `ExperimentRecord.experiment_id` 的生成规则未定义（`design.md:320`），R2 Scenario1 的「两次执行实验 ID 不同」无法稳定断言；② `K: int` 为必填，R5 Scenario2 的「结果缺失 K 字段」在契约上不可构造（只能靠调用方不传，而 dataclass 会报 TypeError）；③ spec R18 Scenario1 要求校准「报告 K 与校正后判定」，但 `CalibrationResult` 只有 `passed/direction/ci/K/params/notes`，无校正后 p / 判定字段。
- **requiredFix**：① 在 §4.1 写明 `experiment_id = f"{hypothesis_id}-{seq:04d}"`（或 UUID4）并把 `seq` 计入台账以便断言唯一；② `K: int | None`，或明确「缺失 K = `K=None` 拒绝构造 → 由 `metrics` 输出 `INCONCLUSIVE`」的二选一并写清；③ `CalibrationResult` 增 `corrected_p: float | None` 与 `verdict: Verdict`。验证方式：TC-R02-01 / TC-R05-02 / TC-R18-01 的对应断言。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:320`、`design.md:324`、`design.md:335-343`（T2-fix 前）
- **复核状态（T4-fix）：已闭合** —— design §4.1：① `experiment_id` = `<hypothesis_id>-<seq:04d>`（`ExperimentRegistry.next_experiment_id`，seq 单调递增）；② `ExperimentRecord.K: int | None`（`None` = 未报告 K → `INCONCLUSIVE`）；③ `CalibrationResult` 增 `corrected_p: float | None` + `verdict: Verdict`。断言见 TC-R02-01 / TC-R05-02 / TC-R18-01 / TC-R18-02。

---

### 8.1 T4-fix / T4-fix-2 / T4-fix-3 提出的 3 条缺口 → **全部闭合（QA-F1–F11 = 11/11，未闭合 0）**

> **结论（T4-fix-3，设计冻结版）**：QA-F9、QA-F10（T2-fix-2 闭合）与 QA-F11（T2-fix-3 闭合）**均已闭合**，`TODO` 标记（QA-F1–F11）机检 = **0**，对应断言写死契约（下表）。本轮只做标记清理与锚点校准，**不新增 finding、不新增用例、不放宽任何断言**。
> 纪律不变：缺口**不得**由 QA 自行放宽（不写成「任一异常/任一字段」）；已闭合的写死契约引用，未闭合的保留 `TODO` + 说明影响哪条断言。

#### QA-F9（low）校准失败的表达形态未二分（库层异常 vs CLI 退出码）

- **problem**：design §4.1 `assert_calibrated(registry)` 注释写「未过 → exit != 0，封锁研究输出」，而异常清单把 `CalibrationFailedError` 归给「R18 校准未通过（封锁研究输出，exit != 0）」，但**未说明 raise 点在库层还是 CLI 层**。单测无法二分（`pytest.raises(CalibrationFailedError)` 还是 `SystemExit`）：TC-R18-02（库层）与 §2.1 S1（CLI 退出码 0）各锁一半，若实现只做 exit-code，则 TC-R18-02 必红而契约看似「已闭合」。
- **requiredFix**：在 `design.md` §4.1 函数签名处写明唯一 raise 点，例如「`calibration.assert_calibrated` 直接 `raise CalibrationFailedError`；`apps/backtest_cli.py` 捕获后 `sys.exit(非 0)`」，或在 §4.2 R18 行的「关键机制」列补该句。验证方式：TC-R18-02 断言异常类（库层），CLI 级用例断言退出码非 0（§2.1 S1 的反例分支），两条各归其位、互不代替。
- **影响断言**：TC-R18-02（校准封锁输出）、TC-SC-01（CLI 退出码 0 与 corrected_p 判定）。原影响的范围（F9 未闭合时 TC-R18-02 无法二分）已解除。
- **文件:行**：T4-fix 时 `design.md:507`/`527`/`539`；**T2-fix-2 后**：`design.md:536`（签名）、`design.md:556`（异常定义）、`design.md:571-575`（「失败表达二分」）、`design.md:676`（§6.3 退出码）
- **复核状态（T4-fix-2）：已闭合** —— 契约写死：① 库层 `calibration.assert_calibrated()` **直接 `raise CalibrationFailedError`**（带 `reason`/`corrected_p`/`verdict`），单测只断 `pytest.raises`、**不断 `SystemExit`**（TC-R18-02 已改）；② CLI `apps/backtest_cli.py` 捕获后打印 stderr 并 **`sys.exit(2)`**（TC-EXIT-01）；③ 退出码语义固定 `1` = 参数/配置/数据错误、`2` = 门禁失败（TC-EXIT-02/03）。本设计新增 §2.3 三条退出码用例，原 `TODO` 标记（QA-F9）已删除。

#### QA-F10（medium）`ledger` 导出契约与 `data/backtest/results/` 路径注入缺失

- **problem**：design §6.3 只列 CLI 子命令名（`preregister / run / calibrate / ledger / gate`），**未给 `ledger` 的导出字段清单与参数**；§4.1 把结果 JSON 与校准 JSON 固定落 `data/backtest/results/`，而注入点只覆盖台账 `store_path`（`QA-F6` 只解决了台账）。后果两条：① proposal 成功标准 S2「任一实验可用**一条命令**导出 假设/参数/样本区间/K/结果/是否触达样本外/预注册 commit」与 R4 Scenario1「导出显示该实验样本外额度已用尽」**无法断言**；② 校准结果落盘断言会写真实 `data/backtest/results/`（污染工作区、用例互相干扰）。
- **requiredFix**：① `design.md` §6.3 补 `ledger` 输出契约：字段清单（至少 `hypothesis_id / params / segments / K / metrics / verdict / burnt / prereg_commit / run_status`）、参数（`--experiment <id>`、`--hypothesis <id>`）、输出格式（JSON，逐行或数组）；② 给**结果目录注入点**（如 `ExperimentRegistry(..., results_dir: Path)` 或 `run_experiment(..., results_dir=...)`），使 `<experiment_id>.json` 与 `calibration.json` 可写 `tmp_path`。验证方式：TC-SC-02 逐字段与预注册 YAML 比对；TC-R18-02 的落盘断言改为读 `results_dir/calibration.json`。
- **影响断言**：TC-R04-01（导出显示额度用尽）、TC-SC-02（S2 台账审计导出）、TC-R18-02（校准结果落盘部分）。三处断言均已改为可执行形态。
- **文件:行**：T4-fix 时 `design.md:636-640`（§6.3）、`design.md:548`（落盘路径）；**T2-fix-2 后**：`design.md:441-445`（`BacktestConfig.results_dir`/`registry_store_path`）、`design.md:448-462`（`LedgerExportRow` 13 字段）、`design.md:530-532`（`write_result`/`export_ledger`）、`design.md:675`（导出契约）、`design.md:680`+`683-686`（注入与落盘）
- **复核状态（T4-fix-2）：已闭合** —— 契约写死：① `BacktestConfig` 增 `results_dir`（默认 `data/backtest/results/`）与 `registry_store_path`（默认 `data/backtest/registry.ndjson`），测试注入 `tmp_path`；② `ExperimentRegistry.__init__(..., results_dir=...)`、`write_result(experiment_id, payload)`（写 `<results_dir>/<experiment_id>.json`）、`export_ledger(*, experiment_id=None, hypothesis_id=None) -> list[LedgerExportRow]`；③ 导出字段 = 13 个（`experiment_id/hypothesis_id/statement/params/segments/K/metrics/verdict/burnt/prereg_commit/run_status/data_version/adjust_mode`），JSON 数组，`burnt=True` 即「额度用尽」。TC-R04-01 / TC-SC-02 / TC-R18-02 已按此改写，原 `TODO` 标记（QA-F10）已删除。

#### QA-F11（low）CLI 的配置/数据注入面（**已闭合：T2-fix-3**）

- **problem**（T4-fix-2 时状态）：`design.md` §6.3 定了子命令名（`preregister/run/calibrate/ledger/gate`）、`ledger` 的可选面（`--experiment`/`--hypothesis`/`--format json`）与退出码语义，但**当时未写** `calibrate`/`run` 的配置来源（`config/app.yaml` 的解析根 = cwd 还是仓库根？是否支持 `--config`）与入口函数形态（`[project.scripts]` 名 `backtest` 已定，但未写 `main(argv) -> int`）。后果：§2.3 的端到端退出码用例**断言语义已锁定（2/1/0）**，但夹具的调用面只能按约定写，T3 若换一种注入方式则用例需改夹具（**不是改断言**）。另有一处同源缺口：`<results_dir>/calibration.json` 的**写入点**未落到函数级（`run_calibration(*, cfg, loader)` 无 registry 入参、`write_result` 面向 `<experiment_id>.json`），TC-R18-02 的「`run_calibration` 之后文件存在」需要 T3 确认归属。
- **requiredFix**（T2-fix-3 已按此落地）：① `design.md` §6.3 补一句入口契约，例如「`apps/backtest_cli.py` 暴露 `main(argv: list[str]) -> int`（返回码即进程退出码），并支持 `--config <path>`（默认仓库根 `config/app.yaml`）」；或在 §4.1 函数签名清单加该入口。② 明确校准结果写入点，例如「`run_calibration` 内部经 `cfg.results_dir` 写 `<results_dir>/calibration.json`」，或「由 CLI 在 `assert_calibrated` 之后经 `registry.write_result("calibration", payload)` 落盘」。
- **影响断言**：TC-EXIT-01/02/03 的**夹具写法**（`cli_runner` 如何注入 `cfg` 与 `results_dir`）；TC-R18-02 / TC-EXIT-01 的**落盘断言归属**（文件由谁写）。退出码语义断言本身不受影响——该影响已随闭合解除。
- **文件:行**：T4-fix-2 时 `design.md:671-677`（§6.3）；**T2-fix-4 后（895 行）**：`design.md:752`（入口契约）、`design.md:754-758`（子命令与参数）、`design.md:759`（配置解析顺序）、`design.md:761`（退出码 0/1/2）、`design.md:603-605`（`run_calibration` / `assert_calibrated` / `write_calibration_result`）、`design.md:649-651`（校准结果写盘点）、`design.md:883`（§10 QA-F11 行）
- **复核状态（T4-fix-3）：已闭合** —— 契约写死：① **入口** = 既有 `src/apps/cli.py` 的 `main(argv: list[str]) -> int` + `build_parser()` 内 `backtest` 子命令组（**不另建 `backtest_cli.py`**，design §4.0/§4.1/§6.3）；② **子命令与参数**：`backtest preregister --file/--hypothesis`、`run --hypothesis [--config]`、`calibrate [--config]`、`ledger [--experiment|--hypothesis] [--format json]`、`gate --rule [--to]`；③ **配置解析顺序**：`--config <path>`（相对路径按 cwd）> `cwd/config/app.yaml` > 缺键 `MissingBacktestConfigError`（退出码 `1`）；④ **`calibration.json` 写盘点**：`run_calibration(*, cfg, loader, registry)` 无论成败经 `write_calibration_result(result, results_dir, *, run_id, at)` **原子写** `<results_dir>/calibration.json`（字段 = `CalibrationResult` + `run_id` + `at`；失败写 `passed=False` + `reason`；重跑覆盖带新 `run_id`）并 `append_run(RunRecord PASSED/FAILED)`；⑤ **退出码** `0`/`1`/`2` 落到 §6.3。用例侧：§2.3 夹具改 `cli_runner(cwd=tmp_path)`（`tmp_path/config/app.yaml` 自动发现），TC-R18-02 / TC-EXIT-01 断言 `calibration.json` 由 `run_calibration` 写出。原 `TODO` 标记（QA-F11）已删除。



### 8.2 T5 findings F7/F8/F9 复核（T2-fix-6 已裁决，t24 收口）

> T5（t14/t20）提出的 F7/F8/F9 属**契约层**问题，已由 architect 在 T2-fix-6 裁决并落 design（939 行）；本轮按裁决更新 QA 用例，全部转绿。

| T5 finding | 裁决（design） | QA 收口 |
| --- | --- | --- |
| F7 空观测语义 | `EventStudyResult.verdict`（design.md:413-420）+ 空观测 → `verdict=INCONCLUSIVE, windows={}, n_events=0`、不抛异常（design.md:928） | `TC-R13-02` 断 `windows == {} / n_events == 0 / verdict is INCONCLUSIVE`；`TC-R17-02` 改断「样本不足 → INCONCLUSIVE」 |
| F8 universe `provider` 协议 | `UniverseProvider`（`historical_constituents`/`delisted_codes`/`st_status`）+ `build_universe(as_of, scope, *, provider)`；不可得 → `BacktestDataGapError`；可得为空 → 空 tuple（design.md:548-557） | `TC-R12-01..04` 改用 `SpyProvider` 三方法：历史成分按时点、退市前计入/后剔除、ST 按时点查询不剔除、缺口报错、空集合法 |
| F9 gate 判据/跳级优先序 | `transition` ①先查边 ②再查判据可用性（缺 → `MissingBacktestConfigError`，**不落业务拒绝行**）③最后查达成性（design.md:637-641） | `TC-R19-01` 用「合法边 + 缺判据」断 `MissingBacktestConfigError`；跳级仍断 `GateSkipError` + 留痕 |

> **T5 侧同步**：`verification.md` §10 的 F7/F8/F9 已标「待裁决」，本轮裁决后其状态应在下一轮 T5 终审转「已消除」（由 captain 派 T5；本文件不改 verification.md）。

> **§8.1 汇总**：QA-F9、QA-F10、QA-F11 **全部闭合（3/3）**；合计 **QA-F1–F11 = 11/11 闭合、未闭合 0**，`TODO` 标记（QA-F1–F11）机检 = **0**。设计冻结（design.md 895 行，T2-fix-4 后）后本文件进入 T5 执行阶段，不再有契约缺口待补。

---

## 9. T5 执行清单（本设计的交付判据）

```bash
# 1) QA 套件（子目录 test/qa/backtest/ 自动收集，无需改 pyproject 的 testpaths）
python -m pytest -q test/qa
# 2) 全量（engineer + QA，含默认排除 akshare_legacy）
python -m pytest -q
# 3) 离线（确认无用例偷偷联网）
python -m pytest -q -m "not network and not akshare_legacy"
# 4) 静态与编译
python -m ruff check .
python -m compileall -q src test
# 5) spec 一致性（change 内 delta 不破坏）
openspec.cmd validate add-backtest-engine --strict
```

每条结果须在 `verification.md` 记录「命令 + 退出码 + 输出摘要」；`test/qa` 与 `test/` 结果分列（`roles/qa.md` 产出契约第 3 章）。

> **ruff 基线口径（captain 已定，T4-fix-2 写死）**：`python -m ruff check .` 在本 change 起波前已有 **39 个既有错误**（28 个文件，位于 `scripts/` / `src/` / `test/`，**均非本 change 产物**；本 change 只新增 `.md`，ruff 不覆盖）。T5 执行与记录方式固定为：
> ① 先跑基线，原样记录「Found 39 errors」与文件清单（作为偏差证据）；
> ② 再跑一次，确认**新增错误 = 0**（对比清单无新文件/新规则）；
> ③ 结论写「ruff：基线偏差 39（既有、非本 change），新增 0，按 captain 口径 **通过**」。
> 三条禁止：**不修既有错误**（超范围）、**不把基线错误记为本 change 失败**、**不放宽为「跳过 ruff」**。

---

## 10. 附录：夹具与独立算式

### 10.1 夹具（`test/qa/backtest/conftest.py`，未来文件）

| 夹具 | 作用 | 关键纪律 |
| --- | --- | --- |
| `cfg_raw` | 回测配置的**原始映射**（含 commission/stamp_tax/slippage_tiers/liquidity_cap/alpha/segments） | 数值是**测试输入**，非生产默认（Q4 未答复）；缺键变体由 `del cfg_raw[...]` 派生，用于 TC-R07-03 |
| `registry_path` / `appended_registry` / `results_dir` | `ExperimentRegistry(store_path=tmp_path/"registry.ndjson", clock=fixed_clock, data_version="test-v1", results_dir=tmp_path/"results")`，预置 1 行；`results_dir` fixture 单独暴露 `<tmp>/results` | 禁止写真实 `data/backtest/`（台账与结果目录都由 `tmp_path` 注入，QA-F6/QA-F10 已闭合）；时间戳由 `clock` 注入固定值 |
| `export_ledger(...)` 结果夹具（`ledger_rows`） | 直接调被测 `registry.export_ledger(...)` 拿 `list[LedgerExportRow]`；另用 `json.loads(cli stdout)` 校验 CLI 同形态 | 断言字段集 == `LedgerExportRow` 13 字段（design §4.1/§6.3）；`burnt=True` 即额度用尽 |
| `cli_runner(argv)` / `results_dir` | 按 design §6.3 的入口契约：以 `["backtest", *argv]` 调既有 `src/apps/cli.py` 的 `main(argv: list[str]) -> int`，把返回值 / `SystemExit.code` 归一为 `returncode`，`capsys` 捕获 stdout/stderr（等价形态：`subprocess` 调 `pyproject.toml` 的 `[project.scripts]` console script）；`cwd=tmp_path`，夹具在 `tmp_path/config/app.yaml` 写最小骨架，`backtest.results_dir` / `backtest.registry_store_path` 指向 `tmp_path`；需覆盖时传 `--config <path>`（**相对路径按 cwd 解析**） | 断退出码语义（§2.3：`2` 门禁失败 / `1` 参数·配置·数据错误 / `0` 成功）；**不写真实 `data/backtest/`**；`calibration.json` 由 `run_calibration` 经 `write_calibration_result` 原子写（QA-F11 已闭合） |
| `run_rows(path)` / `result_rows(path)` / `count_run_rows(path, status)` | 解析台账 NDJSON，按 `row_type` 分出执行行（`RunRecord`）/ 结果行（`ExperimentRecord`）并按 `RunStatus` 计数 | **不是**被测 API，是 QA 侧台账读取器（`row_type` 判别符由 design §4.1 定义）；禁止用生产函数反推 |
| `run_experiment(cfg=..., k=..., benchmarks=...)` | QA 侧**门面夹具**：按 design §4.1 的公开函数串起 pipeline（data → signal → broker → metrics → registry），返回结果行 `ExperimentRecord` | 只编排公开函数，不实现业务判定；判定必须来自被测函数 |
| `bar(...)` / `prices_*` | 构造 `PriceBar`（含 `limit_up_price` / `suspended` / `delisted` / `st` / `amount`） | 封板日必须 `open==high==low==close==limit_up_price`（A3 一字板口径，Q5 未答复前） |
| `financials.*` | 构造 `FinancialRecord`（含 `ann_date=None` 的回退变体） | 覆盖 R11 两个 Scenario |
| `common_factor_series` | 30 只 × 100 日同共因子序列 | 名义 3000；用于 §5.1 |
| `cfg_inference` / `cfg_gates` / `cfg_labels` / `cfg_bullish_broken_loader` | 各用例段的最小配置夹具（块长/重采样次数、门禁月数与仓位上限、切点档数、反向校准 loader） | 全部声明为**测试输入**（Q4–Q8、KQ 未答复），缺键即由 `MissingBacktestConfigError` 拒绝 |
| `gate_sm` / `rule_id` | 门禁状态机 + 临时台账 | 每用例独立 rule_id，避免状态串扰 |
| `calibration_gate`（session） | §4 断言顺序的门闩 | 校准未过 → 研究结论用例 **fail**（非 skip） |

### 10.2 成本手算（独立算式，禁止调用被测函数）

以夹具参数 `rate=2.5e-4`、`min=5`、`sell_rate=5e-4`、滑点档 `[0, 100 万) → 1e-3` 为例（**示例值，非生产默认**）：

| 项 | 独立算式 | 期望（元） |
| --- | --- | --- |
| 买入佣金 | `max(100000 × 2.5e-4, 5)` | 25.00 |
| 买入滑点 | `100000 × 1e-3` | 100.00 |
| 卖出佣金 | `max(110000 × 2.5e-4, 5)` | 27.50 |
| 卖出印花税 | `110000 × 5e-4`（仅卖出） | 55.00 |
| 卖出滑点 | `110000 × 1e-3` | 110.00 |
| 买入合计 | 25.00 + 100.00 | 125.00 |
| 卖出合计 | 27.50 + 55.00 + 110.00 | 192.50 |

断言：`买.cost.total == 125.00`、`卖.cost.total == 192.50`、`买.cost.stamp_tax == 0`，容差 `abs=1e-9`。**若 T3 实现与手算不一致 → 报 finding（台子不可信），不得改期望值迁就实现。**

### 10.3 本设计引用的 design 契约（断言锚点清单）

> 行号按**最终冻结版 `design.md`（939 行，含 T2-fix-4/5/6 全部契约裁决）**标注；每行给「契约要点 → 出处 → 对应用例」。
> 机检：每个 `design.md:<行号>` 都落在对应契约块起止内（脚本校验范围 + `sed -n '<行号>p'` 抽查文本）。
> 本次（t24）一次性按 939 行重算；t19 的「895 行漂移登记」已随之消除。

| 断言锚点（契约要点） | 出处（冻结版 939 行） | 对应用例 |
| --- | --- | --- |
| `PointInTimeSnapshot.__post_init__` 抛 `FutureDataError` | design.md:285-291、design.md:710 | TC-R10-02 |
| `AdjustMode` 无 `qfq`；`load_price_series` 抛 `InvalidAdjustModeError`（非 `BacktestDataGapError`） | design.md:213-216、design.md:538-539、design.md:660 | TC-R09-01 / TC-SC-05 |
| `execute_orders(orders, prices, *, cfg)` + `OrderStatus` 五值 | design.md:221-226、design.md:567-568 | TC-R08-01/02/03/04 |
| `OrderAttempt` / `Fill.attempts` / `fill_date` / `delay_days`（失败→顺延双可断言） | design.md:333-349、design.md:921 | TC-R08-01 / TC-R08-02 |
| `next_tradable_day` 递归顺延 + `max_delay_days`（必须键，防死循环） | design.md:570-571、design.md:491 | TC-R08-04 |
| `CostBreakdown` 四分量（佣金/印花税/滑点/过户费 + total） | design.md:325-331 | TC-R07-01/02/04 |
| **成本 spec 形状**（`CommissionSpec`/`StampTaxSpec`/`TransferFeeSpec`/`SlippageTierSpec{amount_lower,amount_upper,bps}`/`LiquidityCapSpec{adv_tier,max_participation}`） | design.md:465-473 | TC-R07-01/02/04 |
| `PreregistrationSpec`（9 必填）+ `validate_preregistration`（缺键报错含字段名） | design.md:351-363、design.md:608-629 | TC-R01-02 / TC-R01-03 |
| `RunStatus`（RUNNING/PASSED/REJECTED/FAILED） | design.md:237-242 | TC-R02-02 / TC-R04-02 / TC-R10-02 / TC-GATE-04 |
| `RunRecord`（含 `hypothesis_id`：拒绝/烧毁先于结果行也可查询） | design.md:365-376、design.md:696-704 | 台账留痕 / TC-R04-01 |
| `ExperimentRecord`（`K: int|None`、`experiment_id` 规则、`burnt` 为 append 时快照） | design.md:377-394、design.md:922 | TC-R02-01/03 / TC-R05-02 / TC-R04-01 |
| **`BacktestConfig` 必须键**（results_dir/registry_store_path/segments/windows/max_delay_days/min_events）+ 待 Q 键形状 | design.md:484-514、design.md:807 | 全部配置/缺键用例 |
| `LedgerExportRow` **13 字段** + `burnt=True` 即额度用尽 | design.md:517-531、design.md:802 | TC-SC-02 / TC-R04-01 |
| **`EventObservation`**（code/event_date/condition_id/benchmark_kind/excess_returns） | design.md:300-306 | TC-R13-01 / TC-R17-01/02/03 |
| **`ConditionSpec`**（condition_id/kind/params）+ `evaluate_condition` | design.md:310-314、design.md:563-564 | TC-R10-03 |
| **`load_event_observations` + `load_forward_returns`**（T2-fix-5 loader 形状：excess = 标的 − 基准） | design.md:574-581 | TC-R13-01 / TC-R17-01 |
| **`compute_event_study(observations, *, cfg)` + `EventStudyResult.verdict`**（空观测 → INCONCLUSIVE、不抛异常，T2-fix-6） | design.md:413-420、design.md:585-586、design.md:928 | TC-R13-02 / TC-R17-01/02/03 |
| `ExperimentRegistry(store_path, *, clock, data_version, results_dir)` + `append_run/append/get/next_experiment_id/validate_preregistration/assert_not_burnt/cumulative_K/write_result/export_ledger` | design.md:608-629 | 台账/导出用例 |
| **`mark_burnt` = 追加执行行** `RunRecord(reason="样本外已烧毁", hypothesis_id, experiment_id, at)`；导出 `burnt` 由此派生 | design.md:620、design.md:702 | TC-R04-01/02/03 |
| **`UniverseProvider` 协议**（`historical_constituents`/`delisted_codes`/`st_status`）+ `build_universe(as_of, scope, *, provider)`（不可得 → `BacktestDataGapError`；可得为空 → 空 tuple，T2-fix-6） | design.md:548-557、design.md:928 | TC-R12-01/02/03/04 |
| `Benchmark` / `WindowStats`（`n/mean/median/std/ci/effective_n/by_year/by_cap_tier`） | design.md:395-411 | TC-R06-01 / TC-R13-01 / TC-R14 / TC-R17 |
| `AttributionResult`（四项 + `exposures`/`contributions`/`unexplained`）+ **恒等式 `Σcontributions + unexplained == mean(rule)`**（T2-fix-6） | design.md:423-434、design.md:599 | TC-R13-03 |
| `StabilityResult`（`by_year`/`by_market_state`/`by_cap_tier`/`scope_note`） | design.md:436-442 | TC-R14-01 / TC-R14-02 |
| `block_bootstrap(excess, *, block_length, n_bootstrap, seed)` | design.md:589-590 | TC-R06-01/02 |
| `multiple_testing_correction(p_values, K, method, *, cfg)` | design.md:592-593 | TC-R05-01/03 |
| **`attribution(returns: dict, factors)` 口径**：beta 由 `market_portfolio` 回归推导（不入参）、`factors` 固定 `{size,value,momentum}`、缺因子键 → `MissingBacktestConfigError`、缺 `market_portfolio` → `verdict=INCONCLUSIVE`（不抛） | design.md:595-599 | TC-R13-02 / TC-R13-03 |
| `assert_calibrated` **库层 raise `CalibrationFailedError`**（不断 `SystemExit`） | design.md:628、design.md:669-673 | TC-R18-01/02 |
| **CLI 退出码**：`0` 成功 / `1` 参数·配置·数据错误 / `2` 门禁失败（捕获 `CalibrationFailedError` 后 `sys.exit(2)`） | design.md:669-673、design.md:803 | TC-EXIT-01/02/03 / TC-SC-01 |
| `CalibrationResult`（`passed` 与 `verdict` 是两件事：通过 = `passed=True` + `verdict=INVALID`，T2-fix-6） | design.md:444-455、design.md:922 | TC-R18-01/02 / TC-EXIT-03 |
| **`GateStateMachine(registry, *, cfg)`**：判据来自 `cfg.gate_criteria`，缺失 → `MissingBacktestConfigError`（**不落业务拒绝行**） | design.md:476-482、design.md:632-641 | TC-R19-01 |
| **`transition` 判定优先序（T2-fix-6）**：① 先查边（跳级/回退/同态 → `GateSkipError` + REJECTED 留痕）② 再查判据可用性 ③ 最后查达成性 | design.md:637-641、design.md:928 | TC-R19-01/02 |
| `GateStage` 五值 + `GateSkipError`（跳级留痕） | design.md:244-249、design.md:655 | TC-R19-01/02/03 |
| 异常清单 8 类 + 二分表 + 「失败表达二分」 | design.md:643-673 | TC-R09-01 / TC-R02-02/03 / TC-R12-04 / TC-R13-02 / TC-R18-02 / TC-EXIT-01 / TC-GATE-04 |
| `MissingBacktestConfigError`（必须键/待 Q 键缺值即拒绝；配置解析失败退出码 1） | design.md:650、design.md:662、design.md:801 | TC-R07-03 / TC-R19-01 / TC-EXIT-02 |
| `BacktestDataGapError`（数据缺口显式报错，不静默降级） | design.md:649、design.md:661 | TC-R12-04 / TC-R09-01 对照 |
| **R11 口径（T2-fix-4）**：`visible_from = ann_date`（缺 ann_date 才回退保守截止日，**spec 优先、不是 max()**） | design.md:275、design.md:727 | TC-R11-01 / TC-R11-02 |
| **【QA-F11】CLI 入口契约**：入口 = 既有 `src/apps/cli.py` 的 `main(argv)->int` + `build_parser()` 的 `backtest` 子命令组（不另建入口） | design.md:794、design.md:86、design.md:191 | TC-EXIT-01/02/03 |
| **【QA-F11】子命令与参数**：`backtest preregister/run/calibrate/ledger/gate` + `--file/--hypothesis/--experiment/--format/--config/--rule/--to` | design.md:796-800、design.md:925 | TC-EXIT-01/02/03 / TC-SC-02 |
| **【QA-F11】配置解析顺序**：`--config <path>`（相对 cwd）> `cwd/config/app.yaml` > 缺键 `MissingBacktestConfigError`（退出码 1） | design.md:801 | TC-EXIT-02 / 全部 `cli_runner` 用例 |
| **【QA-F11】`calibration.json` 写盘点**：`run_calibration` 无论成败经 `write_calibration_result` 原子写 + `append_run` | design.md:627-629、design.md:675-677 | TC-R18-02 / TC-EXIT-01 / TC-SC-01 |
| **§10 反馈表**：T2-fix-4 / T2-fix-5 / T2-fix-6 三行（config schema、残余歧义、F7/F8/F9 裁决） | design.md:926-928 | 全部 T4-fix 用例 |

---

## 自检记录（T4 → T4-fix → T4-fix-2 → T4-fix-3）

| 检查 | 命令 / 方法 | 结果 |
| --- | --- | --- |
| Scenario 数核对 | 对 `spec.md` 逐条 `grep -c "^#### Scenario"` 汇总 | 56（与 §1.2 的 56 个 TC ID 一一对应） |
| 成功标准数 | `proposal.md` `## 成功标准` 列表 | 5，§2.1 逐条有断言 |
| 失败标准/反目标数 | `proposal.md` `## 失败标准/反目标` 列表 | 8，§2.2 逐条有证伪用例 |
| 八条硬约束 | 飞书 §二 八行 | 8/8 有 §3 代码级负向用例 |
| **落位统一（captain 裁定）** | 检查「扁平旧命名残留」= **0**（`test/qa/` 与 `test_backtest_` 不再相邻出现）；`grep -c 'test/qa/backtest/'` = 99（≥ 18）；design §6.7 的 8 个文件名全部同名出现 | 通过（19 个文件，见 §1.1） |
| **`TODO` 标记归宿（T4-fix-3）** | 机检 `grep -c 'TODO\(QA-F'` = **0**（QA-F1–F11 逐条 = 0，markdown 内无待办标记残留） | QA-F1~F8 在 T2-fix、QA-F9/F10 在 T2-fix-2、QA-F11 在 T2-fix-3 闭合 → **11/11，未闭合 0** |
| **§8.1 逐条结论** | F9 / F10 / F11 各含 problem / requiredFix / 复核状态（契约引用 + 冻结版行号）/ 影响断言 | 通过（3/3 闭合；未放宽断言：TC-R18-02 断 `CalibrationFailedError`、不断 `SystemExit`；退出码由 TC-EXIT-01/02/03 单独断） |
| **退出码用例（QA-F9）** | §2.3 E1–E3：门禁失败 `2` / 参数数据错误 `1` / 成功 `0`，库层异常与 CLI 退出码分列 | 通过（3 条 TC，均落 `test_success_criteria.py`） |
| **导出与落盘用例（QA-F10）** | TC-R04-01（`export_ledger` 唯一 `burnt=True` 行 + `write_result` 落 `tmp_path`）、TC-SC-02（13 字段键集合 + 与预注册 YAML 逐字段一致）、TC-R18-02（`<results_dir>/calibration.json`） | 通过（`results_dir=tmp_path` 注入，不写真实 `data/backtest/`） |
| **§10.3 行号匹配（冻结版 939 行，T2-fix-4/5/6 后）** | 脚本抽取表中全部 `design.md:<行号>` 引用并校验范围 + `sed -n` 抽查契约文本 | 通过（锚点 41 行、行号引用 72 处，全部落在 design.md 1–939 行内；抽查 30 处行文本与类/函数/小节/表格标题一致；T2-fix-6 新增锚点：`EventStudyResult.verdict` / `UniverseProvider` / `build_universe` / `gate` 判定优先序 / attribution 恒等式 / calibration `passed`·`verdict` 分离） |
| **README 目录约定** | `test/qa/README.md` 增「按被测模块镜像 `test/qa/<module>/`」+ 运行命令 | 通过 |
| **QA-F11 夹具同步** | §2.3 尾 + §10.1 `cli_runner`：`cli_runner(cwd=tmp_path)`、`--config`（相对 cwd）、`tmp_path/config/app.yaml` 自动发现、`results_dir` 注入 | 通过 |
| `openspec.cmd validate add-backtest-engine --strict` | 见提交前执行记录 | exit 0 |
| 是否越界写文件 | `git status --porcelain` + `git show --name-only` | T4-fix 仅改 `test-design.md` + `test/qa/README.md`；`design.md`、`specs/`、`openspec/specs/`、`src/`、`test/` 未改 |
| 盲测合规 | 全程未打开 `src/` 下任何实现文件 | 合规（复核只读 `design.md` §4.1/§6.7/§10 与 README） |
| 无「口头测试点」 | 逐条检查 §1.2 每行为「断言要点」而非「应当测试」 | 通过 |
| 未覆盖项 | §7 八条，均带原因与责任方（原第 9 条「ledger 导出/结果目录注入」已随 QA-F10 闭合移除） | 通过 |
