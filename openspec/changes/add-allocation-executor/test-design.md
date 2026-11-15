# T4 QA 测试设计（盲测）— add-allocation-executor

> 角色：qa（T4）｜任务：t5｜分支 `feature/add-allocation-executor`｜设计日 2026-11-15
> 被测能力：`ips plan`（配置执行器的纯算术工单）
> 用例落点：`test/qa/allocation/{conftest.py,test_plan_output.py}`（37 条 pytest 用例）
> 结论：**28/28 Scenario 有用例、37 条用例可收集、断言可机检且已做变异实验证明「能红」**；
> 2 处需 T5 与实现对齐的口径列在 §6（JSON 键名未在设计冻结、退出码只按 spec 的「非零」断言）。

## 0. 盲测声明（只读清单）

断言只来自：

1. `specs/allocation-executor/spec.md`：R1–R10 / 28 个 `#### Scenario`（逐条映射见 §3）
2. `proposal.md`：成功标准 5 条、失败标准·反目标（越界 / 硬门禁 / 派生字段当输入）、假设 A1–A6、Q1–Q5
3. `design.md`：CLI 契约（`ips plan --as-of --json`、退出码 0/1/2）、金额公式与取整、判定顺序、手算对照示例
4. 公开政策值 `config/ips.yaml`（tracked，非私人数据）

**未读**：`src/service/allocation/**`、`src/apps/cli.py` 的 ips 分支实现、`test/service/**`、`test/apps/**`。
用例中的合成数只有两处来源：spec 的 Scenario 数字（1,000,000 / 250,000 / 100,000 / 24 / 135,000 / 50,000 / 4,167）
与本文件 §4 手算的边界数（5÷2、12÷5 等）。未从实现反推任何期望值。

## 1. 机检契约（T4 冻结，供 T3/T5 对齐）

### 1.1 调用与退出码

```text
python -m apps.cli ips plan --as-of YYYY-MM-DD [--json]
```

- 退出码断言只按 **spec 的语义**：成功 = 0；数据/配置错误与时效拒绝 = **非零**。
  design 把二者细化为 1 / 2，本套件**不**断言「必须是 1 或 2」——避免用设计细节替代 spec 契约（若 T5 需要更严，另加用例）。
- `--json` 输出必须是**单个可解析 JSON 对象**（stdout），失败时 stdout 无 JSON、错误文案进 stderr。

### 1.2 `--json` 键（设计只给了字段清单，未冻结键名；本表是 T4 的机检契约）

| 语义（design「输出字段」） | 主键 | 本套件接受的别名（大小写不敏感） |
| --- | --- | --- |
| 执行月 | `execution_month` | `exec_month`, `month` |
| 执行日 | `execution_day` | `exec_day`, `day` |
| 缺口 | `gap` | `equity_gap` |
| 剩余投放月数 | `remaining_months` | `remaining`, `months_left` |
| 当月权益买入额 | `equity_buy_amount` | `equity_amount`, `equity_buy`, `monthly_amount` |
| 类别分配 | `categories` | `allocation`, `category_allocation`, `category`（也接受 `{桶: 金额}` 映射） |
| 顺延 | `defer` | `deferral`, `deferred`, `skip`（bool 或 `{deferred, reason}`） |
| 再平衡提示 | `rebalance_hints` | `rebalance`, `rebalance_hint`, `rebalance_alerts`（每个含 `deviation_pp` 类字段） |
| 现金不足提示 | `cash_hint` | `cash`, `cash_shortfall`, `cash_insufficient`（`triggered` + `shortfall`） |
| 时效 | `staleness` | `freshness`, `timeliness`, `stale`, `data_freshness`（`days` + `threshold`） |
| 理由 | `reasons` | `reason`, `notes`, `explanations` |
| 回显 | `echo` | `inputs`, `echo_inputs`, `policy` |

金额一律按「元」断言为**整数**（`Decimal`，非整数直接判失败）；比率回显按数值比对（容 1e-9 浮点尾巴）。
别名只为「键名差异不造成假红」，**值仍严格断言**；缺字段时报出实际键名（`test-design.md §1.2` 可追溯）。

### 1.3 夹具与隔离（为什么跑「临时仓库」）

