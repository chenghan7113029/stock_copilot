# Tasks: add-backtest-engine（回测模块任务拆解）

> change：`add-backtest-engine`　分支：`feature/add-backtest-engine`　角色：architect（T2）
> 本文件把 [`design.md`](design.md) 的 Decisions 拆成**可勾选、可验证**的步骤，供 T3（engineer 实现）与 T4（QA 验证）使用。
> 判据纪律（`openspec/config.yaml` tasks 规则 + `_shared.md`）：**勾选前必须先真实跑通对应命令**；测试未通过不得勾完成；证据（命令 + 退出码 + 输出）写进 `verification.md`。
> 环境事实（`docs/agent-team/ENV.md`）：命令名 `python`（无 `python3`）；`openspec` 必须写 `openspec.cmd`；排除联网与 legacy 时写 `-m "not network and not akshare_legacy"`。

## 阶段顺序（先数据与撮合 → 再指标与台账 → 最后事件研究与校准）

```text
Phase 1 契约与配置（models/config）      ← 一切的前置
Phase 2 数据对齐（data_provider/backtest + data + universe）
Phase 3 撮合（broker）
Phase 4 信号与指标（signal + metrics）
Phase 5 台账（registry）
Phase 6 校准与三级门禁（calibration + gates）
Phase 7 CLI 装配与端到端
```

---

## Phase 1 · 契约与配置（models / config）

- [x] **T2.1 定义回测契约 dataclass 与枚举（含 T4 findings 补齐的契约）**
  - 设计依据：design.md §4.1 全部 + §10 QA 反馈处理表（`AdjustMode` / `OrderStatus` / `Segment` / `Verdict` / `RunStatus` / `GateStage` / `PriceBar` / `FinancialRecord` / `GroupAssignment` / `PointInTimeSnapshot` / `EventSignal` / `EventObservation` / `ConditionSpec` / `PreregistrationSpec` / `Order` / `OrderAttempt` / `CostBreakdown` / `Fill` / `RunRecord`（含 `hypothesis_id`）/ `ExperimentRecord`（`K: int | None`、`row_type`）/ `Benchmark` / `WindowStats` / `EventStudyResult` / `AttributionResult` / `StabilityResult` / `CalibrationResult`（含 `corrected_p` / `verdict`）/ `GateRecord` / `GateCriteria` / `BacktestConfig`（全量 schema + 成本 spec `CommissionSpec/StampTaxSpec/TransferFeeSpec/SlippageTierSpec/LiquidityCapSpec`）/ `LedgerExportRow` + §4.1「异常清单」的 `BacktestError` 族 8 类）
  - 产出文件：`src/service/backtest/models.py`
  - 验证：`python -m pytest -q test/service/backtest/test_models.py`
  - 判定真伪：`PointInTimeSnapshot.__post_init__` 对 `trade_date > as_of` / `visible_from > as_of` 抛 `FutureDataError`（R10 负向）；`Fill.attempts` 可表达「封板失败→顺延成交」（QA-F7）；`ExperimentRecord.K=None` 可构造（QA-F8）；异常族按类型二分（QA-F5）；`PriceBar.avg_amount` 存在（T2-fix-5）；`AttributionResult.verdict` 存在且缺 `market_portfolio` → `INCONCLUSIVE`（T2-fix-5）。

- [x] **T2.2 定义 `BacktestConfig` 装载器（全量 config schema，缺键即拒绝 + 落盘路径可注入）**
  - 设计依据：design.md §4.1 `BacktestConfig`（全量 schema：必须键 `results_dir/registry_store_path/segments/windows/max_delay_days/min_events`；待 Q 键 `commission/stamp_tax/transfer_fee/slippage_tiers/liquidity_cap/limit_pct/seal_definition/suspend_source/cut_basis/tier_count/recompute_freq/min_group_size/gate_criteria/block_length/n_bootstrap/shrink/burn_scope/burn_counts_as_second/exception_approver/k_components/custom_allowed/k_cost_per_window`）+ `config.py`、否-2、R7、QA-F10、T2-fix-4
  - 产出文件：`src/service/backtest/config.py` + **`config/app.example.yaml`**（tracked，写 `backtest:` 示例段；`config/app.yaml` 是 gitignore 的本地副本，非契约源）
  - 验证：`python -m pytest -q test/service/backtest/test_config.py`
  - 判定真伪：必须键缺失 → `MissingBacktestConfigError`；待 Q 键缺值被消费处拒绝（不预埋默认）；`BacktestConfig(results_dir=tmp_path, registry_store_path=tmp_path/...)` 可注入（QA-F10）；`max_delay_days/min_events` 键存在但数值不预埋（T2-fix-4）；§9.3 落值（佣金 0.01254% 双边 / 印花税 0.1% 仅卖出 / 过户费 0.001% / 最低 5 元 / 滑点三档 / 流动性 20 日均额 1%）由 engineer 落 `config/app.example.yaml`（T2-fix-8）。

---

## Phase 2 · 数据对齐（data_provider/backtest + data + universe）

- [x] **T2.3 后复权/分段复权价格适配器（前复权拒绝）**
  - 设计依据：design.md §4.1 `data.py::load_price_series`、否-1、R9
  - 产出文件：`src/data_provider/backtest/adjust_price.py` + `test/data_provider/backtest/test_adjust_price.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_adjust_price.py`
  - 判定真伪：请求前复权（`adjust="qfq"`）抛错；后复权序列分红日前后持有期收益连续（R9 Scenario「分红日无假跳空」）；缺口抛 `BacktestDataGapError`。

