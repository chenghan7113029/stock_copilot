# 验证报告：add-allocation-executor

- 变更：`openspec/changes/add-allocation-executor/`
- 波次：`add-allocation-executor`（一期 P0 第二项：配置执行器）
- 验证人：qa
- 验证时间：2026-11-15 21:57
- 代码基线：`83449c06006a53aa924accd024aa0d295f6f80d5`（`git rev-parse HEAD`，分支 `feature/add-allocation-executor`；本报告写完前已核对工作树无未提交改动）
- 环境：Windows 11 / Python 3.14.3 / pytest 9.0.3 / PyYAML 6.0.3 / ruff 0.15.17；`pytest` 默认 deselect 32 个 `akshare_legacy`；本机无 `python3`、`openspec` 只走 `openspec.cmd`

> **证据纪律**：本报告每条证据 = 命令 + 退出码 + 关键输出（或 `文件:行` / 测试节点 id），全部复制自本次实际执行。
> **章节数说明**：任务 acceptance 写「按模板 8 章」，但 `docs/agent-team/templates/verification-report.md:14` 自述「共 **9** 章节，编号固定，缺一节即视为不合格」。
> 本报告按模板 **9 章** 交付（含 §9 Case 复现核对）；若必须收敛为 8 章，请以模板为准合并/删除章节，而不是漏节。

## 1. 结论

**结论**：有条件通过

**依据**：
- 三套测试全绿：全量 `python -m pytest -q` → `1177 passed, 32 deselected`（exit 0）；`test/qa` → `99 passed`（exit 0）；本 change 路径 ruff → `All checks passed!`（exit 0）；`openspec.cmd validate --strict` → valid（exit 0）。
- proposal 5 条成功标准全部达成、8 条失败标准/反目标全部未触发（§2.2/§2.3 逐条），28/28 Scenario 有覆盖测试（§5），负向/边界真执行（§4）。
- **附带条件（不阻塞归档判定，但 T6 必须裁决/跟踪）**：
  1. **F1（medium）**：spec R3-S1 字面要求「回显 `0.35 × 1,000,000 − 250,000 = 100,000`」，实现 echo 只有四项输入（0.35/1,000,000/250,000/24），公式字符串缺失（结果与月数在 `reasons` 里）。「可手算到元」的 SHALL 满足，scenario 字面不满足 → 需 T6 裁决「改实现补一行公式」或「改 scenario 措辞」。
  2. **F3（low）**：`docs/cases/case-20261115-allocation-executor/traces.yaml` 目前只有 K3 的 1 条 `layer: knowledge` 行；本报告 §9 的 function/number trace 因 T5 任务契约 inScope 仅 `verification.md` 未 append，需 captain 开补录任务。
- **无 blocker、无测试失败、无隐瞒失败项**；ruff 的 38 个 error 全为**预存在基线**且不在本 change 改动文件内（§3）。

## 2. 验收标准逐条核对

### 2.1 T1 acceptance（plan 原文 5 条）

| # | 验收标准 | 命令 | 退出码 | 关键输出 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | `openspec.cmd validate add-allocation-executor --strict` 通过（命令与输出贴进产物） | `openspec.cmd validate add-allocation-executor --strict` | 0 | `Change 'add-allocation-executor' is valid` | 通过 |
| 2 | proposal 含 Why / What Changes / Capabilities / 成功标准 / 失败标准·反目标 / Impact + out of scope / 外部参考 / 假设·开放问题 | 结构自检（见下） | 0 | `proposal headings missing: []` | 通过 |
| 3 | 每条 Requirement 标来源锚点，并显式记录 MRD 未定稿 | 结构自检 | 0 | `anchors(来源锚点：): 10`；`MRD 未定稿 recorded: True`（proposal:124 / spec:7） | 通过 |
| 4 | specs delta 每条 Requirement 用 SHALL + ≥1 Scenario，覆盖可复算金额/顺延/过期/再平衡/现金不足/归零 | 结构自检 | 0 | `requirements: 10`；`without Scenario: []`；`without SHALL: []`；`scenarios: 28`；6 类关键词全 True | 通过 |
| 5 | out of scope 明列：自动下单、选股、账本重建、持仓体检、LLM | 结构自检（切 `## out of scope` 段） | 0 | `out of scope 明列: ['自动下单','选股','账本重建','持仓体检','LLM']` | 通过 |

结构自检命令（可重放）：

