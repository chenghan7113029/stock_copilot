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

- [ ] **T2.1 定义回测契约 dataclass 与枚举**
  - 设计依据：design.md §4.1（`AdjustMode` / `OrderStatus` / `Segment` / `Verdict` / `GateStage` / `PriceBar` / `FinancialRecord` / `GroupAssignment` / `PointInTimeSnapshot` / `EventSignal` / `Order` / `CostBreakdown` / `Fill` / `ExperimentRecord` / `CalibrationResult` / `GateRecord`）
  - 产出文件：`src/service/backtest/models.py`
  - 验证：`python -m pytest -q test/service/backtest/test_models.py`
  - 判定真伪：`PointInTimeSnapshot.__post_init__` 对 `trade_date > as_of` / `visible_from > as_of` 抛 `FutureDataError`（R10 负向）。

- [ ] **T2.2 定义 `BacktestConfig` 装载器（缺键即拒绝）**
  - 设计依据：design.md §4.1 `config.py`、否-2、R7「费率配置缺失时拒绝执行」
  - 产出文件：`src/service/backtest/config.py` + `config/app.yaml` 的 `backtest:` 段（键形态见 K1 §12.1，**不填数值**）
  - 验证：`python -m pytest -q test/service/backtest/test_config.py`
  - 判定真伪：构造缺 `commission`/`stamp_tax`/`slippage_tiers` 的配置 → 抛 `MissingBacktestConfigError`，`exit != 0`；不含任何预埋默认业务值。

---

## Phase 2 · 数据对齐（data_provider/backtest + data + universe）

- [ ] **T2.3 后复权/分段复权价格适配器（前复权拒绝）**
  - 设计依据：design.md §4.1 `data.py::load_price_series`、否-1、R9
  - 产出文件：`src/data_provider/backtest/adjust_price.py` + `test/data_provider/backtest/test_adjust_price.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_adjust_price.py`
  - 判定真伪：请求前复权（`adjust="qfq"`）抛错；后复权序列分红日前后持有期收益连续（R9 Scenario「分红日无假跳空」）；缺口抛 `BacktestDataGapError`。

- [ ] **T2.4 撮合所需市场数据适配器（成交额/涨跌停/停牌）**
  - 设计依据：design.md §4.1 `market_rules.py`、R7/R8、KD-4-07/KD-3-07 缺口
  - 产出文件：`src/data_provider/backtest/market_rules.py` + `test/data_provider/backtest/test_market_rules.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_market_rules.py`
  - 判定真伪：取不到成交额/涨跌停价/停牌标记 → `BacktestDataGapError`（不按 0/不按可成交）。

- [ ] **T2.5 退市/ST/历史成分适配器**
  - 设计依据：design.md §4.1 `universe.py::build_universe`、R12、A4
  - 产出文件：`src/data_provider/backtest/universe.py` + `test/data_provider/backtest/test_universe.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_universe.py`
  - 判定真伪：名单不可得 → 报缺口并停止；退市股退市日前计入、退市日后不计（R12 Scenario）。

- [ ] **T2.6 财务公告日对齐适配器**
  - 设计依据：design.md §4.1 `financial_timing.py`、R11、KD-2-01/02/03 缺口
  - 产出文件：`src/data_provider/backtest/financial_timing.py` + `test/data_provider/backtest/test_financial_timing.py`
  - 验证：`python -m pytest -q test/data_provider/backtest/test_financial_timing.py`
  - 判定真伪：年报 2023-12-31 报告期、公告日 2024-04-25 → 2024-04-24 的评估不含该字段（R11 Scenario）；缺 `ann_date` 走保守回退并标注。

- [ ] **T2.7 数据对齐编排 `data.py`（时点视图构造）**
  - 设计依据：design.md §4.1 `data.py`、R9/R10/R11
  - 产出文件：`src/service/backtest/data.py` + `test/service/backtest/test_data.py`
  - 验证：`python -m pytest -q test/service/backtest/test_data.py`
  - 判定真伪：`build_point_in_time` 产出 `PointInTimeSnapshot`，任何 `trade_date/visible_from > as_of` 被拒绝（R10）。