- [x] **T2.4 撮合所需市场数据适配器（成交额/涨跌停/停牌）**
  - 设计依据：design.md §4.1 `market_rules.py`、R7/R8、KD-4-07/KD-3-07 缺口
  - 产出文件：`src/data_provider/backtest/market_rules.py` + `test/data_provider/backtest/test_market_rules.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_market_rules.py`
  - 判定真伪：取不到成交额/日均成交额（`avg_amount`）/涨跌停价/停牌标记 → `BacktestDataGapError`（不按 0/不按可成交/不退化）；`avg_amount`（日均成交额）是流动性上限数据源（T2-fix-5）。

- [x] **T2.5 退市/ST/历史成分适配器**
  - 设计依据：design.md §4.1 `universe.py::build_universe`、R12、A4
  - 产出文件：`src/data_provider/backtest/universe.py` + `test/data_provider/backtest/test_universe.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_universe.py`
  - 判定真伪：名单不可得 → 报缺口并停止；退市股退市日前计入、退市日后不计（R12 Scenario）。

- [x] **T2.6 财务公告日对齐适配器**
  - 设计依据：design.md §4.1 `financial_timing.py`、R11、KD-2-01/02/03 缺口
  - 产出文件：`src/data_provider/backtest/financial_timing.py` + `test/data_provider/backtest/test_financial_timing.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_financial_timing.py`
  - 判定真伪：年报 2023-12-31 报告期、公告日 2024-04-25 → 2024-04-24 的评估不含该字段（R11 Scenario）；缺 `ann_date` 走保守回退并标注。

- [x] **T2.7 数据对齐编排 `data.py`（时点视图构造 + 事件收益装载）**
  - 设计依据：design.md §4.1 `data.py`（`build_point_in_time` + `load_event_observations`）、R9/R10/R11/R17、T2-fix-4
  - 产出文件：`src/service/backtest/data.py` + `test/service/backtest/test_data.py`
  - 验证：`python -m pytest -q test/service/backtest/test_data.py`
  - 判定真伪：`build_point_in_time` 产出 `PointInTimeSnapshot`，任何 `trade_date/visible_from > as_of` 被拒绝（R10）；`visible_from = ann_date`（缺 ann_date 才回退 conservative_cutoff，spec R11 优先，非 max）；`load_forward_returns(signal, horizon)` + `load_benchmark_forward_returns(kind, signal, horizon)` 定 loader 形状，`load_event_observations` 按「逐日标的收益 − 逐日基准收益」产出 `EventObservation`（T2-fix-5）。

- [x] **T2.8 分组切点与成分 `universe.py`（季度重算，不回改历史）**
  - 设计依据：design.md §4.1 `assign_groups`、R15/R16、KD-6-05/KD-6-07
  - 产出文件：`src/service/backtest/universe.py` + `test/service/backtest/test_universe.py`
  - 验证：`python -m pytest -q test/service/backtest/test_universe.py`
  - 判定真伪：软标签/结果标签作为分组维度被拒；`cut_basis="all_a_cross_section"`（全 A 时点截面分位）、`tier_count=5`（Owner 二次确认「5 档」，5×5=25 组）、换档计入 K（§9.3，T2-fix-8/T2-fix-9）；2021Q2 重算不回改 2020 及之前分组（R15 Scenario）。

---

## Phase 3 · 撮合（broker）

- [x] **T2.9 成本计算（佣金/卖出印花税/滑点/过户费，四分量）**
  - 设计依据：design.md §4.1 `CostBreakdown`、R7、REF-03
  - 产出文件：`src/service/backtest/broker.py`（`CostCalculator` 部分）+ `test/service/backtest/test_broker.py`
  - 验证：`python -m pytest -q test/service/backtest/test_broker.py`
  - 判定真伪：10 万买入、11 万卖出 → 四分量与手算一致（R7 Scenario）；小额触发最低佣金标注；缺印花税率/最低额拒绝；流动性上限 = `avg_amount × max_participation`，`liquidity_cap` 缺 → `MissingBacktestConfigError`、`avg_amount` 缺 → `BacktestDataGapError`、多档无 adv 不退化单档（T2-fix-5）。

- [x] **T2.10 撮合状态机（T+1 / 封板顺延 / 停牌跳过 / 流动性上限）**
  - 设计依据：design.md §4.1 `execute_orders`、R8、KD-3-01/02/03
  - 产出文件：`src/service/backtest/broker.py`（`execute_orders`/`next_tradable_day`）+ `test/service/backtest/test_broker.py`
  - 验证：`python -m pytest -q test/service/backtest/test_broker.py`
  - 判定真伪：一字涨停买不进顺延、跌停卖不出顺延、当日买入当日卖出拒绝（`REJECTED_T1`）、停牌跳过；每笔留痕顺延天数/原因（R8 各 Scenario）；流动性超限截断标注。

---

## Phase 4 · 信号与指标（signal + metrics）

- [x] **T2.11 纯函数信号 `signal.py`（t 日及之前切片 → 事件/动作）**
  - 设计依据：design.md §4.1 `evaluate_condition(snapshot, condition: ConditionSpec)` + `EventSignal`/`ConditionSpec`、R10、KD-10-03、T2-fix-4
  - 产出文件：`src/service/backtest/signal.py` + `test/service/backtest/test_signal.py`
  - 验证：`python -m pytest -q test/service/backtest/test_signal.py`
  - 判定真伪：同一 t 切片 + 同一 `ConditionSpec` 重复输入 → 同输出（R10 Scenario「纯函数可复现」）；越界读 t+1 → `FutureDataError`；`ConditionSpec`（`condition_id/kind/params`）是信号唯一条件入参。

- [x] **T2.12 事件研究指标 `compute_event_study`（20/60 日双基准超额分布）**
  - 设计依据：design.md §4.1 `compute_event_study(observations: Sequence[EventObservation], *, cfg)` + `EventStudyResult`/`WindowStats`、R17/R13、REF-02、QA-F4、T2-fix-4
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：按 `benchmark_kind × window` 聚合双基准（买入持有 + 市场组合）的事件数/均值/中位数/标准差/CI/分年度/分市值组（R17 + R13）；`min_events` 未达 → 标注「样本不足」不出判定；CI 含 0 且校正后不显著 → 结论「无信号」；入参只收 `EventObservation`，不直接读价格；loader 夹具用 `load_forward_returns`/`load_benchmark_forward_returns` 造（T2-fix-5）。