```text
$ python - <<'PY'   # 切分 spec 的 ### Requirement 段 + 检查 proposal 章节/锚点
...
requirements: 10 ['R1','R2','R3','R4','R5','R6','R7','R8','R9','R10']
requirements without Scenario: []
requirements without SHALL: []
scenarios: 28
anchors(来源锚点：): 10
proposal headings missing: []
MRD 未定稿 recorded: True
6 类覆盖关键词: {'可复算': True, '顺延': True, '过期': True, '再平衡': True, '现金不足': True, '归零': True}
out of scope 明列: ['自动下单', '选股', '账本重建', '持仓体检', 'LLM']
（exit 0）
```

### 2.2 proposal 成功标准（5 条，逐条）

| # | 成功标准（原文摘要） | 是否达成 | 证据（命令 + 退出码 + 关键输出 / 测试节点 id） |
| --- | --- | --- | --- |
| 1 | 金额可复算到元且与 ips 一致：缺口、剩余月数、当月金额可手算；幂等；改 `allocation.target.equity` 金额重算 | 达成 | `python -m pytest -q test/qa/allocation` → exit 0 → `37 passed`；其中 `test_tc_r3_01_gap_and_remaining_months_hand_calc`（gap 100,000 / remaining 24 / echo 含 0.35、1,000,000、250,000、24）、`test_tc_r4_01_regular_month_rounds_to_yuan`（100,000÷24 → 4,167，echo 含取整规则）、`test_tc_r3_02_idempotent`（两次 JSON 与文本逐字节相同）、`test_tc_r1_01_policy_change_recomputes_amount`（equity 0.40 → gap 150,000 / 当月 6,250） |
| 2 | 权益超限只顺延不追高：>35% 当月 0 + 顺延理由；>40% 仅提示、不产减仓/调仓金额 | 达成 | `test_tc_r6_01_defer_when_equity_above_35`（0.36 → deferred=True、当月 0、理由含「顺延」）、`test_tc_r6_02_over_40_percent_hints_only`（0.42 → 顺延 + 40% 提示、无减仓类别/负金额）、`test_tc_r6_04_exactly_35_percent_is_not_deferred`（恰好 0.35 不顺延）→ 均 passed |
| 3 | 快照过期拒绝：>7 天非零退出 + 「数据过期」且不出金额；恰好 7 天允许；缺 `as_of` 拒绝 | 达成 | `test_tc_r7_01_stale_snapshot_rejected`（14 天 → 非零退出、文案含「数据过期」/as_of/14/7、无 JSON）、`test_tc_r7_02_exactly_seven_days_allowed`（7 天 → 成功、`stale.days=7`）、`test_tc_r7_03_missing_as_of_rejected`、`test_tc_r7_04_future_snapshot_rejected` → 均 passed |
| 4 | 提示类不越界：任一桶 >5pp 再平衡提示（桶/偏差 pp/方向）不含调仓金额；现金 <20% 提示 + 补足金额但不改当月权益额 | 达成 | `test_tc_r8_01_deviation_over_5pp_hints`（固收 −15pp 提示，当月买入额与无提示基线相同）、`test_tc_r8_02_within_band_no_hint`、`test_tc_r8_03_hints_do_not_create_trade_amounts`（类别只有三桶、无调仓/减仓文案）、`test_tc_r9_01_cash_shortfall_amount`（补足 50,000 且当月额不变）、`test_tc_r9_02_cash_sufficient_no_hint` → 均 passed |
| 5 | 期末归零：目标月当月金额 = 当期全部缺口、标注「投放期结束」；之后为 0 不再出买入指令 | 达成 | `test_tc_r4_02_target_month_fills_gap`（2028-11 → 当月 = gap，文案含「投放期结束」）、`test_tc_r4_03_after_period_ends_no_buy`（2028-12 → 0，文案含「已结束」）→ 均 passed |

### 2.3 proposal 失败标准 / 反目标（8 条，逐条证明「未触发」）