`ips plan` 的输入是 cwd 下的 `config/ips.yaml` + `config/ips.local.yaml`，且 design **没有**输入路径参数。
仓库里的 `config/ips.local.yaml` 是 gitignored 的**私人快照**——测试绝不能读它，也不能改写它。因此：

- 会话级 `repo_copy`：把 `src/` 复制到临时目录，`config/` 只放测试自己写的合成政策/快照；
- 每条用例以**子进程**（`cwd=临时仓库`、`PYTHONPATH=临时仓库/src`）跑 `python -m apps.cli`，
  既不 import 实现、也不依赖模块级缓存；
- 输出里若找不到夹具快照的 `holdings.as_of`，夹具判「配置未被隔离」失败（防止静默用仓库真值）；
- `IPS_QA_SRC` 环境变量可把被测源码指向一份副本（只用于 §5 的变异实验，不碰仓库 `src/`）。

## 2. 用例与 Scenario 映射（37 条 → 28 Scenario + 9 条边界/负向）

| TC id | Scenario / 依据 | 断言要点（可机检） |
| --- | --- | --- |
| TC-R1-01 | R1-S1 政策值改动后金额随之重算 | equity 0.35→0.40：gap 150,000、当月 6,250；echo 含 0.40 |
| TC-R1-02 | R1-S2 派生字段不得被当结果抄出 | 快照 `gap_to_target=9,999,999` / `monthly_amount=7` 时 gap 仍 100,000、当月仍 4,167 |
| TC-R2-01 | R2-S1 未到来的最后一个周四 | 计算日 2026-11-15 → 执行日 2026-11-26、执行月 2026-11 |
| TC-R2-02 | R2-S2 当月执行日已过取下一月 | 计算日 2026-12-01 → 执行日 2026-12-31、执行月 2026-12 |
| TC-R2-03 | R2-S3 不择时 | 2026-12-30 与 2026-12-31 同快照：金额/类别/顺延逐项一致 |
| TC-R3-01 | R3-S1 缺口与月数手算一致 | gap 100,000、remaining 24；echo 含 0.35/1,000,000/250,000/24；输出含 100,000 |
| TC-R3-02 | R3-S2 幂等可复算 | 同输入两次：`--json` 与文本输出逐字节一致 |
| TC-R3-03 | R3-S3 缺权益市值时拒绝 | 缺 `holdings.total_market_value` → 非零退出、无 JSON、文案含字段名 |
| TC-R4-01 | R4-S1 常规月按缺口均摊到元 | 100,000÷24 → 4,167；echo 有取整规则文案 |
| TC-R4-02 | R4-S2 目标月补齐使缺口归零 | 执行月 2028-11：当月买入 = 当期缺口；文案含「投放期结束」 |
| TC-R4-03 | R4-S3 投放期结束后不再出买入 | 2028-12 → 当月 0；文案含「已结束」 |
| TC-R4-04 | R4-S4 缺口为负不出卖出 | eq_mv 400,000 → gap −50,000、当月 0、无负金额类别 |
| TC-R4-05 | R4 取整边界（`round_yuan` 规则） | 5÷2 = 2.5 → **3**（`.5` 向上，proposal A2） |
| TC-R4-06 | R4 取整边界（向下） | 12÷5 = 2.4 → **2** |
| TC-R4-07 | R4「MUST NOT 因取整使某月超出当期缺口」 | 常规月 0 < 当月 ≤ gap |
| TC-R5-01 | R5-S1 迁移月只做固收迁移 | 2026-11：权益 0、固收迁移 135,000；文案含 2026-12 |
| TC-R5-02 | R5-S2 定投月只买宽基 ETF 类别 | 权益类别名含「宽基/ETF」、金额 = 当月买入额；无 6 位代码字符串 |
| TC-R5-03 | R5-S3 定投开始后不再输出迁移金额 | 2026-12 起迁移/固收金额 = 0；现金新增 = 0 |
| TC-R6-01 | R6-S1 权益超 35% 时顺延 | 0.36 → 顺延 true + 理由、当月 0；文案含「顺延」/36% |
| TC-R6-02 | R6-S2 权益超 40% 只加提示 | 0.42 → 顺延 + 文案含 40%/提示；无减仓/调仓类别、无负金额 |
| TC-R6-03 | R6-S3 顺延不产生独立待补额度 | 2026-12 顺延后 2027-01：remaining 23、当月 4,348（100,000÷23）；无「待补」字样 |
| TC-R6-04 | R6 边界：恰好 35% | 0.35 = 阈值 → **不顺延**、当月 4,167 |
| TC-R7-01 | R7-S1 快照过期拒绝 | as_of 2026-11-01 vs 2026-11-15（14 天）→ 非零退出、文案含「数据过期」/as_of/14/7、无 JSON |
| TC-R7-02 | R7-S2 恰好 7 天允许执行 | 2026-12-02 vs 2026-12-09 → 成功、`stale.days=7`、当月 > 0 |
| TC-R7-03 | R7-S3 缺 as_of 拒绝 | 缺 `holdings.as_of` → 非零退出、文案含 as_of/缺、无 JSON |
| TC-R7-04 | R7「as_of 晚于计算日同样拒绝」 | 未来快照 2026-11-20 vs 2026-11-15 → 非零退出、无 JSON |
| TC-R8-01 | R8-S1 偏离超 5pp 触发提示 | 固收 0.30 vs 0.45 → 有固收提示、偏差 15pp；当月买入额与无提示基线相同 |
| TC-R8-02 | R8-S2 偏离在带内不提示 | 0.33/0.47/0.20 → 提示列表为空 |
| TC-R8-03 | R8「MUST NOT 产出调仓金额」 | 类别只含三桶、无「调仓/减仓」类别或金额文案 |
| TC-R9-01 | R9-S1 现金不足给出补足金额 | 现金 15% → 提示 + 补足 50,000；当月买入额与基线相同 |
| TC-R9-02 | R9-S2 现金充足不提示 | 现金 22% → 未触发、补足 0/None |
| TC-R10-01 | R10-S1 零 LLM 与离线 | 禁用 `socket.socket` 后仍成功；输出无 llm/openai/gpt 痕迹 |
| TC-R10-02 | R10-S2 不越界到下单与选股 | 无「下单/买入指令/清仓/减仓建议」文案；无 6 位代码字符串；类别 ⊆ 三桶 |
| TC-R10-03 | R10-S3 不重建账本与体检 | 无「账本/持仓成本/清仓/减仓」文案 |
| TC-CFG-01 | proposal 失败标准「缺键不得按 0 继续」 | 缺 `allocation.target.cash` → 非零退出、无金额输出 |
| TC-CFG-02 | R1/R3 缺键拒绝 | 缺 `pool.total` → 非零退出、无 JSON |
| TC-CFG-03 | design「`--as-of` 格式错 → 退出码 1（非 argparse usage）」 | `--as-of 2026-13-40` → 非零退出、stderr 无 Traceback |