- [x] **T2.13 统计推断 `block_bootstrap` + 多重比较校正**
  - 设计依据：design.md §4.1 `block_bootstrap`/`multiple_testing_correction`、R5/R6、KQ-2、T2-fix-4
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：报告名义样本 + 有效样本（时间块数）；默认不用 iid t 检验（R6）；`block_length/n_bootstrap` 来自 `cfg`（KQ-2），缺值即 `MissingBacktestConfigError`（不预埋默认）；K=1 与 K=50 同一 p 值判定翻转且都入台账（R5 Scenario）；K 缺失 → 拒绝标「有效」。

- [x] **T2.14 基准归因 + 稳定性分档 + 部分池化**
  - 设计依据：design.md §4.1 `attribution(returns, factors: dict[str, Sequence[float]], benchmarks: Sequence[Benchmark])` + `AttributionResult` / `stability` + `StabilityResult` / `partial_pooling`、R13/R14/R16、KQ-3/KQ-7、QA-F4、T2-fix-4
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：`returns` 键集固定 `{"rule","market_portfolio"}`（同长）；`beta` 由 `returns["rule"]` 对 `returns["market_portfolio"]` 回归推导（不入参）；缺 `market_portfolio` → 返回 `AttributionResult(verdict=INCONCLUSIVE, beta=None, unexplained=None)`（不抛异常，T2-fix-5）；`factors` 键集固定 `{size,value,momentum}`，缺键 → `MissingBacktestConfigError`；双基准各出四项暴露与贡献 + `unexplained`（R13）；全期显著但 80% 贡献来自单一年度 → `scope_note` 标注「仅在 2015 年有效」（R14）；单票绝对收益预测不返回、只返回组内分位（R16）。

---

## Phase 5 · 台账（registry）

- [x] **T2.15 实验台账 append-only + 执行行/结果行 + 哈希校验 + 注入点 + 导出**
  - 设计依据：design.md §4.1 `ExperimentRegistry(store_path, *, clock, data_version, results_dir)` + `append_run`/`append`/`get`/`next_experiment_id`/`validate_preregistration`/`write_result`/`export_ledger` + `RunRecord`/`ExperimentRecord`/`LedgerExportRow`、R1/R2/R4、台账存储机制、QA-F2/QA-F3/QA-F6/QA-F8/QA-F10
  - 产出文件：`src/service/backtest/registry.py` + `test/service/backtest/test_registry.py`
  - 验证：`python -m pytest -q test/service/backtest/test_registry.py`
  - 判定真伪：同一预注册执行两次 → 两行、`experiment_id = f"{hypothesis_id}-{seq:04d}"` 两值不同；改已写入行 → 抛 `RegistryCorruptedError` + 执行行留痕（无 UPDATE/DELETE）；改假设 → 新实验 + `parent_experiment_id`（R2 各 Scenario）；`RunRecord(status=REJECTED/FAILED)` 可追加留痕且带 `hypothesis_id`（T2-fix-4）；`validate_preregistration` 缺键报错含字段名；`export_ledger()` 返回 `LedgerExportRow` 清单且 `burnt=True` 体现额度用尽（QA-F10）；`write_result` 落盘到注入的 `results_dir`；`mark_burnt` 追加执行行 `reason="样本外已烧毁"`（T2-fix-4）。

- [x] **T2.16 样本外烧毁 + K 累计**
  - 设计依据：design.md §4.1 `assert_not_burnt/mark_burnt/cumulative_K`、R3/R4/R5、QA-F2/QA-F5
  - 产出文件：`src/service/backtest/registry.py` + `test/service/backtest/test_registry.py`
  - 验证：`python -m pytest -q test/service/backtest/test_registry.py`
  - 判定真伪：`mark_burnt` 追加唯一执行行 `RunRecord(reason="样本外已烧毁", hypothesis_id, experiment_id, at)`（不可撤销，含时间戳 + 实验 ID）；`burn_scope="hypothesis"`（按假设计，换实现/换指标不算第二次）、旧样本外 `expired` 留档（§9.3，T2-fix-8）；二次请求抛 `RegistryImmutableError` 并落 `RunRecord(status=REJECTED)` 留痕；新实验独立额度（R4 各 Scenario）；`cumulative_K` 按 `k_components[]` 累计；导出 `burnt` 按「是否存在 `reason="样本外已烧毁"` 执行行」派生（T2-fix-4）。

---

## Phase 6 · 校准与三级门禁（calibration + gates）

- [x] **T2.17 已知答案校准门禁 `calibration.py`**
  - 设计依据：design.md §4.1 `run_calibration/assert_calibrated` + `CalibrationResult`（`passed/direction/ci/K/corrected_p/verdict`）、R18、KD-10-01/02、KQ-1/KQ-5/KQ-6、QA-F5/QA-F8/QA-F9
  - 产出文件：`src/service/backtest/calibration.py` + `test/service/backtest/test_calibration.py`
  - 验证：`python -m pytest -q test/service/backtest/test_calibration.py`
  - 判定真伪：「跌破 MA60」跑全 A 显著跑输买入持有 → `CalibrationResult(verdict=INVALID, passed=True)` 标记台子可信；复现不出 → **库层 `assert_calibrated` 抛 `CalibrationFailedError`（QA-F9）** + 台账落 `RunRecord(status=FAILED)` 记校准失败；校准失败不被表述为「策略无效」（R18 各 Scenario）；校准口径全 spec 固定（不新增 `calibration.*` 键），成本走 `broker.execute_orders` 真实四分量、Q4 缺即拒绝（不采用比例成本近似，T2-fix-5）。

