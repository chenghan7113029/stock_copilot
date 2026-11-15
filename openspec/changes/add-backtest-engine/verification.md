# Verification: add-backtest-engine（T3 实现波证据）

> 角色：engineer（T3）　任务：`t13`　分支：`feature/add-backtest-engine`　基线 HEAD：`0cc6f85`
> 纪律：本文件只记录**真实跑过**的命令 + 退出码 + 输出摘要（禁手写/凭记忆）；数值为测试输入，非生产默认。
> 环境：`python`（无 `python3`）、pytest 9.0.3、ruff 0.15.17、`openspec.cmd`。

## 1. T2.1–T2.20 逐条验证（命令 → 退出码 → 输出）

| 任务 | 验证命令 | 退出码 | 输出摘要 | 判定真伪覆盖点 |
| --- | --- | --- | --- | --- |
| T2.1 | `python -m pytest -q test/service/backtest/test_models.py` | 0 | `10 passed` | `PointInTimeSnapshot` 对 `trade_date/visible_from > as_of` 抛 `FutureDataError`；`Fill.attempts` 表达封板→顺延；`ExperimentRecord(K=None)` 可构造；异常族按类型二分 |
| T2.2 | `python -m pytest -q test/service/backtest/test_config.py` | 0 | `11 passed` | 缺 `commission/stamp_tax/slippage_tiers` → `MissingBacktestConfigError` 且列出缺失键；`results_dir/registry_store_path` 可注入；`segments` 三段互不重叠；`config/app.yaml` 的 `backtest:` 段无未确认数值 |
| T2.3 | `python -m pytest -q test/data_provider/backtest/test_adjust_price.py` | 0 | `6 passed` | `qfq` → `InvalidAdjustModeError`（非数据缺口）；因子换算使分红日持有期收益连续；缺因子 → `BacktestDataGapError` |
| T2.4 | `python -m pytest -q test/data_provider/backtest/test_market_rules.py` | 0 | `7 passed` | 成交额/涨跌停/停牌任一缺失 → `BacktestDataGapError`（不按 0/不按可成交）；字段合并按日期 |
| T2.5 | `python -m pytest -q test/data_provider/backtest/test_universe.py` | 0 | `5 passed` | 名单不可得 → 缺口；成分去重排序；退市日/时点 ST 保留 |
| T2.6 | `python -m pytest -q test/data_provider/backtest/test_financial_timing.py` | 0 | `9 passed` | `ann_date` 优先；缺公告日按 4/8/10 月底回退并标注；未知报告期 → 缺口 |
| T2.7 | `python -m pytest -q test/service/backtest/test_data.py` | 0 | `7 passed` | `build_point_in_time` 对越界 bar 抛 `FutureDataError`；`visible_from <= as_of` 过滤；前复权拒绝 |
| T2.8 | `python -m pytest -q test/service/backtest/test_universe.py` | 0 | `9 passed` | 软标签/结果标签拒绝；`cut_basis` 缺键拒绝；季度重算不回改历史；退市日后剔除 |
| T2.9 + T2.10 | `python -m pytest -q test/service/backtest/test_broker.py` | 0 | `11 passed` | 10 万买/11 万卖四分量手算一致（125.0 / 192.5）；最低佣金标注；一字涨停/跌停顺延 `delay_days`；停牌跳过；T+1 拒绝；流动性截断；最大顺延上限 |
| T2.11 | `python -m pytest -q test/service/backtest/test_signal.py` | 0 | `7 passed` | 同输入同输出；MA60 跌破出事件；越界抛 `FutureDataError`；缺参数拒绝；源码无 IO 依赖 + 签名仅 `(snapshot, condition)` |
| T2.12 + T2.13 + T2.14 | `python -m pytest -q test/service/backtest/test_metrics.py` | 0 | `12 passed` | 20/60 日 × 双基准 `WindowStats`（含 `by_year/by_cap_tier/effective_n`）；样本不足标注；K=1/50 判定翻转；K 缺失拒绝；归因四项 + `unexplained`；`shrink` 缺省拒绝；`scope_note`「仅在 2015 年有效」 |
| T2.15 + T2.16 | `python -m pytest -q test/service/backtest/test_registry.py` | 0 | `15 passed` | 两次执行两行且 ID 顺序；篡改行 → `RegistryCorruptedError`；改假设须新实验 + 父 ID；执行行（REJECTED/FAILED）留痕；预注册缺键报字段名；样本外烧毁唯一且二次拒绝留痕；`cumulative_K`；`write_result` + `export_ledger` 13 字段 |
| T2.17 | `python -m pytest -q test/service/backtest/test_calibration.py` | 0 | `4 passed` | 校准通过 `passed=True`/`verdict=INVALID`/`corrected_p<alpha`；失败 `passed=False`；`assert_calibrated` 库层抛 `CalibrationFailedError`（携带 `reason/corrected_p/verdict`）；`calibration.json` 成败都写；禁词扫描通过 |
| T2.18 | `python -m pytest -q test/service/backtest/test_gates.py` | 0 | `6 passed` | 新规则 `BACKTEST_PENDING`；跳级 `GateSkipError` + 拒绝留痕；影子期未满拒进实盘；方向一致判据；判据缺键拒绝；`REJECTED` 终态 |
| T2.19 | `python -m pytest -q test/apps/test_cli_backtest.py` | 0 | `7 passed` | `ledger --experiment no-such-id` → 1（非 2）；`preregister` 写文件；`run` 缺预注册 → 1 且只落执行行 REJECTED、无结果行；`ledger --format json` 13 字段；`calibrate` 成功 0 / 门禁失败 2；`gate` 查询 |
| T2.20 | 见 §2 全量门禁 | 0 | 见下 | 5 条成功标准的机检面由上述单测 + 全量门禁支撑 |