| # | 失败标准（反目标） | 是否触发 | 证据 |
| --- | --- | --- | --- |
| 1 | 把未验证阈值（40/5/25/-15/MA60）当硬门禁改写金额 | 未触发 | `test_tc_r6_02_over_40_percent_hints_only`（0.42 仅提示、顺延判定不变、无减仓金额）、`test_tc_r8_01…`（提示前后当月额相同）、`test_tc_r9_01…`（现金 15% 不把权益额改 0）；单测 `test_defer_over_cap_adds_hint_only`（engineer `test/service/allocation/`） |
| 2 | 用 LLM 生成/修改数值，或联网取价后再算数 | 未触发 | `grep -rniE "openai\|llm\|gpt\|anthropic" src/service/allocation/` → exit 1（0 命中）；`test_tc_r10_01_offline_and_zero_llm`（禁用 `socket.socket` 后 exit 0，输出无 LLM 痕迹）；实现只用 `decimal`/`calendar` 标准库（`src/service/allocation/executor.py:32` 取整规则为常量） |
| 3 | 用过期快照出指令 / 对缺 `as_of`、缺权益市值猜数 | 未触发 | `test_tc_r7_01/03/04`（过期/缺日期/未来 → 非零退出且无 JSON）、`test_tc_r3_03_missing_equity_market_value_rejects`（缺 `holdings.total_market_value` → 非零退出、无金额）；单测 `test_loader_snapshot_rejects_missing_field[...]` 5 个参数化用例 |
| 4 | 快照派生字段 `gap_to_target`/`monthly_amount` 被直接当结果抄出 | 未触发 | `test_tc_r1_02_derived_fields_are_not_copied`（快照写 9,999,999 / 7，输出仍 gap 100,000、当月 4,167）；单测 `test_loader_snapshot_ignores_derived_deployment_fields` |
| 5 | 输出下单指令 / 具体标的代码 / 账本重建 / 持仓「持有·减仓·清仓」体检 | 未触发 | `test_tc_r10_02_no_order_or_underlying_picks`（无「下单/买入指令/清仓/减仓建议」、无 6 位代码字符串、类别 ⊆ 三桶）、`test_tc_r10_03_no_ledger_or_health_check`（无「账本/持仓成本/清仓/减仓/持有建议」）→ passed |
| 6 | 再平衡变成自动调仓（产出调仓金额或改持仓建议） | 未触发 | `test_tc_r8_03_hints_do_not_create_trade_amounts`（类别仅三桶、无调仓/减仓金额文案）；`rebalance_hints` 在 JSON 中只有提示字段（`test_tc_r8_01` 已核对提示不改变金额） |
| 7 | 金额不可复算：公式输入不回显 / 取整规则不写死 / 同一输入两次不同 | 未触发（附 F1 字面差异） | `test_tc_r3_01`（echo 回显 0.35/1,000,000/250,000/24）、`test_tc_r4_01`（echo 含「四舍五入…ROUND_HALF_UP」取整规则，来源 `executor.py:32`）、`test_tc_r3_02`（幂等逐字节一致）。**但** spec R3-S1 的公式字符串未回显 → F1 |
| 8 | 越界：改 `openspec/specs/`、写 `src/`·`test/`、改 `docs/mrd/`、伪造 MRD 锚点 | 未触发 | `git show --stat --format='' 83449c0` → 仅 8 个文件（`src/apps/cli.py`、`src/service/allocation/{__init__,models,loader,executor}.py`、`test/service/allocation/test_executor.py`、`test/apps/test_cli_ips_plan.py`、`.../tasks.md`），无 `openspec/specs/`、`docs/mrd/`、`pyproject.toml`；`openspec.cmd validate --strict` valid；proposal:124 明写不引用 MRD 编号；T5 只写本文件 |

### 2.4 T3（implementation）acceptance（7 条）

| # | 验收标准 | 命令 / 证据 | 退出码 | 结论 |
| --- | --- | --- | --- | --- |
| 1 | design 契约逐条落地（函数级） | `grep -n "^def " src/service/allocation/executor.py` → `resolve_execution_month_day:105`、`compute_gap:135`、`compute_remaining_months:140`、`round_yuan:149`、`decide_defer:154`、`compute_monthly_amount:173`、`allocate_categories:248`、`rebalance_hints:270`、`cash_floor_hint:301`、`assert_fresh:331`、`compute_plan:351`、`render_plan:408`、`render_plan_json:462`；`loader.py:94/127/144`；`src/apps/cli.py:2051`（run_ips_plan）、`:2321-2323`（`ips plan --as-of/--json`） | 0 | 通过 |
| 2 | 金额可手算到元：单测固定输入对照 | `python -m pytest -q test/service/allocation test/apps/test_cli_ips_plan.py` → `46 tests collected`，包含 `test_compute_gap_hand_calc`、`test_regular_month_buys_gap_over_remaining_months`、`test_round_yuan_half_up_to_yuan` | 0 | 通过 |
| 3 | 权益超限 → 顺延 + 理由，有单测 | `test_defer_when_equity_above_skip`、`test_defer_is_strictly_above_skip_threshold`、`test_defer_over_cap_adds_hint_only`、`test_plan_defer_printed_with_reason`（均在 1078 passed 内） | 0 | 通过 |
| 4 | 快照过期 → 拒绝（非零 + 明确 stderr），有单测 | `test_assert_fresh_rejects_stale_snapshot`、`test_assert_fresh_allows_exactly_stale_days`、`test_plan_stale_snapshot_exits_2`、`test_plan_missing_snapshot_date_exits_1` | 0 | 通过 |
| 5 | 零 LLM：`grep -rn "openai\|llm" src/service/allocation/` 无命中 | 同上 grep（扩展 `gpt\|anthropic`）→ 无输出、exit 1 | 1（无命中即符合） | 通过 |
| 6 | 全量 `python -m pytest -q` 退出码 0；本 change 路径 ruff 新增 0 | 全量 `1177 passed, 32 deselected, 5 warnings in 83.92s`（exit 0）；`python -m ruff check src/service/allocation src/apps/cli.py test/qa/allocation test/service/allocation test/apps/test_cli_ips_plan.py` → `All checks passed!`（exit 0） | 0 | 通过 |
| 7 | `openspec.cmd validate add-allocation-executor --strict` 通过 | `Change 'add-allocation-executor' is valid` | 0 | 通过 |