- [x] **T2.18 三级门禁状态机 `gates.py`**
  - 设计依据：design.md §4.1 `GateStateMachine(registry, *, cfg)` + `GateCriteria`、R19、否-3、KD-9-01/06、Q7/KQ-4、T2-fix-4
  - 产出文件：`src/service/backtest/gates.py` + `test/service/backtest/test_gates.py`
  - 验证：`python -m pytest -q test/service/backtest/test_gates.py`
  - 判定真伪：判据来自 `cfg.gate_criteria`（`backtest.gates`），缺失/None → `transition` 抛 `MissingBacktestConfigError`（不允许 transition）；回测未通过 → 拒进影子；影子期 **< 3 个月**（KQ-4 修正，3 个月起、12 个月封顶、按交易日、规则改则清零）→ 拒进实盘；「方向一致」= 同号且年化差 ≤ 回测年化波动 50%、实盘上限 = min(权益 10%, 单票 1%)（§9.3，T2-fix-8）；跳级抛 `GateSkipError` 并留痕；每规则唯一状态可查询且带每级通过时间与实验 ID（R19 各 Scenario）。

---

## Phase 7 · CLI 装配与端到端

- [x] **T2.19 CLI 子命令装配（在既有 `src/apps/cli.py` 内扩展 + 配置解析 + 退出码）**
  - 设计依据：design.md §4.0/§6.3（入口 = 既有 `src/apps/cli.py`，`main(argv) -> int`，不另建入口文件）、B 项（pipeline 装配）、QA-F9/QA-F10/QA-F11
  - 产出文件：`src/apps/cli.py`（扩展，新增 `backtest preregister/run/calibrate/ledger/gate`）+ `pyproject.toml`（`[project.scripts]` 既有 `backtest` 入口不变）+ `test/apps/test_cli.py`（扩展）
  - 验证：`python -m pytest -q test/apps/test_cli.py`
  - 判定真伪：`backtest preregister` 写预注册文件并取到 commit；`backtest run` 缺预注册 → `exit 1` 且无结果行（R1）；`--config <path>`（相对路径按 cwd）覆盖默认 `cwd/config/app.yaml`（QA-F11）；`backtest ledger --experiment <id> --format json` 输出 `LedgerExportRow` JSON 数组（QA-F10）；`backtest calibrate` 门禁失败 → 捕获 `CalibrationFailedError` 后 `sys.exit(2)`（QA-F9）；`backtest calibrate` 无论成败写 `<results_dir>/calibration.json`（QA-F11）；`custom_allowed=true`（允许 20/60 之外窗口）且每额外窗口计入 K（`k_cost_per_window=1`，§9.3，T2-fix-8）。

- [x] **T2.20 端到端 + 全量门禁**
  - 设计依据：proposal `## 成功标准` 5 条 + design.md §6.6/6.7
  - 产出文件：`test/qa/backtest/*`（QA 盲测负向/边界用例，见 design.md §6.7）
  - 验证：
    - `python -m pytest -q test/service/backtest`
    - `python -m pytest -q test/data_provider/backtest`
    - `python -m pytest -q test/qa/backtest`
    - `python -m pytest -q -m "not network and not akshare_legacy"`
    - `python -m ruff check .`
    - `openspec.cmd validate add-backtest-engine --strict`
  - 判定真伪：5 条成功标准逐条由命令输出支撑（校准可复现 / 台账可审计 / 样本外只烧一次 / 成本手算复算 / 无未来函数证伪）；QA 退出码契约（TC-EXIT-01/02/03：门禁失败 `2` / 参数·数据错误 `1` / 成功 `0`）与 `calibration.json` 写出（QA-F11）由 `test/qa/backtest/` 的校准与退出码用例覆盖。

---

## 完成判定

- [x] 上述 T2.1–T2.20 全部勾选，且每个勾选前有 `verification.md` 里的命令 + 退出码 + 输出证据。
- [x] `openspec.cmd validate add-backtest-engine --strict` 通过（退出码 0）。
- [x] 未触碰 `openspec/specs/`、未改 K1 的 `config/knowledge/_design.md` 层语义、未改 `proposal.md`/`specs/`/`knowledge-delta.md`。

> 本波（T2）只产出 `design.md` + `tasks.md`，**不执行上述 T2.1–T2.20**；它们是 T3 实现波的施工图，由 T4 QA 按 `test/qa/` 用例证伪。

---

## T3 实现记录（engineer，2026-11-15）

> 证据真源：[`verification.md`](verification.md)（逐条命令 + 退出码 + 输出摘要）。本节只记「做了什么 / 偏离了什么 / 闸门状态」。

### 交付物

- `src/service/backtest/`：`models.py` / `config.py` / `data.py` / `universe.py` / `signal.py` / `broker.py` / `metrics.py` / `registry.py` / `calibration.py` / `gates.py`（design §6.1 的 10 文件，未自创结构）。
- `src/data_provider/backtest/`：`__init__.py` / `adjust_price.py` / `market_rules.py` / `universe.py` / `financial_timing.py`（§6.2）。
- `src/apps/cli.py`：新增 `backtest preregister|run|calibrate|ledger|gate`（§6.3，不另建入口）；`src/common/exceptions.py`：8 类回测异常。
- `config/app.yaml` 与 `config/app.example.yaml`：新增 `backtest:` 段（**只放键与空值**，无费率/税率/滑点/块长/收缩强度）。
- `test/service/backtest/`（10 文件 + conftest）、`test/data_provider/backtest/`（4 文件）、`test/apps/test_cli_backtest.py`：**126 单测全绿**。

### 偏离 / 契约补充（供 architect 裁决，见 verification.md §4）