## 3. 覆盖矩阵（按 Requirement）

| Req | Scenario 数 | 对应用例 | 额外边界 |
| --- | --- | --- | --- |
| R1 | 2 | TC-R1-01/02 | 缺键 → TC-CFG-01 |
| R2 | 3 | TC-R2-01/02/03 | — |
| R3 | 3 | TC-R3-01/02/03 | 缺 pool → TC-CFG-02 |
| R4 | 4 | TC-R4-01…04 | 取整 `.5` 向上/向下、≤ 缺口 → TC-R4-05/06/07 |
| R5 | 3 | TC-R5-01/02/03 | 6 位代码反例合并进 R5-02 |
| R6 | 3 | TC-R6-01/02/03 | 恰好阈值 → TC-R6-04 |
| R7 | 3 | TC-R7-01/02/03 | 未来快照 → TC-R7-04 |
| R8 | 2 | TC-R8-01/02 | 不产调仓金额 → TC-R8-03 |
| R9 | 2 | TC-R9-01/02 | 不改金额（与基线对比，含在两条内） |
| R10 | 3 | TC-R10-01/02/03 | — |

合计：28/28 Scenario 有对应用例；37 条用例 = 28 + 9 条边界/负向（R4 三条、R6 一条、R7 一条、CFG 三条、R8 一条）。

## 4. 合成数与手算（不漏算）