## 3. 测试执行

| 套件 | 命令 | 结果 | 备注 |
| --- | --- | --- | --- |
| engineer `test/` | `python -m pytest -q test --ignore=test/qa` | exit 0 → `1078 passed, 32 deselected, 2 warnings in 26.25s` | 标准 spec 单测（含 allocation 46 例）；`--ignore` 仅用于分列，门禁以「全量」为准 |
| QA `test/qa/` | `python -m pytest -q test/qa` | exit 0 → `99 passed, 3 warnings in 50.48s` | 62 backtest QA + **37 allocation QA**（本波盲测） |
| QA（本波） | `python -m pytest -q test/qa/allocation` | exit 0 → `37 passed in 47.30s` | 28/28 Scenario + 9 边界/负向 |
| 全量 | `python -m pytest -q` | exit 0 → `1177 passed, 32 deselected, 5 warnings in 83.92s (0:01:23)` | 默认 deselect 32 个 `akshare_legacy`（`pyproject.toml` addopts） |
| 静态检查（全仓） | `python -m ruff check .` | **exit 1 → `Found 38 errors.`** | **基线偏差**：38 个 error 分布在 26 个文件（`scripts/*`、`src/apps/formatters.py`、`src/data_provider/*`、`src/service/{dual_track,report,toplist,value}/*`、`test/{apps,data_provider,service}/*` 等），**全部为本 change 之前的预存在错误**；本 change 改动文件不在其中（`src/apps/cli.py` 也不在列表里） |
| 静态检查（本 change 路径） | `python -m ruff check src/service/allocation src/apps/cli.py test/qa/allocation test/service/allocation test/apps/test_cli_ips_plan.py` | exit 0 → `All checks passed!` | 新增错误 = 0（与基线分开记录） |
| 语法检查 | `python -m compileall -q src test` | exit 0（无输出） | 两套测试均可编译 |

> ruff 基线判定方法：`python -m ruff check . --output-format=concise \| cut -d: -f1 \| sort -u` 得到 26 个报错文件，与 `git show --name-only 83449c0`（8 个改动文件）无交集；`T3` 回合报告亦称「38 errors 全在未改动文件，预存在基线」，与本次实测一致。

## 4. 负向与边界用例（全部真实执行）