1. `EventObservation`（新增 dataclass）：`compute_event_study` 的入参在 design 中为 `events`，但 `EventSignal` 只有 `condition_id/event_date`、无收益，无法计算超额。**属契约层补充，需 architect 裁决**（captain 已裁定不由 engineer 单方定）。
2. `ConditionSpec`（新增 dataclass）：design §4.1 签名引用但未定义字段。
3. `RunRecord` 增 `hypothesis_id`（`data_version` 按 captain R1-04 裁定补）：前者是 captain R1-03 的 join 键所需。
4. `mark_burnt` 形态：append 一条 `burnt=True` 标记行（同实验 ID + `timestamps["burnt_at"]`），`get` 取最新行；满足 R4「写入标记」+ R2 append-only。
5. `GateStateMachine(store_or_registry, *, cfg, clock)`：门禁拒绝额外落 `RunRecord(REJECTED)`；`evidence_experiment_ids` 用级名 `backtest/shadow/live`。
6. config 键形状由 engineer 定义（design 未给键清单，captain 已确认根因在 design）：`commission{rate,min}` / `stamp_tax{sell_rate}` / `transfer_fee{included,rate}` / `slippage_tiers[{amount_lower,amount_upper,bps}]` / `liquidity_cap[{amount_lower,amount_upper,max_participation}]` / `max_delay_days` / `gates{backtest_pass,shadow_min_months,...}` / `calibration{...}` / `segments{...}`；未确认项在 `config/app.yaml` 一律空值。
7. R11 `visible_from`：按 **spec R11 Scenario1** 取 `ann_date`（缺失才回退法定截止日）；design §4.1 的 `max(ann_date, cutoff)` 与 spec 冲突，按任务书「spec 为最终判据」执行，未改 design。

### 闸门状态（如实）

- `python -m pytest -q -m "not network and not akshare_legacy" --ignore=test/qa` → **955 passed / exit 0**（**过程证据，不替代全量闸门**）。
- 含 QA（commit `0cc6f85`）的 `test/qa/backtest/` 全量跑 → **977 passed / 31 failed / 3 errors / exit 1**：红点全部来自 QA 盲测草稿与冻结 design 的夹具形状差异（详见 `verification.md` §3），**engineer 未改 `test/qa/`、未为过闸门放宽断言**。
- 结论：T3 实现与 engineer 单测完成；**全量闸门未通过**，待 t15（architect 补 config schema + 裁决契约歧义）后由 t17 对齐，再由 T5 复核。

---

## T3-align 记录（engineer，t17；按 t15 补后契约）

> 基线：`5f8f631`（design §4.1 + §10 T2-fix-4）。本波**不再单方改契约**，只把实现/单测对齐到补后契约。
> 证据：`pytest test/service/backtest` 115 passed、`pytest -m "not network and not akshare_legacy" --ignore=test/qa` 978 passed、`ruff` scoped 0、`compileall` 0、`openspec validate --strict` 0（均为 exit 0）。

### 对齐的契约点（实现 + 单测同步）

| # | 契约（t15） | 实现对齐 |
| --- | --- | --- |
| 1 | `BacktestConfig` 全量 schema（必须键 `results_dir/registry_store_path/segments/windows/max_delay_days/min_events`；待 Q 键 22 个；成本 spec `CommissionSpec/StampTaxSpec/TransferFeeSpec/SlippageTierSpec/LiquidityCapSpec`；`GateCriteria`） | `models.py` 重写为类型化字段 + `from_config` 形状/必须键校验（缺键即 `MissingBacktestConfigError`；待 Q 值缺失 = `None`，消费处拒绝）；`config/app.example.yaml`（tracked）按 design 写全 28 键、数值留空；`config/app.yaml` 同步为本机副本 |
| 2 | 事件收益载体 `EventObservation{code,event_date,condition_id,benchmark_kind,excess_returns}` + `ConditionSpec` + `load_event_observations(signals, benchmarks, *, loader, cfg)` | `models.py` 按 5 字段实现；`data.py` 新增 `load_event_observations`（逐日超额，`horizon=max(cfg.windows)`）；`signal.py` 条件类型固定 `ma60_breakdown`、参数只 `{window}` |
| 3 | `compute_event_study(observations, *, cfg)`（**无 benchmarks 参数**） | `metrics.py` 改为只收 `EventObservation`，按 `benchmark_kind × cfg.windows` 聚合；窗口超额 = `excess_returns[:window]` 之和（CAR）；`block_length/n_bootstrap` 取自 cfg（None → 拒绝） |
| 4 | `GateStateMachine(registry, *, cfg)`（**无 clock 形参**）；判据来自 `cfg.gate_criteria`，缺失 → `MissingBacktestConfigError` | `gates.py` 构造收齐为 `(registry, *, cfg=None)`；时间戳/持久化经 `registry.clock` 与 `registry.store_path`；判据缺失直接拒绝 transition（不留痕、不降级）；跳级仍抛 `GateSkipError` + 追加 `RunRecord(REJECTED)` |
| 5 | `mark_burnt` 追加执行行 `RunRecord(reason="样本外已烧毁", hypothesis_id, experiment_id, at)`；导出 `burnt` 由此派生 | `registry.py` 实现为 append `RunRecord(status=RUNNING, reason=退出标记常量)`，同一假设幂等、换实验拒绝；`export_ledger` 的 `burnt` = 存在该执行行（或结果行快照） |
| 6 | `attribution(returns, factors, benchmarks)`：beta 由 `market_portfolio` 回归推导（不入参）、`factors` 键集固定 `{size,value,momentum}`、缺 `market_portfolio` → 归因 INCONCLUSIVE | `metrics.py` 实现：`returns` 支持映射 `{strategy, market_portfolio}`；缺因子键/缺基准序列 → 拒绝；beta = cov/var 市场收益 |
| 7 | R11 `visible_from = ann_date`（缺才回退，spec 优先） | 已在 `data.py` + `financial_timing.py` 按 spec 实现（本次未改） |

