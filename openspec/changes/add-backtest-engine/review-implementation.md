# Review (Implementation): add-backtest-engine（T6 白盒代码评审）

> 评审者：reviewer（T6）　方法：`ponytail-review`（correct / safe / load / tested / fast / lean）+ Agent 特有 7 项
> 评审对象：`git diff ba609a0..HEAD -- src test config`（本波全部实现；HEAD=`17de5fc`，代码树等同 T5 基线 `be35936`）
> 契约基准：`design.md`（939 行）、`specs/backtest-engine/spec.md`、`test-design.md`
> 边界：只读代码/测试/配置；本评审只新增本文件，不改任何被评审产物。

## 0. 结论先行

| 项 | 结论 |
| --- | --- |
| **verdict** | **pass** |
| findings | **3 条**（1 medium + 2 low），无 blocker / high → 不触发 needs_revision |
| 确定性边界 | `src/service/backtest`、`src/data_provider/backtest` 内 **0** 处 LLM/openai 调用；`src/` 全仓 **0** 处 `import ref.` |
| 特别核查 5 项 | 台账 append-only=真机制 / 缺键即拒绝=真抛 / 防未来函数=真结构 / 成本四分量=真算无近似 / 测试有效性=会红 |

**给 captain/integrator 的一句话**：本波实现忠实兑现了 design 契约与 T5 已验证的行为；3 个 medium/low finding 都是「契约收口级」边界（空信号表达、复权口径硬编码、门禁状态持久化），不阻断归档，可进 T7。

---

## 1. What this change does

本波落地回测台子（design §4.0/§6）：`src/service/backtest/`（11 文件：models/config/data/universe/signal/broker/metrics/registry/calibration/gates）+ `src/data_provider/backtest/`（4 适配器 + loader）+ `src/apps/cli.py` 扩展 `backtest` 子命令组 + `src/common/exceptions.py` 8 类回测异常 + `config/app.example.yaml` `backtest:` 段。全链路确定性计算、零 LLM，测试 1059 条（含 QA 56 条）全绿。

---

## 2. CR 清单逐项结论（无留白）

### 2.1 通用 6 条（`ponytail-review`）

| # | 维度 | 结论（发现 / 未发现 + 依据） |
| --- | --- | --- |
| A1 | correct | 未发现逻辑 bug。关键路径均有确定性断言兜底：`PointInTimeSnapshot.__post_init__` 双字段越界抛 `FutureDataError`（models.py:158-169）、`execute_orders` 缺 `max_delay_days`/成本键抛 `MissingBacktestConfigError`（broker.py:202-209）。边界空观测有契约缺口 → **R2-01（medium）** |
| A2 | safe | 未发现。台账逐行 `record_sha256`（registry.py:75-83），读取校验不匹配即 `RegistryCorruptedError`（:93-97）；无 UPDATE/DELETE 接口；无弱随机/密钥/写序错误面 |
| A3 | load | 未发现。单进程批处理 pipeline；台账 append-only 不读全量到内存之外的操作（`_read_rows` 逐行读）；`next_tradable_day` 有 3650 上限 + `execute_orders` 有 `max_delay` 封死循环 |
| A4 | tested | 未发现。157 条 engineer + 56 条 QA 测试真实可红（见 §3.5 抽查）；无 `assert True`/空断言/自证 |
| A5 | fast | 未发现。纯函数 + `random.Random(seed)` 固定种子；无热循环重复/无 N+1/无只增不减结构（台账 append 是业务语义，非内存泄漏） |
| A6 | lean | 未发现过度设计。复用 `common.trading_day`/`common.exceptions`/既有 `apps.cli` 入口；未重复造轮子。轻微一致性点见 **R2-02/R2-03（low）** |

### 2.2 Agent 特有 7 项