| # | 场景 | 输入 | 期望 | 实际（含证据） | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 字段缺失：快照缺 `as_of` | `holdings.as_of` 删除 | 非零退出 + 说明缺日期，不出指令 | `test_tc_r7_03_missing_as_of_rejected` → passed（非零退出、文案含 as_of/缺、无 JSON） | 通过 |
| 2 | 字段缺失：快照缺权益市值 | 删除 `holdings.total_market_value` | 非零退出，不产出金额 | `test_tc_r3_03_missing_equity_market_value_rejects` → passed | 通过 |
| 3 | 字段缺失：缺 `pool.total` | 删除 `pool.total` | 非零退出 | `test_tc_cfg_02_missing_pool_total_rejects` → passed | 通过 |
| 4 | 配置缺键：缺 `allocation.target.cash` | 删除政策键 | 非零退出、不按 0 继续 | `test_tc_cfg_01_missing_policy_key_rejects` → passed（无 JSON、不输出金额） | 通过 |
| 5 | 边界：恰好 7 天 | `as_of` 2026-12-02 vs 计算日 2026-12-09 | 允许执行 | `test_tc_r7_02_exactly_seven_days_allowed` → passed（`stale.days=7`、当月 > 0） | 通过 |
| 6 | 边界：权益恰好 35% | current.equity = 0.35 | 不顺延（严格大于） | `test_tc_r6_04_exactly_35_percent_is_not_deferred` → passed（当月 4,167） | 通过 |
| 7 | 边界：取整 `.5` 向上 | gap 5、remaining 2 → 2.5 | 3 元 | `test_tc_r4_05_round_half_up` → passed（反证：T4 变异实验把 ROUND_HALF_UP→ROUND_HALF_DOWN 后**仅**该用例变红，见 `test-design.md §5`） | 通过 |
| 8 | 边界：取整向下 | gap 12、remaining 5 → 2.4 | 2 元 | `test_tc_r4_06_round_below_half_down` → passed | 通过 |
| 9 | 边界：目标月补齐 | 执行月 2028-11 | 当月 = 全部缺口 | `test_tc_r4_02_target_month_fills_gap` → passed | 通过 |
| 10 | 边界：负缺口 | eq_mv 400,000（gap −50,000） | 当月 0、不卖出 | `test_tc_r4_04_negative_gap_no_sell` → passed | 通过 |
| 11 | 边界：取整不超缺口 | 常规月 | 0 < 当月 ≤ gap | `test_tc_r4_07_monthly_amount_not_exceed_gap` → passed | 通过 |
| 12 | 依赖不可用：网络不可用 | `socket.socket` 被替换为抛错 | 照常产出（本能力无网络依赖） | `test_tc_r10_01_offline_and_zero_llm` → passed | 通过 |
| 13 | 依赖不可用：YAML 损坏 | 非法 YAML | 明确报错（配置错误） | engineer 单测 `test_loader_snapshot_rejects_bad_yaml`（在全量 1078 passed 内）；`test_loader_policy_rejects_unsupported_execution_day` 同类 | 通过 |
| 14 | 对抗：派生字段陷阱值 | 快照 `gap_to_target=9,999,999`、`monthly_amount=7` | 结果仍由政策与原始市值重算 | `test_tc_r1_02_derived_fields_are_not_copied` → passed（gap 100,000 / 当月 4,167） | 通过 |
| 15 | 对抗：提示越界（调仓/减仓金额） | 三桶偏离 −15pp / 现金 15% | 只提示、金额不变 | `test_tc_r8_03`、`test_tc_r9_01` → passed | 通过 |
| 16 | 数字捏造 | 全链路无 LLM | 数值只来自确定性计算 | `grep -rniE "openai\|llm..."` exit 1（无命中）+ `test_tc_r10_01` passed | 通过 |
| 17 | 过滤条件不生效 | — | — | **N/A**：本能力无过滤/筛选语义（不适用，不计未覆盖） | N/A |

负向批跑命令（真实执行，非只看单测名）：

```text
$ python -m pytest -q test/qa/allocation/test_plan_output.py::test_tc_r7_01_stale_snapshot_rejected \
    ...::test_tc_r6_01_defer_when_equity_above_35 \
    ...::test_tc_r9_01_cash_shortfall_amount \
    ...::test_tc_cfg_01_missing_policy_key_rejects
4 passed in 5.62s        （exit 0）
```

## 5. 规格一致性（28/28 Scenario → 覆盖测试）