### 回退 / 删除（t13 自定、与补后契约冲突的部分）

1. `BacktestConfig.params` + `require()/get()/missing()/require_keys()` 访问器 → 类型化字段（design schema），删除自定键 `prereg_dir/data_version/trading_calendar/alpha/correction_method/calibration.*/stability.*/segments 边界映射`。
2. `GateStateMachine(store_or_registry, *, cfg, clock)` → `(registry, *, cfg)`；删除 `clock` 形参与 Path 构造（时钟改由 registry 注入）。
3. `execute_orders(..., positions=...)` → 回到 design 签名 `(orders, prices, *, cfg)`；T+1 持仓来源 = 同批次 Buy 成交日。
4. `EventObservation` 旧字段 `window/excess/cap_tier` → 契约 5 字段。
5. `LiquidityRules` 的「按成交金额匹配档位」→ design 的 `{adv_tier, max_participation}`（单档可用；多档缺 adv_tier 数据源 → `BacktestDataGapError`）。
6. 校准题的自定 `calibration.*` 配置键 → 删除（见下方残余歧义 3）。

### 保留

- `RunRecord.data_version`（captain R1-04 裁定）。
- `ConditionSpec` / `EventObservation`（t15 已采纳）。
- 8 类回测异常、`PreregistrationSpec` 校验/读写、`segment_of`/`SEGMENT_YEAR_RANGES`（spec R3 常量）、CLI `build_backtest_loader` 注入点（patch 点）。

### 残余歧义（**未自行补**，待 architect 裁决）

1. `load_event_observations` 的 loader 取数形状：`EventSignal` 无 `code`，本波定义为 `load_forward_returns(signal, horizon) -> (code, 逐日收益)` + `load_benchmark_forward_returns(kind, signal, horizon)`；design 未固定，需裁决是否写进契约。
2. `attribution` 的市场基准收益来源：design 只写「beta 由 market_portfolio 基准收益回归推导（不入参）」但 `Benchmark{kind,label}` 无序列字段；本波把序列放进 `returns` 映射（`strategy` + `market_portfolio`）。另 `AttributionResult` 无 verdict 字段，故「缺 market_portfolio → INCONCLUSIVE」用 `BacktestError` 文案表达，判定由调用方结果行承担。
3. 校准题参数：schema 无 `calibration.*`/`alpha`。本波取 spec 固定值：区间 = R3 三段年份（2015-01-01 ~ 2026-12-31）、窗口 = `cfg.windows` 的最大值、K = 校准执行次数（执行行可数）、「显著」判据 = CI 不含 0（KQ-5 未答复）、成本 = 比例口径近似（佣金×2 + 卖出印花税 + 首档滑点×2，notes 标注）、次新股沿用 MA20 替代（KQ-1 未答复，notes 标注）。需 architect 确认是否补 `calibration.*` 键。
4. `liquidity_cap` 多档需要「日均成交额 → adv_tier」数据源；本机缺口，多档配置直接 `BacktestDataGapError`。

### 闸门状态

- 前 5 条验收命令全部 exit 0（engineer 套件 115 passed；`--ignore=test/qa` 978 passed；ruff/compileall/openspec 绿）。
- 全量含 QA：**24 failed / 1010 passed / exit 1**（t13 时 31 failed + 3 errors → 本次消除 7 条红点 + 全部 3 个 collection error；余下红点均为 QA 盲测夹具/调用面与补后契约不一致，见 T5）。

---

## T3-align-2 记录（engineer，t21；按 t18 T2-fix-5 裁决）

> 基线：`c0f0507`（design §4.1 `PriceBar.avg_amount` / `AttributionResult.verdict` / loader 形状 / 「校准口径 spec 固定」）。本波只改实现与 engineer 单测，不改 design/spec/test/qa。
> 证据：`pytest test/service/backtest test/data_provider/backtest test/apps/test_cli_backtest.py` **157 passed**；`pytest -m "not network and not akshare_legacy" --ignore=test/qa` **986 passed**；ruff scoped 0；`compileall` 0；`openspec validate --strict` 0。

### 5 点各自落点