| # | 维度 | 结论（发现 / 未发现 + 依据） |
| --- | --- | --- |
| B1 | LLM 与确定性边界 | 未发现。grep `openai\|llm\|narrate` 在 `src/service/backtest` + `src/data_provider/backtest` = 0 命中（仅 docstring「零 LLM」一句）；数值与判定全部由确定性函数产出（signal/broker/metrics/calibration） |
| B2 | 可信保证落地（trace、双行台账、hash） | 未发现（真机制非声明）。`RunRecord`（执行行）+ `ExperimentRecord`（结果行）双行同文件 append；`_encode_line` 逐行写 hash、`_decode_line` 读时校验；拒绝/失败落执行行（`_bt_run` 预注册缺失/未提交/BacktestError 三处均 `append_run(REJECTED/FAILED)`）。见 §3.1 |
| B3 | 上下文 | N/A（零 LLM）。无上下文/数据灌入面 |
| B4 | 成本 | N/A（零 LLM）。无 LLM 调用/token 面 |
| B5 | 确定性 | 未发现。signal 纯函数（同输入同输出，test_signal.py 断言）；`random.Random(0)` 固定种子仅为可复现；无 LLM 生成阈值/排序/口径 |
| B6 | 注入面 | 未发现。零 LLM；注入点显式：`ExperimentRegistry(store_path, *, clock, data_version, results_dir)`、`load_price_series(..., loader)`、`build_universe(..., provider)`、`cli_runner(cwd=tmp_path)`；CLI 配置解析 `--config`（相对 cwd）> `cwd/config/app.yaml` > 缺键拒绝 |
| B7 | 可重入与可拒绝 | 未发现。可重入 = 预注册 commit + 参数快照 + data_version；可拒绝 = 预注册缺失/未提交（R1）、配置缺键（R7）、数据缺口（R9/R12）三处硬拒绝，均 `exit != 0` 且留执行行 |

---

## 3. 特别核查 5 项（最易假实现处）

### 3.1 台账 append-only：真机制

- **双行**：`RunRecord`（执行行，含 `row_type="run"`）+ `ExperimentRecord`（结果行，`row_type="result"`），同文件 `registry.ndjson` append（registry.py:172-211）。
- **逐行 hash**：`_record_hash` = `sha256(json.dumps(payload, sort_keys=True))`（:75-77）；`_decode_line` 读取时校验，不匹配抛 `RegistryCorruptedError`（:93-97）。
- **篡改可检**：`test_tampered_row_rejected`（test_registry.py:56-65）改 `K` 后 `registry.rows()` 抛 `RegistryCorruptedError` 且信息含「损坏/哈希」——真会红。
- **失败也落执行行**：`test_run_record_rejected_and_failed_are_persisted`（:87-108）断言 REJECTED/FAILED 两条执行行落盘且 `result_rows()==()`。
- **无 UPDATE/DELETE 接口**：`ExperimentRegistry` 只有 `append_run/append/get/result_rows/...`，无任何改/删方法。
- **结论**：真机制，非「只有字段」。

### 3.2 缺键即拒绝：真抛，无偷默认

- `BacktestConfig.from_config` 先查 `MUST_KEYS`（segments/windows/max_delay_days/min_events）缺失即 `MissingBacktestConfigError`（models.py:491-493）。
- 消费处对 None 逐一拒绝：`CostCalculator.from_config`→`_cost_rules` 对 commission/stamp_tax/transfer_fee/slippage 缺即抛（broker.py:127-139）；`block_bootstrap`/`_inference_cfg` 对 block_length/n_bootstrap 缺即抛（metrics.py:186-193）；`partial_pooling` 对 shrink 缺即抛（metrics.py:416-419）；`assign_groups` 对 Q6 四键缺即抛（universe.py:100-107）。
- `config/app.example.yaml` `backtest:` 段数值全 `null`/`[]`（commission.rate/min、stamp_tax.rate、block_length、n_bootstrap、shrink、gate_criteria 等），**无一处预埋业务默认值**。
- **结论**：真抛，无偷默认（`DEFAULT_RESULTS_DIR`/`DEFAULT_REGISTRY_STORE` 是 design 明文的路径默认，非口径数值）。

### 3.3 防未来函数：真结构

- `PointInTimeSnapshot.__post_init__` 覆盖 `price[].trade_date > as_of` 与 `financials[].visible_from > as_of` 两处，抛 `FutureDataError`（models.py:158-169）。
- `signal.evaluate_condition(snapshot, condition)` 签名只有 `{snapshot, condition}`，**不接收任何日期参数**；`signal.py` 源码不含 `data_provider`/`dao`/`datetime.now`/`open(`（test_signal.py:90-96 结构断言，QA test_no_future_function.py:59-61 同款）。
- `data.build_point_in_time` 请求 `end=as_of`，且「不裁剪而是让快照抛错」——不静默截断（data.py:147 注释 + :148-152）。
- **结论**：真结构，非靠自觉（design 否-4 兑现）。