| Requirement | Scenario | 覆盖测试（QA `test/qa/allocation/`，全部 37 passed；engineer 单测见括号） | 结论 |
| --- | --- | --- | --- |
| R1 | 政策值改动后金额随之重算 | `test_tc_r1_01_policy_change_recomputes_amount`（`test_plan_recomputes_when_policy_changes`） | 覆盖 |
| R1 | 派生字段不得被当结果抄出 | `test_tc_r1_02_derived_fields_are_not_copied`（`test_loader_snapshot_ignores_derived_deployment_fields`） | 覆盖 |
| R2 | 计算日所在月有未到来的最后一个周四 | `test_tc_r2_01_last_thursday_november`（`test_resolve_execution_day_is_last_thursday`） | 覆盖 |
| R2 | 当月执行日已过则取下一月 | `test_tc_r2_02_execution_day_passed_takes_next_month`（`test_resolve_execution_day_on_the_day_and_after`） | 覆盖 |
| R2 | 不择时 | `test_tc_r2_03_no_market_timing`（QA 独有） | 覆盖 |
| R3 | 缺口与月数手算一致 | `test_tc_r3_01_gap_and_remaining_months_hand_calc`（`test_compute_gap_hand_calc`） | 覆盖（回显字面差异见 F1） |
| R3 | 幂等可复算 | `test_tc_r3_02_idempotent`（`test_plan_is_idempotent`） | 覆盖 |
| R3 | 缺权益市值时拒绝 | `test_tc_r3_03_missing_equity_market_value_rejects`（`test_plan_missing_market_value_exits_1`） | 覆盖 |
| R4 | 常规月按缺口均摊到元 | `test_tc_r4_01_regular_month_rounds_to_yuan`（`test_regular_month_buys_gap_over_remaining_months`） | 覆盖 |
| R4 | 目标月补齐使缺口归零 | `test_tc_r4_02_target_month_fills_gap`（`test_target_month_buys_rest_of_gap_and_ends`） | 覆盖 |
| R4 | 投放期结束后不再出买入建议 | `test_tc_r4_03_after_period_ends_no_buy`（`test_after_target_month_no_buy`） | 覆盖 |
| R4 | 缺口为负不出卖出 | `test_tc_r4_04_negative_gap_no_sell`（`test_negative_gap_never_sells`） | 覆盖 |
| R5 | 迁移月只做固收迁移 | `test_tc_r5_01_migration_month_only_fixed_income`（`test_migration_month_only_migrates_fixed_income`） | 覆盖 |
| R5 | 定投月只买宽基 ETF 类别 | `test_tc_r5_02_investment_month_buys_broad_etf_only`（`test_categories_never_name_codes`） | 覆盖 |
| R5 | 定投开始后不再输出迁移金额 | `test_tc_r5_03_no_migration_after_start`（`test_dca_month_has_no_migration_amount`） | 覆盖 |
| R6 | 权益超 35% 时顺延 | `test_tc_r6_01_defer_when_equity_above_35`（`test_defer_when_equity_above_skip`） | 覆盖 |
| R6 | 权益超 40% 只加提示 | `test_tc_r6_02_over_40_percent_hints_only`（`test_defer_over_cap_adds_hint_only`） | 覆盖 |
| R6 | 顺延不产生独立待补额度 | `test_tc_r6_03_no_carryover_bucket`（`test_defer_does_not_carry_over_quota`） | 覆盖 |
| R7 | 快照过期拒绝 | `test_tc_r7_01_stale_snapshot_rejected`（`test_assert_fresh_rejects_stale_snapshot`） | 覆盖 |
| R7 | 恰好 7 天允许执行 | `test_tc_r7_02_exactly_seven_days_allowed`（`test_assert_fresh_allows_exactly_stale_days`） | 覆盖 |
| R7 | 缺 as_of 拒绝 | `test_tc_r7_03_missing_as_of_rejected`（`test_plan_missing_snapshot_date_exits_1`） | 覆盖 |
| R8 | 偏离超 5pp 触发提示 | `test_tc_r8_01_deviation_over_5pp_hints`（`test_rebalance_hint_over_band_does_not_change_amount`） | 覆盖 |
| R8 | 偏离在带内不提示 | `test_tc_r8_02_within_band_no_hint`（`test_rebalance_hint_within_band_is_silent`） | 覆盖 |
| R9 | 现金不足给出补足金额 | `test_tc_r9_01_cash_shortfall_amount`（`test_cash_floor_hint_gives_shortfall_without_changing_amount`） | 覆盖 |
| R9 | 现金充足不提示 | `test_tc_r9_02_cash_sufficient_no_hint`（`test_cash_floor_hint_silent_when_above_floor`） | 覆盖 |
| R10 | 零 LLM 与离线 | `test_tc_r10_01_offline_and_zero_llm`（QA 独有 + 源码 grep） | 覆盖 |
| R10 | 不越界到下单与选股 | `test_tc_r10_02_no_order_or_underlying_picks`（QA 独有） | 覆盖 |
| R10 | 不重建账本与体检 | `test_tc_r10_03_no_ledger_or_health_check`（QA 独有） | 覆盖 |

补充 9 条非 Scenario 用例：`test_tc_r4_05/06/07`、`test_tc_r6_04`、`test_tc_r7_04`、`test_tc_r8_03`、`test_tc_cfg_01/02/03`（对应 spec 的 MUST 条款与 proposal 失败标准）。

## 6. 未覆盖项与风险（如实列）