- [ ] **T2.8 分组切点与成分 `universe.py`（季度重算，不回改历史）**
  - 设计依据：design.md §4.1 `assign_groups`、R15/R16、KD-6-05/KD-6-07
  - 产出文件：`src/service/backtest/universe.py` + `test/service/backtest/test_universe.py`
  - 验证：`python -m pytest -q test/service/backtest/test_universe.py`
  - 判定真伪：软标签/结果标签作为分组维度被拒；切点基准 `cut_basis` 缺键拒绝；2021Q2 重算不回改 2020 及之前分组（R15 Scenario）。

---

## Phase 3 · 撮合（broker）

- [ ] **T2.9 成本计算（佣金/卖出印花税/滑点/过户费，四分量）**
  - 设计依据：design.md §4.1 `CostBreakdown`、R7、REF-03
  - 产出文件：`src/service/backtest/broker.py`（`CostCalculator` 部分）+ `test/service/backtest/test_broker.py`
  - 验证：`python -m pytest -q test/service/backtest/test_broker.py`
  - 判定真伪：10 万买入、11 万卖出 → 四分量与手算一致（R7 Scenario）；小额触发最低佣金标注；缺印花税率/最低额拒绝。

- [ ] **T2.10 撮合状态机（T+1 / 封板顺延 / 停牌跳过 / 流动性上限）**
  - 设计依据：design.md §4.1 `execute_orders`、R8、KD-3-01/02/03
  - 产出文件：`src/service/backtest/broker.py`（`execute_orders`/`next_tradable_day`）+ `test/service/backtest/test_broker.py`
  - 验证：`python -m pytest -q test/service/backtest/test_broker.py`
  - 判定真伪：一字涨停买不进顺延、跌停卖不出顺延、当日买入当日卖出拒绝（`REJECTED_T1`）、停牌跳过；每笔留痕顺延天数/原因（R8 各 Scenario）；流动性超限截断标注。

---

## Phase 4 · 信号与指标（signal + metrics）

- [ ] **T2.11 纯函数信号 `signal.py`（t 日及之前切片 → 事件/动作）**
  - 设计依据：design.md §4.1 `evaluate_condition`、R10、KD-10-03（MA60 = SMA，不足 60 日用 MA20 替代，复用 `tech-analyzer` 口径）
  - 产出文件：`src/service/backtest/signal.py` + `test/service/backtest/test_signal.py`
  - 验证：`python -m pytest -q test/service/backtest/test_signal.py`
  - 判定真伪：同一 t 切片重复输入 → 同输出（R10 Scenario「纯函数可复现」）；越界读 t+1 → `FutureDataError`。

- [ ] **T2.12 事件研究指标 `compute_event_study`（20/60 日相对基准超额分布）**
  - 设计依据：design.md §4.1 `compute_event_study`、R17、REF-02
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：输出 20/60 日窗口的事件数/均值/中位数/标准差/CI/分年度/分档（R17 Scenario）；有效事件数低于预注册阈值 → 标注「样本不足」不出判定；CI 含 0 且校正后不显著 → 结论「无信号」。

- [ ] **T2.13 统计推断 `block_bootstrap` + 多重比较校正**
  - 设计依据：design.md §4.1 `block_bootstrap`/`multiple_testing_correction`、R5/R6、KQ-2
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：报告名义样本 + 有效样本（时间块数）；默认不用 iid t 检验（R6）；K=1 与 K=50 同一 p 值判定翻转且都入台账（R5 Scenario）；K 缺失 → 拒绝标「有效」。

- [ ] **T2.14 基准归因 + 稳定性分档 + 部分池化**
  - 设计依据：design.md §4.1 `attribution`/`stability`/`partial_pooling`、R13/R14/R16、KQ-3/KQ-7
  - 产出文件：`src/service/backtest/metrics.py` + `test/service/backtest/test_metrics.py`
  - 验证：`python -m pytest -q test/service/backtest/test_metrics.py`
  - 判定真伪：双基准（买入持有 + 市场组合）+ beta/规模/价值/动量四项；全期显著但 80% 贡献来自单一年度 → 标注「仅在 2015 年有效」（R14）；单票绝对收益预测不返回、只返回组内分位（R16）。

---

## Phase 5 · 台账（registry）

- [ ] **T2.15 实验台账 append-only + 哈希校验**
  - 设计依据：design.md §4.1 `ExperimentRegistry.append`、R2、台账存储机制
  - 产出文件：`src/service/backtest/registry.py` + `test/service/backtest/test_registry.py`
  - 验证：`python -m pytest -q test/service/backtest/test_registry.py`
  - 判定真伪：同一预注册执行两次 → 两行、实验 ID 不同；改已写入行的 K/结果 → 拒绝（无 UPDATE/DELETE 接口）+ 留痕；改假设 → 新实验 + `parent_experiment_id`（R2 各 Scenario）。