### 3.4 成本四分量：真算，无比例成本近似残留

- `CostCalculator.cost`（broker.py:76-97）独立算四分量：`commission=max(amount*rate, min)`、`stamp_tax=amount*rate if SELL else 0`、`slippage=amount*tier.bps/10000`、`transfer_fee=amount*rate if included else 0`，`total`=四者之和。
- 校准不再用比例近似：`run_calibration` 的 `cost_rate = fill.cost.total / fill.filled_amount`（calibration.py:129）——`fill.cost.total` 来自 broker 四分量，非固定 bps（T2-fix-5 落实）。
- `test_cost_hand_calc.py` 用独立算式手算四分量（不调用被测函数）断言 `approx(1e-9)`（:37-53），且断言「买入印花税==0」（:49）——成本实现坏会红。
- **结论**：真四分量，无「比例成本近似」残留。

### 3.5 测试有效性抽查（≥5 QA + ≥5 engineer，判断「改坏实现会不会红」）

| 侧 | 抽查测试 | 改坏实现会不会红 |
| --- | --- | --- |
| engineer | `test_registry.py::test_tampered_row_rejected` | 会——改 hash 校验逻辑或改成可 UPDATE 即红 |
| engineer | `test_registry.py::test_changed_params_requires_new_experiment_with_parent` | 会——去掉 parent/params 校验即红 |
| engineer | `test_signal.py::test_signal_module_has_no_io_dependency` | 会——signal 引入 IO import 或日期参数即红 |
| engineer | `test_signal.py::test_future_bar_rejected_by_snapshot` | 会——`__post_init__` 漏 `trade_date` 校验即红 |
| engineer | `test_registry.py::test_export_ledger_13_fields_and_statement_from_prereg` | 会——删 `statement` 来源或 13 字段不齐即红 |
| QA | `test_no_future_function.py::test_tc_r10_02_future_data_raises` | 会——快照越界不抛或静默截断即红 |
| QA | `test_cost_hand_calc.py::test_tc_r07_01_cost_components_match_hand_calc` | 会——成本四分量任一算错/漏印花税方向即红 |
| QA | `test_out_of_sample_burn.py::test_tc_r04_02_second_out_of_sample_request_rejected` | 会——烧毁二次不拒或标记重复即红 |
| QA | `test_no_future_function.py::test_tc_r10_03_signal_is_pure_and_io_free` | 会——signal 加日期参数/IO 依赖即红 |
| QA | `test_survivorship_bias.py`（R12 provider 缺口/历史成分时点） | 会——provider 缺口被吞成空名单/用当前名单即红 |

- 机检：`grep assert True|assert None is None|^pass` 在 backtest 测试 = **0 命中**（无自证/空断言）。
- 计数：engineer backtest 157 个 `def test_`，QA 56 个 `def test_`。

---

## 4. 越权 / 范围检查

| 检查 | 命令 | 结论 |
| --- | --- | --- |
| D1 `openspec/specs/` 未被手改 | `git diff --name-only ba609a0..HEAD -- openspec/specs/` | 空 → 通过（本波 diff 含 `openspec/changes/...` 与 `config/knowledge/` 但无 `openspec/specs/`） |
| D2 `test/` 与 `test/qa/` 分离 | 逐 commit `git show --name-only`（t13–t24 系列） | engineer 写 `test/service/backtest/`、`test/data_provider/backtest/`、`test/apps/`；QA 写 `test/qa/backtest/`；互不越界 |
| D3 评审只读 | 本评审未写任何 `src/`/`test/`/`config/`/`design.md`/`specs/` | 通过（只新增本文件） |
| 无 `import ref.` | `grep -rniE "import ref\.|from ref|sys\.path" src/` | 0 命中 → 通过 |
| 无未登记依赖 | diff 无 `pyproject.toml`/`requirements.txt` 变更；新依赖 0 | 通过 |
| `backtest:` 段无未确认数值 | `config/app.example.yaml:148-195` 待 Q 键全 `null`/`[]` | 通过 |

---

## 5. verdict 的两项开放条件