| 场景 | 输入 | 手算 | 用例 |
| --- | --- | --- | --- |
| 常规月 | pool 1,000,000 / eq_mv 250,000 / 2026-12 | gap = 0.35×1e6 − 250,000 = 100,000；100,000÷24 = 4,166.67 → **4,167** | R3-01、R4-01 |
| 迁移月 | 同上 / 2026-11 | 0.45×1e6×0.30 = **135,000**；权益 0 | R5-01 |
| 目标月 | 同上 / 2028-11 | 当月 = gap = 100,000，期末归零 | R4-02 |
| 顺延后一月 | 2027-01 / eq 0.34 | remaining = 23；100,000÷23 = 4,347.83 → **4,348** | R6-03 |
| 现金不足 | 现金 15% | 0.20×1e6 − 150,000 = **50,000** | R9-01 |
| `.5` 向上 | pool 1,000 / eq_mv 345 / 2028-10 | gap 5；remaining 2；2.5 → **3** | R4-05 |
| 向下 | pool 1,000 / eq_mv 338 / 2028-07 | gap 12；remaining 5；2.4 → **2** | R4-06 |

（2026-12 为 `first_dca_month`、2026-11 为迁移月，均由 `target_date 2028-11-30 − horizon 24 + 1` / `start_month 2` 推得，
见 design「金额公式」；测试未直接断言这两个派生月，只通过金额与文案间接核对。）

## 5. 「断言能红」证据（变异实验，不碰仓库 `src/`）

```text
# 1) 正常实现：37 条全绿
$ python -m pytest -q test/qa/allocation
37 passed in 48.88s          （exit 0；首轮为 49.25s，均为本机实测）

# 2) 变异：把 src 副本里的 ROUND_HALF_UP 改成 ROUND_HALF_DOWN（只改临时副本，
#    经 IPS_QA_SRC 指向该副本），期望「取整边界」用例变红
$ IPS_QA_SRC=<temp>/src python -m pytest -q test/qa/allocation
1 failed, 36 passed          （exit 1）
FAILED ...::test_tc_r4_05_round_half_up      # 期望 3、实际 2
```

说明：期望 3 来自 proposal A2「.5 向上」+ design 取整规则，**不是**从实现取值；变异后只有该用例变红，
其余 36 条保持绿，证明断言既不空转、也没有互相串味的宽泛断言。

## 6. 未覆盖 / 待对齐（T5 关注）

1. **`--json` 键名未在设计冻结**：design「输出字段」只给中文语义清单，键名留给 T3。T4 按 §1.2 冻结机检契约并做别名归一；
   若 T3 采用不同键名，夹具会报出实际键并失败——这属**契约对齐**（T5 与 T3 协商），不是断言放宽。
2. **退出码**：spec 只说「非零」，本套件按 spec 断言；design 的 1/2 细分未写成断言（避免设计细节替代需求）。
   若 T5 要把 1/2 纳入验收，建议在 `verification.md` 单列（或由 T3 补 design 冻结后再加用例）。
3. **未定义行为不测**：迁移月恰逢权益超限（状态机顺序只在 design 出现、spec 未规定）、交易日/节假日顺延（KQ-1 未答复）、
   顺延额度结转（Q4 未答复）——按「不发明范围」跳过，不写会误判实现的用例。
4. **不做**：性能/并发、`--json` 之外的格式化细节、真实 `config/ips.local.yaml` 的读取（隐私边界，见 §1.3）。
5. **R3-S1 的「回显公式」口径待 T5 判定**：scenario 字面写「并回显 `0.35 × 1,000,000 − 250,000 = 100,000`」；
   当前套件断言「echo 含四项输入（0.35 / 1,000,000 / 250,000 / 24）+ 输出整体含缺口结果 100,000」。
   若按 scenario 字面要求**公式字符串**回显，则现实现（echo 只有输入、公式信息分散在 `reasons`）可能不满足——
   T5 需判定「可手算到元」的满足层级，必要时提 finding，不得由本设计默认放行。
6. **T5 必跑**：`python -m pytest -q`、`python -m pytest -q test/qa`、`python -m ruff check .`、`python -m compileall -q src test`；
   本文件 §5 的实测只是 T3 工作树当时的快照，T5 以最终字节重跑为准。

## 7. 复现命令

```text
python -m pytest -q test/qa/allocation --collect-only   # 37 tests collected, exit 0
python -m pytest -q test/qa/allocation                  # 37 passed, exit 0（实现就绪时）
python -m ruff check test/qa/allocation                 # All checks passed!, exit 0
python -m compileall -q test/qa/allocation              # exit 0
```