| # | 未覆盖 / 风险 | 原因 | 影响 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | `--json` 键名未在 design 冻结 | design.md:99-100 只给中文字段清单；键名由 T3 定 | 下游机检/集成可能二次对齐；本波 T4 已在 `test-design.md §1.2` 冻结契约 + 别名归一 | F2：T3/T2 在 design 补 JSON schema，或追认 T4 契约为准 |
| 2 | 迁移月恰逢权益超限的优先级 | spec 未定义；design 状态机顺序（迁移月先于顺延）才写 | 不测以避免「发明范围」；当前实现按 design 顺序 | T6 评审确认该顺序可接受；若 Owner 要求写进 spec，另立 change |
| 3 | 执行日遇休市/节假日（KQ-1）、顺延额度结转（Q4） | Owner 未答复（`config/knowledge/known_unknowns.yaml` 的 `KU-2026-11-alloc-holiday-01` / `-carryover-01`） | 本波按假设执行（仍按日历周四 / 不记账）；答复后可能改 `resolve_execution_month_day` 或触账本 | 答复到达后回采；`-holiday-01` due = 2026-11-15T22:30:00+08:00 |
| 4 | 真实私人快照（`config/ips.local.yaml`）未参与验证 | 隐私边界：gitignored，不入报告、不被测试读取；T4/T5 全用合成数（pool 1,000,000 等） | 首次在真实快照上运行时可能因字段缺失被 exit 1 拒绝（这是设计行为，不是缺陷） | 人工按 §8 加一条本机命令自测；报告不记录任何私人数值 |
| 5 | `--as-of` 省略时「取本机当日」未测 | 时间依赖会让用例不稳定；spec 未把该默认行为写成 Scenario | 省略参数路径未被自动化覆盖 | 若需覆盖，T3 用可注入时钟或增加参数化日期；不建议在 QA 套件里读系统时钟 |
| 6 | design 的退出码 1/2 细分未断言 | spec 只要求「非零」；本套件按 spec 断言（避免设计细节替代需求） | 实现若把过期返回 1 而非 2，现有用例不会红 | 若 T6 要求 1/2 纳入验收，先由 design 冻结再补用例 |
| 7 | 功能层 case trace 未 append | T5 任务契约 inScope 仅 `verification.md`；写 `docs/cases/` 越界 | `traces.yaml` 目前只有 K3 的 1 条 knowledge 行（`:15-16`） | F3：captain 开补录任务，按 §9 追加 `layer: function/number` 行（append-only） |
| 8 | 性能 / 并发 | 本能力为单次离线算术，无性能/并发语义 | 不适用 | 不覆盖 |

## 7. 失败项记录（结构化 finding）

> **无测试失败**（三套均 exit 0）。下列为本波**未达字面 / 流程缺口**，均不阻塞归档，但 T6 必须裁决或跟踪。

| finding id | 严重度 | 问题 | 要求修复（requiredFix） | 位置（`文件:行` / 测试节点 id） | 阻塞归档 |
| --- | --- | --- | --- | --- | --- |
| F1 | medium | spec R3-S1 字面要求「回显 `0.35 × 1,000,000 − 250,000 = 100,000` 与 `2026-12 → 2028-11（24 个月）`」，实现 echo 只回显四项输入（target 0.35 / pool_total / holdings_market_value / horizon 24），公式字符串缺失；缺口结果与剩余月数出现在 `reasons`（「常规月：缺口 100,000 ÷ 剩余 24 个月 = 4,166.67，取整到元 4,167」）。R3 的 SHALL（回显公式输入使金额可手算到元）已满足，scenario 字面未满足 | 二选一，由 T6 裁决：① T3 在 `render_plan` / `render_plan_json` 的输出里补一行公式回显（如 `公式：0.35 × 1,000,000 − 250,000 = 100,000`，数据来自 `echo` 与 `gap`，不引入新口径）；② T1 把该 Scenario 的 THEN 改为「回显四项公式输入 + 缺口结果与剩余月数」。任一落地后跑 `python -m pytest -q test/qa/allocation` 全绿，并确认 `test_tc_r3_01` 的断言与新口径一致（当前用例按「echo 含输入 + 输出整体含缺口结果」断言，已记录在 `test-design.md §6.5`） | `openspec/changes/add-allocation-executor/specs/allocation-executor/spec.md:57`；`src/service/allocation/executor.py:380-400`（`PlanEcho` 组装）、`:453`（文本取整行）、`:529`（JSON `rounding_rule`） | 否 |
| F2 | low | design 未冻结 `--json` 键名（只给中文字段清单），导致盲测机检契约只能由 T4 侧冻结；集成/后续波次可能二次改键 | 在 `design.md` 的「输出字段」后补一节 JSON schema（键名/类型/必填），或由 captain 追认 `openspec/changes/add-allocation-executor/test-design.md §1.2` 为本波机检契约；不改代码 | `openspec/changes/add-allocation-executor/design.md:99-100` | 否 |
| F3 | low | `docs/cases/case-20261115-allocation-executor/traces.yaml` 只有 K3 的 1 条 `layer: knowledge` 记录，本报告 §9 的 C1–C5 功能层核实结论尚未落 trace（T5 契约 inScope 仅 verification.md） | captain 开补录任务：按 §9 表在 `traces.yaml` **append** 5 条 `kind: reproduction` / `layer: function|number` 记录（`run_id` 指向本文件），不改既有行；补录后 T7 收口核对 | `docs/cases/case-20261115-allocation-executor/traces.yaml:15-16`（现有 knowledge 行） | 否 |

## 8. 复现说明