1. **tasks.md 是否全完成**：是。T2.1–T2.20 已由 T3 实现、T5 终审勾选（verification.md §11 附录 A 逐条 23/0）；本评审复核实现与 tasks 判定一致。
2. **声称行为是否在生产路径可达**：`build_parser`/`main` 已接 `backtest` 子命令（cli.py:2250-2280 / 2415-2420），`run_backtest_command` 分发 5 个子命令且退出码 0/1/2 语义落地（:2017-2038）。**数据路径有意 fail-closed**：`BacktestDataLoader` 默认四适配器 `fetch=None` → 任何取数 `BacktestDataGapError`（data_provider/backtest/__init__.py:33-45 + adjust_price.py:64-68），这是 proposal「数据前置缺口显式报错」的落地，非断链。

---

## 6. Findings（3 条，均 medium/low → verdict pass）

### R2-01（medium）`load_event_observations` 对零事件信号抛 `BacktestDataGapError`，使 F7「空观测→INCONCLUSIVE」经 CLI `run` 不可达

- **problem**：`data.py:170-171` `load_event_observations` 在 `not signals` 时 `raise BacktestDataGapError("事件研究无事件信号：不得产出结论")`；而 `_bt_run`（cli.py:1886-1895）先 `evaluate_condition` 收集 signals，再直接调 `load_event_observations(signals, ...)`。触发输入：一条规则在整个样本上从未触发（合法「无信号」，R17 Scenario3「允许结论为无信号」）→ `backtest run` 退出码 1 + 「数据缺口」文案，而不是 `compute_event_study(())` 的 `verdict=INCONCLUSIVE, windows={}, n_events=0`（F7/T2-fix-6 已裁定的契约，metrics.py:250-259 已实现却不可达）。**错误结果**：「规则零触发」与「数据通道未接通」被混为一类，违反 R17 的「无信号」与 F7 的「空观测不抛异常」。
- **requiredFix**：`data.py::load_event_observations` 改为 `if not signals: return ()`（把「零信号」交给 `compute_event_study(())` 得 INCONCLUSIVE）；「数据通道未接通」（loader 缺 `load_forward_returns`）继续抛 `BacktestDataGapError`。或在 `_bt_run` 对 `not signals` 直接构造空 observations 跳过 loader。验证：`backtest run` 零事件 → exit 0 + `verdict=inconclusive`，而非 exit 1。
- **file:line**：`src/service/backtest/data.py:170-171`；`src/apps/cli.py:1895`

### R2-02（low）`AdjustMode.SEGMENTED_HFQ` 在信号/校准路径不可达（硬编码 HFQ）

- **problem**：`build_point_in_time`（data.py:139）、`_run_backtest_experiment`（cli.py:1885）、`run_calibration`（calibration.py:94-96）三处硬编码 `AdjustMode.HFQ`，尽管 `load_price_series` 公共入口与 `parse_adjust_mode` 均支持 `hfq/segmented_hfq`（R9「后复权**或**分段复权」）。触发输入：未来数据源只提供分段复权（`segmented_hfq`）时，这三条路径无法使用它。**影响**：design §4.1 的 `AdjustMode` 双值契约在信号/校准路径只兑现了一半。
- **requiredFix**：把复权口径提升为 `BacktestConfig` 或预注册参数（缺省 HFQ 可接受，但须可配置），三处改为读配置而非硬编码；或显式在 design §9 注明「MVP 信号/校准固定 HFQ，分段复权仅在 `load_price_series` 直调可用」。
- **file:line**：`src/service/backtest/data.py:139`；`src/apps/cli.py:1885`；`src/service/backtest/calibration.py:94-96`

### R2-03（low）`GateStateMachine` 直接写独立的、无逐行 hash 的 `gates.ndjson`，未按 design §4.1「读写委托 registry」

- **problem**：design §4.1 写明 gates 是「薄状态机，读写委托 registry」，但实现 `GateStateMachine._append`（gates.py:233-245）直接写 `registry.store_path.parent / "gates.ndjson"`，该文件**无 `record_sha256`、无逐行校验**（对比实验台账 registry.py:75-97）；只有「拒绝动作」经 `registry.append_run(RunRecord REJECTED)` 进 hash 台账（gates.py:150-158），**已接受的迁移行**（`accepted=True`）无防篡改。触发输入：有人编辑 `gates.ndjson` 把某规则改成 `backtest_passed`（无依据实验）→ `current()` 直接返回篡改后状态，无法像实验台账那样被检出。**影响**：R19「跳级请求 MUST 被拒绝并留痕」的离线防篡改只覆盖了拒绝侧、未覆盖接受侧。
- **requiredFix**：二选一——① `gates` 迁移行也落 `ExperimentRegistry`（带 hash 的执行行语义，如 `RunRecord` 扩展 `gate_*` 字段或独立 `GateRecord` 走 registry 的 hash append）；② 给 `gates.ndjson` 补与 registry 同款的逐行 hash 校验。至少把 design §4.1「读写委托 registry」与实现的差异在 design 里显式登记。
- **file:line**：`src/service/backtest/gates.py:233-245`；`src/service/backtest/gates.py:63`