## 2. 全量门禁（T2.20）

```text
$ python -m pytest -q test/service/backtest test/data_provider/backtest test/apps/test_cli_backtest.py
126 passed, 1 warning in 1.08s                                     # exit=0

$ python -m pytest -q -m "not network and not akshare_legacy" --ignore=test/qa
955 passed, 35 deselected, 1 warning in 6.34s                      # exit=0

$ python -m compileall -q src test
# 无输出                                                        # exit=0

$ python -m ruff check src/service/backtest src/data_provider/backtest src/apps/cli.py test/service/backtest test/data_provider/backtest test/apps/test_cli_backtest.py
All checks passed!                                                # exit=0（既有 39 个基线错误不修）

$ openspec.cmd validate add-backtest-engine --strict
Change 'add-backtest-engine' is valid                             # exit=0

$ grep -rn "openai" src/service/backtest src/data_provider/backtest
# 无输出（未命中）                                                # exit=1 = 无 LLM 调用

$ grep -rn "import ref\.\|from ref\." src
# 无输出（未命中）                                                # exit=1 = 未 import ref/
```

**`config/app.yaml` 的 `backtest:` 段无未确认数值**（`test_config.py::test_app_yaml_backtest_section_has_no_unconfirmed_numbers`，exit=0）：
`commission={rate:null,min:null}`、`stamp_tax={sell_rate:null}`、`transfer_fee={included:null,rate:null}`、`slippage_tiers=[]`、`liquidity_cap=[]`、`alpha/block_length/n_bootstrap/max_delay_days/... = null`。

**台账 append-only 有测试**：`test_registry.py::test_tampered_row_rejected`（篡改 K → `RegistryCorruptedError`）、`test_run_record_rejected_and_failed_are_persisted`（失败也落 `RunRecord(FAILED)`）、`test_out_of_sample_burn_once_and_rejection_traced`（二次样本外 → 拒绝留痕）。

## 3. 与 QA 盲测套件的差异（`test/qa/backtest/`，QA 于 commit `0cc6f85` 提交，T5 所有）

```text
$ python -m pytest -q -m "not network and not akshare_legacy"
31 failed, 977 passed, 35 deselected, 3 errors                       # exit=1
```

全部红点集中在 QA 在 commit `0cc6f85` 提交的 `test/qa/backtest/`（T4-exec 盲测，本波 engineer 不得修改 `test/qa/`）。根因是**夹具与冻结版 design 不一致**，非实现偏离契约：