```bash
# 任何人从干净环境重跑本报告全部命令的最小步骤（Windows，本机无 python3）
git rev-parse HEAD                     # 期望 83449c06006a53aa924accd024aa0d295f6f80d5
python -m pytest -q                    # 1177 passed, 32 deselected, exit 0
python -m pytest -q test/qa            # 99 passed, exit 0
python -m pytest -q test --ignore=test/qa   # 1078 passed, 32 deselected, exit 0（仅分列用）
python -m ruff check .                 # 38 errors（预存在基线，exit 1；本 change 文件不在其中）
python -m ruff check src/service/allocation src/apps/cli.py test/qa/allocation \
    test/service/allocation test/apps/test_cli_ips_plan.py   # All checks passed! exit 0
python -m compileall -q src test       # exit 0
openspec.cmd validate add-allocation-executor --strict   # valid, exit 0
```

## 9. Case 复现核对 + 记 trace

> 对照 proposal「Case 复现锚点」（proposal.md:98-107）与 `docs/cases/case-20261115-allocation-executor/annotations.md` §5 的 5 条可证伪判据。
> 结论编号按 qa.md 现行枚举（`C0` = 知识层 / `C1`–`C5` = 判据 1–5，见 `docs/agent-team/roles/qa.md`）；`annotations.md` 本身尚未编号，已在 K3b 报告登记该缺口。

| 结论编号 | 环 | proposal 锚点（X→Y） | 实际 | verdict | trace id | 卡点（功能 / 知识 / 数据源） |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 计算 | §5-1 金额可复算到元、与 ips 一致：从「零散手算、无固定输出」→「输出公式输入 + 取整规则」 | `test_tc_r3_01`（gap 100,000 / remaining 24 / echo 含 0.35、1,000,000、250,000、24）、`test_tc_r4_01`（4,167 + 取整规则）、`test_tc_r3_02`（幂等）、`test_tc_r1_01`（政策改 0.40 → 6,250）→ 37 passed；本机手算 0.35×1,000,000−250,000=100,000、100,000÷24=4,166.67→4,167 与输出一致 | pass | `20261115-add-allocation-executor-02`（**待 append，见 F3**） | 无（字面回显差异见 F1，不影响「可复算到元」） |
| C2 | 计算 | §5-2 权益 >35% 顺延且不给买入金额：从无规则 → 顺延 + 理由 + 0 金额；>40% 仅提示 | `test_tc_r6_01`（0.36 → deferred、0 金额、理由含顺延）、`test_tc_r6_02`（0.42 → 顺延 + 40% 提示、无减仓金额）、`test_tc_r6_04`（恰好 0.35 不顺延）→ passed | pass | `20261115-add-allocation-executor-03`（**待 append**） | 无 |
| C3 | 计算 | §5-3 快照 >7 天拒绝：从无时效门禁 → 非零退出 + 过期说明、不出指令 | `test_tc_r7_01`（14 天 → 非零、「数据过期」、无 JSON）、`test_tc_r7_02`（7 天 → 允许）、`test_tc_r7_03/04`（缺 as_of / 未来 → 拒绝）→ passed | pass | `20261115-add-allocation-executor-04`（**待 append**） | 无 |
| C4 | 计算 | §5-4 任一桶偏离 >5pp 提示、不自动调仓：从无提示 → 再平衡提示（含偏差 pp）且无调仓金额 | `test_tc_r8_01`（固收 −15pp 提示且金额不变）、`test_tc_r8_02`（带内静默）、`test_tc_r8_03`（无调仓/减仓金额）、`test_tc_r9_01`（现金补足 50,000 不改金额）→ passed | pass | `20261115-add-allocation-executor-05`（**待 append**） | 无 |
| C5 | 呈现 / 计算 | §5-5 零 LLM、无网络：从无执行链 → 纯确定性代码、输出只含类别与金额 | `grep -rniE "openai\|llm\|gpt\|anthropic" src/service/allocation/` → exit 1（0 命中）；`test_tc_r10_01`（禁 socket 仍 exit 0）、`test_tc_r10_02/03`（无下单/代码/账本/体检）→ passed | pass | `20261115-add-allocation-executor-06`（**待 append**） | 无 |
| C0 | 知识 | 本波 canon 口径（K3 盲验） | K3 报告：5 条 canon 4 通过 / 1 退回（F1，已由 K2-repair `a3fe7c4` 修正）；6 条 KU 全部通过 | partial → 已修复 | `20261115-add-allocation-executor-01`（已存在，`traces.yaml:10-16`） | 知识（已闭环） |

**trace 记录状态**：C0 已由 K3b（提交 914a095）append 进 `traces.yaml`；C1–C5 **尚未 append**（T5 任务契约 inScope 仅 `verification.md`，写 `docs/cases/` 越界）→ 已作为 F3 交给 captain。补录时只需 append、不得覆盖 `:15-16` 的既有行；`run_id` 用本报告路径。