---

## 7. 分流核对

| finding | type | severity | verdict 影响 | 去向 |
| --- | --- | --- | --- | --- |
| R2-01 | bug（空信号语义） | medium | pass | T7 改进点（建议 T7 前由 architect/engineer 收口） |
| R2-02 | bug（复权口径硬编码） | low | pass | T7 改进点 |
| R2-03 | bug（门禁状态无 hash） | low | pass | T7 改进点 |

无 `blocker`/`high` → verdict = **pass**，findings 保留、不消失。

---

## 12. 重审（T6-r2，按当前 bytes `39dde34`）

> 触发：t34/t37/t39 改了 `src/`、`test/`、`config/` 字节，t28 verdict 判废。本重审对当前 HEAD 全量复判，不只看增量。
> 起点 HEAD = 结束 HEAD = `39dde342759e5dd0a0141a771e044752115d5937`（前后一致，无位移）。
> 与 t28（`f5085c0`）的字节差异：`src/service/backtest/{broker,calibration,data,metrics,models,registry}.py`、`src/apps/cli.py`、`config/app.example.yaml`（Owner 口径落值）、`config/knowledge/canon/*`（K2 落库）、`test/*` 新增口径用例；`git diff --stat f5085c0..HEAD -- src test config` = 31 files，+1603/−147。

### 12.1 verdict

**pass**（无 blocker/high）。新口径全部正确落地；t28 的 R2-01 已修，R2-02/R2-03 仍开但均 low，不阻断归档。

### 12.2 CR 清单 6+7 项（重审结论）

**通用 6 条（ponytail-review）**

| 维度 | 结论 |
| --- | --- |
| correct | 未发现新逻辑 bug。R2-01（零触发语义）已修（data.py:170-173）；成本/撮合/分组/K 计数口径与 §9.3 对齐 |
| safe | 未发现。台账 append-only+逐行 hash 不变；Q5 封板判定改为配置驱动、无硬编码阈值，缺键即 `MissingBacktestConfigError` |
| load | 未发现。单进程 pipeline；无新增竞态/内存增长面 |
| tested | 未发现。全量 1091 passed（QA 62）；新口径有区分力用例（§12.5） |
| fast | 未发现。无新增热循环/大减速 |
| lean | 未发现过度设计。未实现键（shrink/significance/calibration/stability）如实注释 + TODO→IMPROVEMENTS，未假实现 |

**Agent 特有 7 项**

| 维度 | 结论 |
| --- | --- |
| LLM 与确定性边界 | 未发现。backtest 全链路仍零 LLM/openai |
| 可信保证（trace/双行台账/hash） | 未发现。台账机制不变；R2-03（gates.ndjson 无 hash）仍开，见 §12.3 |
| 上下文 | N/A（零 LLM） |
| 成本 | N/A（零 LLM） |
| 确定性 | 未发现。纯函数 + 固定种子不变 |
| 注入面 | 未发现。Q5 三键（limit_pct/seal_definition/suspend_source）从配置读、无默认值 |
| 可重入与可拒绝 | 未发现。burn_scope=hypothesis 按 hypothesis_id 键；custom_window 缺 flag 拒绝；缺键拒绝不变 |

### 12.3 t28 findings 现状复核

| finding | 状态 | 证据 |
| --- | --- | --- |
| R2-01（medium，空信号抛数据缺口） | **已修** | `data.py:170-173`：`if not signals: return ()`，空序列交 `compute_event_study(())` 得 `INCONCLUSIVE`（F7）；QA `test_event_study.py` 增零触发用例锁定（t30） |
| R2-02（low，HFQ 硬编码） | **仍开** | grep `AdjustMode.HFQ` 命中 5 处：`data.py:139`、`cli.py:1886/1909/1934`、`calibration.py:102` |
| R2-03（low，gates.ndjson 无 hash） | **仍开** | `gates.py` 无 `sha256/record_sha256/_record_hash`；`gates.ndjson` 仍直接 append、无逐行 hash |