- [ ] **T2.16 样本外烧毁 + K 累计**
  - 设计依据：design.md §4.1 `assert_not_burnt/mark_burnt/cumulative_K`、R3/R4/R5
  - 产出文件：`src/service/backtest/registry.py` + `test/service/backtest/test_registry.py`
  - 验证：`python -m pytest -q test/service/backtest/test_registry.py`
  - 判定真伪：首次使用样本外写入唯一「已烧毁」标记（不可撤销）；二次请求抛错 + 留痕；新实验独立额度（R4 各 Scenario）；`cumulative_K` 按 `k_components[]` 累计。

---

## Phase 6 · 校准与三级门禁（calibration + gates）

- [ ] **T2.17 已知答案校准门禁 `calibration.py`**
  - 设计依据：design.md §4.1 `run_calibration/assert_calibrated`、R18、KD-10-01/02、KQ-1/KQ-5/KQ-6
  - 产出文件：`src/service/backtest/calibration.py` + `test/service/backtest/test_calibration.py`
  - 验证：`python -m pytest -q test/service/backtest/test_calibration.py`
  - 判定真伪：「跌破 MA60」跑全 A 显著跑输买入持有 → 标记台子可信；复现不出 → `exit != 0` + 封锁研究输出 + 台账记校准失败；校准失败不被表述为「策略无效」（R18 各 Scenario）。

- [ ] **T2.18 三级门禁状态机 `gates.py`**
  - 设计依据：design.md §4.1 `GateStateMachine`、R19、否-3、KD-9-01/06、Q7/KQ-4
  - 产出文件：`src/service/backtest/gates.py` + `test/service/backtest/test_gates.py`
  - 验证：`python -m pytest -q test/service/backtest/test_gates.py`
  - 判定真伪：回测未通过 → 拒进影子；影子期 < 6 个月 → 拒进实盘；跳级请求拒绝并留痕；每规则唯一状态可查询且带每级通过时间与实验 ID（R19 各 Scenario）。

---

## Phase 7 · CLI 装配与端到端

- [ ] **T2.19 CLI 子命令装配**
  - 设计依据：design.md §4.0 `apps/backtest_cli.py`、B 项（pipeline 装配）
  - 产出文件：`src/apps/backtest_cli.py` + `pyproject.toml`（`[project.scripts]` 注册 `backtest`）+ `test/apps/test_backtest_cli.py`
  - 验证：`python -m pytest -q test/apps/test_backtest_cli.py`
  - 判定真伪：`preregister` 写预注册文件并取到 commit；`run` 缺预注册 → `exit != 0` 且无结果行（R1）。

- [ ] **T2.20 端到端 + 全量门禁**
  - 设计依据：proposal `## 成功标准` 5 条 + design.md §6.6/6.7
  - 产出文件：`test/qa/backtest/*`（QA 盲测负向/边界用例，见 design.md §6.7）
  - 验证：
    - `python -m pytest -q test/service/backtest`
    - `python -m pytest -q test/data_provider/backtest`
    - `python -m pytest -q test/qa/backtest`
    - `python -m pytest -q -m "not network and not akshare_legacy"`
    - `python -m ruff check .`
    - `openspec.cmd validate add-backtest-engine --strict`
  - 判定真伪：5 条成功标准逐条由命令输出支撑（校准可复现 / 台账可审计 / 样本外只烧一次 / 成本手算复算 / 无未来函数证伪）。

---

## 完成判定

- [ ] 上述 T2.1–T2.20 全部勾选，且每个勾选前有 `verification.md` 里的命令 + 退出码 + 输出证据。
- [ ] `openspec.cmd validate add-backtest-engine --strict` 通过（退出码 0）。
- [ ] 未触碰 `openspec/specs/`、未改 K1 的 `config/knowledge/_design.md` 层语义、未改 `proposal.md`/`specs/`/`knowledge-delta.md`。

> 本波（T2）只产出 `design.md` + `tasks.md`，**不执行上述 T2.1–T2.20**；它们是 T3 实现波的施工图，由 T4 QA 按 `test/qa/` 用例证伪。