| # | t18 裁决 | 实现改动 |
| --- | --- | --- |
| 1 | `PriceBar.avg_amount`（日均成交额，元）；liquidity 单/多档都依赖它；无 adv 数据 → `BacktestDataGapError`；多档不退化单档；`liquidity_cap` 未配置 → `MissingBacktestConfigError` | `models.py::PriceBar` 增 `avg_amount: float \| None`；`data.py::_to_price_bar` 映射该字段；`data_provider/backtest/market_rules.py` 把 `avg_amount` 列入必取字段（缺失即缺口）并并入撮合字段；`data_provider/backtest/adjust_price.py` 透传；`broker.py::LiquidityRules.from_config` 在 `liquidity_cap is None` → `MissingBacktestConfigError`、多档 → `BacktestDataGapError`；`_run_order` 用 `bar.avg_amount × max_participation` 截断，`avg_amount is None` → `BacktestDataGapError` |
| 2 | `AttributionResult.verdict` + `beta/unexplained` 可空；`attribution(returns: dict{"rule","market_portfolio"}, factors: dict{"size","value","momentum"})`；缺 `market_portfolio` → 返回 `verdict=INCONCLUSIVE, beta=None, unexplained=None`（不抛异常）；缺因子键 → `MissingBacktestConfigError` | `models.py::AttributionResult` 增 `verdict`、`beta/unexplained` 改 `Optional`；`metrics.py::attribution` 改签名（删 `benchmarks` 参数），缺 market 键返回 INCONCLUSIVE（exposures 省略 beta），factor 缺键仍 `MissingBacktestConfigError` |
| 3 | loader 形状：`load_forward_returns(signal, horizon) -> (code, 逐日收益)` + `load_benchmark_forward_returns(kind, signal, horizon) -> 逐日基准收益`；`excess_returns[t] = 标的 − 基准`；`H = max(cfg.windows)` | `data.py::load_event_observations` 已按该形状实现并加注释；单测夹具统一改为这两个方法（`test_data.py` / `test_calibration.py` / `test_cli_backtest.py`） |
| 4 | 校准口径全 spec 固定（不新增 `calibration.*` 键）：区间=R3、窗口=`max(cfg.windows)`、K=校准执行次数、显著=CI 不含 0、撮合走正式路径、成本=broker 四分量（Q4 缺键即拒绝）、**不得用比例成本近似**；KQ-1 沿用 MA20 替代并标注 | `calibration.py` 重写事件收益计算：每个事件用 `broker.execute_orders`（SELL，`requested_qty=LOT_SIZE`）取正式撮合与 `Fill.cost` 四分量，超额 = `-cost/filled_amount - hold_return`；删除 `_cost_rate` 比例近似与 `CALIBRATION_COST_NOTE`；`params` 增 `cost_model="broker_four_components"`、`match_engine="execute_orders"`；notes 明示「不使用比例成本近似」+ KQ-1 标注；Q4 缺键 → `MissingBacktestConfigError` |
| 5 | 同步 engineer 单测 + tasks 说明 | 单测：`test_models`（avg_amount / AttributionResult 字段）、`test_broker`（avg_amount 缺口、liquidity 未配置、多档不退化）、`test_metrics`（新 attribution 契约/缺 market → INCONCLUSIVE）、`test_data`（loader 形状 + avg_amount 映射）、`test_calibration`（四分量口径 + Q4 缺键拒绝）、`test_market_rules`（avg_amount 必取） |

### 明确事项

- **未采用比例成本近似**：校准成本只走 `broker.execute_orders` 的佣金/印花税/滑点/过户费四分量；Q4 成本键缺失即 `MissingBacktestConfigError`。
- 残余（非契约）：`avg_amount` 属本机数据缺口（KD-4-07）；QA 夹具造 `PriceBar` 时需补 `avg_amount`，否则撮合按 R7 报缺口（这是 R7/T2-fix-5 的预期行为）。
- 全量含 QA：**24 failed / 1018 passed / exit 1**（与 t17 的 24 failed 数量持平，无新增红点；余下为 QA 夹具/调用面待 T5）。

---

## 附录 A：T3 验收原文（8 条，T2-fix-6 / t22 落盘，逐字抄自 t13 契约）

> 用途：T5（verification）逐条核对时的**唯一权威原文**。来源 = 任务清单 t13 的 `acceptance` 字段（team 状态内）。原 t14 曾报「T3 验收原文未落盘」（F11），本附录补上。

1. `tasks.md` 的 T2.1–T2.20 全部勾选，且每条对应验证命令真实跑过（输出贴进任务产物）
2. 全量单测绿：`python -m pytest -q -m "not network and not akshare_legacy"` 退出码 0
3. `python -m compileall -q src test` 退出码 0
4. `python -m ruff check src/service/backtest src/data_provider/backtest src/apps/cli.py test/service/backtest` 新增错误 0（既有 39 个基线不修）
5. `openspec.cmd validate add-backtest-engine --strict` 退出码 0
6. 静态自证：`src/service/backtest` 与 `src/data_provider/backtest` 内无 openai/LLM 调用；`src/` 内无 `import ref.`
7. `config/app.yaml` 的 `backtest:` 段只有键与注释，无任何未确认数值（佣金/印花税/滑点等）
8. 台账 append-only 有测试：篡改已写行被拒、失败也落执行行（RunRecord FAILED）

### 证据归属说明（F13，T2-fix-6）

- `verification.md` 本波归 **T5**（t14/t20）撰写与维护；本文件（tasks.md）不复制其证据正文，只给「T3 验收原文」供 T5 引用。
- t13 的 T3 实现证据在 `HEAD~1`（即 t13 提交链 `bab72ad` / `04a7c09`；对齐后的最终实现证据在 t17 `d9c860a`、t21 `a6db784`），不因后续 design 修订丢失。

---

## T3-align-3 记录（engineer，t23；按 t22 T2-fix-6 实现 F7/F8/F9）

> 基线：`ba5265f`（design §4.1 `EventStudyResult.verdict` / `UniverseProvider` / gate 优先序 / attribution 恒等式 / CalibrationResult 语义）。本波只改实现与 engineer 单测。
> 证据：`pytest test/service/backtest test/data_provider/backtest test/apps/test_cli_backtest.py` **174 passed**；`--ignore=test/qa` **1003 passed**；ruff scoped 0；compileall 0；openspec validate 0。

### F7 空观测

- `models.py::EventStudyResult` 增 `verdict: Verdict`（首字段）；`metrics.py::compute_event_study(())` 直接返回 `EventStudyResult(verdict=INCONCLUSIVE, windows={}, n_events=0, inference_method="block_bootstrap", block_length/cfg…)`，**不抛异常**；非空时 `verdict` 由 `_study_verdict`（样本不足→INCONCLUSIVE；任一窗口 CI 不含 0→VALID；否则 INVALID）给出；CLI 结果行直接采用 `result.verdict`（删除重复判定函数）。

### F8 UniverseProvider

- `service/backtest/universe.py`：新增 `@runtime_checkable UniverseProvider`（`historical_constituents(as_of, scope)` / `delisted_codes(as_of)` / `st_status(code, as_of)`）与 `build_universe(as_of, universe_scope: str, *, provider)`；任一方法不可得/抛错 → `BacktestDataGapError`；成分可得但为空 → 空 tuple（合法）；退市名单剔除（退市日前不在名单→计入）；ST 逐票按时点查询且**不剔除**（R12）。
- `data_provider/backtest/universe.py::UniverseAdapter` 补三个协议方法（`fetch` 以 `kind="constituents"/"delisted"/"st"` 分派；无源即缺口；成分空合法），保留原 `load_members/load_flags` 供 `BacktestDataLoader` 使用。