1. 共享 `cfg` 夹具形状：`liquidity_cap={max_pct_of_avg_amount}`（design/knowledge-delta = 档位列表 `{amount_lower, amount_upper, max_participation}`）、`slippage_tiers={max_amount, rate}`（design = `{amount_lower, amount_upper, bps}`）、缺 `max_delay_days`（design §3H 明写「必须存在」）/`min_events`/`k_components`/`gates.*`。
2. `compute_event_study` 收到 `Sequence[EventSignal]`：design §4.1 的 `EventSignal` 只有 `condition_id/event_date`，**不含收益**，无法计算超额；实现另增 `EventObservation` 承载「事件×窗口×基准的超额」（见 §4 契约补充）。
3. `attribution` 夹具只给 size/value/momentum 三因子；design 要求四项（beta/规模/价值/动量）。
4. `run_calibration` 夹具仅 2 根 bar 且 `cfg` 无 `calibration.*`：R18 校准题需要 MA60 序列 + Q4 成本参数。
5. `GateStateMachine(registry)` 未传门禁判据：与 design §9.1 Q7「判据数值缺即不允许 transition」冲突。

**结论**：`--ignore=test/qa` 口径 955 passed / exit 0；QA 套件需 T5/T2 按冻结 design 修夹具（不是放宽断言），本波未越界改 `test/qa/`。

## 4. 契约补充（不改 design/spec，属实现层「把欠定义处写实」）

| # | 补充 | 依据 / 理由 |
| --- | --- | --- |
| C1 | `ConditionSpec{condition_id, kind, params}` | design §4.1 `evaluate_condition(snapshot, condition: ConditionSpec)` 引用了该类型但未定义字段；本波补为最小契约 |
| C2 | `EventObservation{code, event_date, window, benchmark_kind, excess, cap_tier}` | design `EventSignal` 无收益字段，`compute_event_study` 无法从事件本身算超额；用独立观测行承载，签名不变 |
| C3 | `RunRecord` 增 `hypothesis_id`、`data_version` | `data_version` 按 captain R1-04 裁定补齐；`hypothesis_id` 是 captain R1-03 裁定 join 键（`hypothesis_id + experiment_id`）所必需 |
| C4 | `mark_burnt` = append 一条 `burnt=True` 标记行（同实验 ID，带 `timestamps["burnt_at"]`），`get` 取最新行 | R4「在台账写入已烧毁标记」+ R2 append-only：不重写旧行、标记唯一不可撤销 |
| C5 | `GateStateMachine(store_or_registry, *, cfg, clock)`；拒绝迁移额外落 `RunRecord(REJECTED)`；`evidence_experiment_ids` 用级名 `backtest/shadow/live` | design §4.0「门禁状态读写委托 registry」+ R19「拒绝记录写入台账」「每级依据的实验 ID」 |
| C6 | `R11` 的 `visible_from`：有 `ann_date` 取 `ann_date`，缺失才回退法定截止日 | design §4.1 写 `max(ann_date, cutoff)` 与 spec R11 Scenario1（04-25 可见 / 04-24 不可见）矛盾；按任务书「spec 为最终判据」执行 spec，未改 design |
| C7 | loader 注入形态：`带方法对象` 或 `callable`；行可为 `dict` 或 `PriceBar/FinancialRecord`；`adjust` 以 `AdjustMode` 枚举传达到取数层 | design 只写 `*, loader` 未定形态；两种形态都保持「口径必达、缺口显式报错」 |
| C8 | `BacktestConfig.segments` 属性（三段边界、互不重叠校验） | design §4.2 R3 明写 `config.py::BacktestConfig.segments`；Q3 未答复 → 三段显式配置，缺键即拒绝 |

## 5. 自检

```text
$ git rev-parse HEAD
0cc6f85...（提交前基线；提交后以 git log -1 为准）
$ git branch --show-current
feature/add-backtest-engine
```

- 未修改 `openspec/specs/`、`openspec/changes/add-backtest-engine/{design.md,specs/,test-design.md}`、`test/qa/`、`ref/`、`src/service/value/`、`src/dao/`。
- 未新增依赖（仅用既有 pyyaml / 标准库）。
- 未预埋未确认数值：费率/税率/滑点/块长/收缩强度/门限/切点全部来自配置，缺键即 `MissingBacktestConfigError`。