### 12.4 新口径核查（5 项，均有证据）

1. **`tier_count=5` → 25 组、切点全 A 时点截面**：`config/app.example.yaml:180` `tier_count: 5`、`:179` `cut_basis: all_a_cross_section`；`test_universe.py::test_five_tiers_two_dimensions_makes_25_groups`（25 标的 × 2 维度 × 5 档 → `len(combinations)==25`，档 ∈[0,4]）实测 pass。
2. **`transfer_fee.included=true` 不双算**：`broker.py:85-100` 过户费只加进 `commission` 行、`transfer_fee=0.0`、`total=commission+stamp_tax+slippage`（无第二笔过户费）；`test_broker.py::test_transfer_fee_merged_into_commission_not_double_counted` 断 `transfer_fee==0`、`commission==separate.commission+fee`、`total==separate.total+fee` 实测 pass。
3. **commission 双边、费率 1.254e-4**：`broker.py::cost` 对 BUY/SELL 均计佣金（无方向判断，双边）；`config/app.example.yaml:160` `rate: 0.0001254`（注释「0.01254%，非 0.05%，买卖双边」）；`test_owner_values.py`（TC-CFG-01）断 `rate==1.254e-4` 且 `!=0.01254`、`!=5e-4` 实测 pass。
4. **exception_approver 保留**：`config/app.example.yaml:196` `exception_approver: Owner`；知识 `CAN-SAMPLE-001` notes「留口子、机制保留、不得因自动化关闭」。
5. **burn_scope/k_components/custom_windows 可测**：`burn_scope: hypothesis`（registry 烧毁标记按 `hypothesis_id` 键）；`registry.cumulative_K({"k_components": {组件: 规模}})` 走 `k_from_grid` 乘积、只给分量名抛 `MissingBacktestConfigError`；`metrics.custom_window_k_cost` 每额外窗口 ×`k_cost_per_window`、`custom_allowed` 非 true 拒绝。对应 TC-CFG-03/04/05 实测 pass。

### 12.5 测试有效性抽查（≥3 条，改坏会红；未提交任何改动）

| 测试 | 改坏实现会红 |
| --- | --- |
| `test_five_tiers_two_dimensions_makes_25_groups` | 会——tier_count 解析错/分位算法错 → 组合数 ≠25 红 |
| `test_transfer_fee_merged_into_commission_not_double_counted` | 会——过户费单列一次或双算 → `transfer_fee==0`/`total` 断言红 |
| `test_owner_values.py::TC-CFG-01` | 会——佣金率写成 `5e-4`（旧 0.05%）或 `0.01254`（量纲误）→ `rate==1.254e-4` 红 |
| `test_st_uses_5_percent_limit` | 会——ST 阈值用错（10% 而非 5%）→ 封板判定红 |

### 12.6 证据（命令 + 退出码）

```bash
$ git rev-parse HEAD   # 起点与结束一致
39dde342759e5dd0a0141a771e044752115d5937

$ python -m pytest -q test/service/backtest/test_universe.py::test_five_tiers_two_dimensions_makes_25_groups \
    test/service/backtest/test_broker.py::test_transfer_fee_merged_into_commission_not_double_counted \
    test/service/backtest/test_broker.py::test_st_uses_5_percent_limit \
    test/service/backtest/test_broker.py::test_opened_seal_is_tradable_with_doubled_slippage \
    test/qa/backtest/test_owner_values.py
9 passed in 0.08s        # exit=0

$ python -m pytest -q -m "not network and not akshare_legacy"
1091 passed, 35 deselected, 5 warnings in 9.34s   # exit=0

$ openspec.cmd validate add-backtest-engine --strict
Change 'add-backtest-engine' is valid           # exit=0
```

### 12.7 findings 汇总（更新后）

| finding | severity | 状态 | 去向 |
| --- | --- | --- | --- |
| R2-01 | medium | 已修（t29） | 关闭 |
| R2-02 | low | 仍开 | T7 改进点 |
| R2-03 | low | 仍开 | T7 改进点 |

无新增 finding；verdict = **pass**。