### F9 gate 优先序

- `gates.py::GateStateMachine.transition` 重排为 ① 边合法性（跳级/回退/同态/已拒绝 → `GateSkipError` + `append_run(REJECTED)`）② 判据可用性（`cfg.gate_criteria` 为 None/缺该级键 → `MissingBacktestConfigError`，**不落业务拒绝行**，design 明文）③ 达成性（evidence 不满足 → `GateSkipError` + `append_run(REJECTED)`）；三段分别落 `_validate_edge` / `_ensure_criteria` / `_validate_attainment`。

### 两条期望修正（已钉进单测）

- `attribution`：`Σcontributions + unexplained == mean(returns["rule"])`（`test_attribution_identity_sum_plus_unexplained_equals_mean_rule`，abs=1e-12）。
- `CalibrationResult`：`passed`（台子可信）与 `verdict`（所测规则有效性）分离、不互相推导（`test_passed_and_verdict_are_separate_fields`：通过→`passed=True, verdict=INVALID`；未复现→`passed=False, verdict=INCONCLUSIVE`；dataclass 允许二者独立组合）。

### 同步单测

`test_models`（EventStudyResult.verdict 字段）、`test_metrics`（空观测不抛异常 + 非空 verdict + attribution 恒等式）、`test_universe`（SpyProvider：退市/ST 时点/空名单合法/不可得缺口/缺方法缺口）、`test_data_provider/backtest/test_universe`（三协议方法 + 无源缺口）、`test_gates`（边先于判据、判据缺失不落拒绝行、达成性失败落拒绝行）、`test_calibration`（passed/verdict 分离）。

### 闸门状态

- 5 条验收命令全部 exit 0（engineer 174 passed / `--ignore=test/qa` 1003 passed / compileall 0 / ruff 0 / openspec 0）。
- 全量含 QA：**8 failed / 1051 passed / exit 1**（t21 时 24 failed → 本次消除 16 条）。余下 8 条为 QA 侧尚未按 t22 更新的旧夹具（`EventStudyResult` 未传 `verdict`、旧 provider 形状、断言「结果不得带 verdict」等），归 T5 更新用例，engineer 未改 `test/qa/`。

---

## T3-repair 记录（engineer，t29；R2-01：零触发 ≠ 数据缺口）

> 触发：T6 白盒评审 R2-01（medium）——`load_event_observations` 把规则零触发当成数据缺口，导致 F7 的「空观测 → INCONCLUSIVE」在 CLI `run` 路径不可达（违反 spec R17「允许无信号」）。本波只改实现与 engineer 单测。

### 两种语义（拆分后）

| 情形 | 语义 | 行为 |
| --- | --- | --- |
| 事件数为 0（规则零触发） | **合法结果**（无信号） | `load_event_observations([], ...)` → **空序列**（不访问 loader）；`compute_event_study(())` → `verdict=INCONCLUSIVE, windows={}, n_events=0`；CLI 退出码 **0**，写结果行 + 结果 JSON |
| 数据不可得（价格/基准序列/财务快照取不到、Loader 缺取数方法、事件后收益不足） | **错误**（不可算） | 仍抛 `BacktestDataGapError`（CLI 记 FAILED 执行行、退出码 1） |

### 调用链修正

- `data.py::load_event_observations`：`signals` 为空 → `return ()`（在基准/loader 校验**之前**，零事件不取数）；非空时保持原缺口语义。
- `apps/cli.py::_run_backtest_experiment`：`result.windows` 为空时 `corrected_p=None`（不调用 `_primary_sample`，避免空窗口取值）；`verdict` 直接用 `result.verdict`（INCONCLUSIVE），仍写 `RunRecord(PASSED)` + 结果行 + `write_result`；退出码 0。
- `apps/cli.py::_primary_corrected_p`：空 `windows` 早退 `None`（防御）。
- `calibration.py`：全 A 名单为空 → `BacktestDataGapError`（数据不可得，不是「无信号」）；扫描事件**之前**先 `CostCalculator.from_config(cfg)`，使零事件也不能绕过 Q4「缺键即拒绝」。

### 单测（两条路径各有覆盖）

- `test_data.py`：`test_load_event_observations_zero_signals_is_empty_not_gap`（loader 为 `object()` 也不报错）、`..._zero_signals_without_benchmarks_is_empty`。
- `test_cli_backtest.py::test_run_zero_trigger_reaches_inconclusive_exit_0`：横盘价格 → 零事件 → **exit 0**，结果行 `verdict=inconclusive`，`metrics.event_study.windows=={} / n_events==0 / verdict=="inconclusive"`、`n_observations==0`、`corrected_p is None`，结果 JSON 落盘，stderr 无「预注册缺失/数据缺口」。
- `test_calibration.py`：`test_calibration_empty_universe_is_data_gap`（空名单 → 缺口）、`test_calibration_requires_q4_costs_even_with_zero_events`（零事件 + Q4 缺键 → `MissingBacktestConfigError`）。

### 闸门（本波实测）

- trio：`pytest test/service/backtest test/data_provider/backtest test/apps/test_cli_backtest.py` → **179 passed**（exit 0）。
- 全量：`pytest -m "not network and not akshare_legacy"` → **1064 passed / 35 deselected**（exit 0）；`pytest test/qa/backtest` → **56 passed**。
- `ruff`（本 change 路径）All checks passed；`compileall` 0；`openspec validate --strict` 0。

> R2-02（HFQ 硬编码）与 R2-03（gates.ndjson 未走 registry）不在本任务，留 T7。
