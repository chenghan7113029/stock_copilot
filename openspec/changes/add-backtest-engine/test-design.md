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
| 契约缺口（结构化 finding） | **8 条**：2 high / 4 medium / 2 low，见 §8 —— T3 落地前须由 T2/T7 补契约，否则 §1.2 中标注 `TODO(QA-Fx)` 的断言只能弱化为「有异常/有字段」 |

**给 T5 的一句话**：56 条 Scenario 用例都写成「离线可跑」的形态——依赖真实全 A 数据与 Owner 未答复参数（Q4/Q5/Q6/Q7、KQ-1/KQ-2/KQ-5/KQ-7）的**结论级**断言（真实校准题数值、真实牛熊分档判据、影子期真实计时等）不在单测内，单测只覆盖其「判定链」，真实结论由 T5 端到端取证，**未覆盖原因已在 §7 如实列明**。

**给 T3 的一句话**：§8 的 QA-F2 / QA-F4 会在实现阶段直接决定「能不能写测试」，请在写代码前回 `design.md` 补契约；**QA 不会为了迁就实现改断言**（`roles/qa.md`「测试所有权」）。

---

## 1. 规格一致性表

### 1.1 用例落位（未来文件名，本波不创建）

命名按本任务契约 `test/qa/test_backtest_<topic>.py`。`design.md:545-552` 写的是 `test/qa/backtest/test_*.py`（子目录），**两者不一致**，已登记 `QA-F1`，由 captain 裁定后统一；本设计暂按 `test/qa/test_backtest_<topic>.py` 落位（扁平目录更贴合 `test/qa/README.md` 现行结构「仅 README.md，无子目录」）。

| # | 未来文件 | 覆盖 Requirement | 用例数 |
| --- | --- | --- | --- |
| 1 | `test/qa/test_backtest_prereg.py` | R1、R2 | 6 + 2（§3.1 对抗） |
| 2 | `test/qa/test_backtest_segments.py` | R3、R4 | 6 + 1（§3.2） |
| 3 | `test/qa/test_backtest_multi_comparison.py` | R5 | 3 + 1（§3.3） |
| 4 | `test/qa/test_backtest_stat_inference.py` | R6 | 2 + 2（§5.1） |
| 5 | `test/qa/test_backtest_cost.py` | R7 | 4 + 2（§3.4） |
| 6 | `test/qa/test_backtest_matching.py` | R8 | 4 + 3（§3.5） |
| 7 | `test/qa/test_backtest_adjust.py` | R9 | 3 |
| 8 | `test/qa/test_backtest_no_future.py` | R10 | 3 + 3（§3.6） |
| 9 | `test/qa/test_backtest_financial_timing.py` | R11 | 2 |
| 10 | `test/qa/test_backtest_survivorship.py` | R12 | 4 + 2（§3.7） |
| 11 | `test/qa/test_backtest_benchmark.py` | R13 | 3 + 1（§3.8） |
| 12 | `test/qa/test_backtest_stability.py` | R14 | 2 |
| 13 | `test/qa/test_backtest_labels.py` | R15、R16 | 5 + 2（§5.2、§5.3） |
| 14 | `test/qa/test_backtest_event_study.py` | R17 | 3 |
| 15 | `test/qa/test_backtest_calibration.py` | R18 | 3 + 1（§4） |
| 16 | `test/qa/test_backtest_gates.py` | R19 | 3 + 2（§6） |
| 17 | `test/qa/test_backtest_success_criteria.py` | proposal 成功标准 S1–S5（CLI/台账级） | 5 |
| 18 | `test/qa/test_backtest_anti_goals.py` | proposal 失败标准/反目标 F1–F8（静态 + 行为） | 8 |
| — | `test/qa/conftest.py`（QA 专用 fixture，本波不创建） | 全部 | — |

> `conftest.py` 是 QA 自有文件，允许承载 §10 的 fixture 与 §4 的 `calibration_gate`。`pyproject.toml` 的 markers 不加新标记（本设计只用 `pytest.skipif` / `pytest.importorskip` / 模块级 `skip`，避免改 engineer 拥有的 `pyproject.toml`）。

### 1.2 逐 Requirement / Scenario → 用例

> 断言要点列即用例的 WHEN→THEN 断言；`文件` 指上表落位文件。凡带 `TODO(QA-Fx)` 的，表示契约字段/异常类待 §8 补齐后由 QA 收紧（`roles/qa.md`：QA 自修，engineer 不改 `test/qa/`）。

#### R1 实验预注册先于跑数 — `test_backtest_prereg.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R01-01 | 预注册后正常执行 | 已提交预注册 → 执行器返回成功；台账首行 `prereg_commit` == `git rev-parse HEAD` 前缀（真值取自 `git rev-parse`，不硬编码），且含 `hypothesis_id` 与 `params` | `test_backtest_prereg.py` |
| TC-R01-02 | 无预注册时拒绝执行 | 台账无对应预注册 → 进程退出码非 0（`subprocess`/`SystemExit.code != 0`）；stderr 含缺失字段清单（逐字段可 grep）；台账行数**不变** | `test_backtest_prereg.py` |
| TC-R01-03 | 预注册只在工作区未提交 | 预注册文件存在但 `git status --porcelain` 有该文件 → 拒绝执行，提示含「未提交」；台账不新增行 | `test_backtest_prereg.py` |

#### R2 实验台账逐次落一行且 K 不可事后修改 — `test_backtest_prereg.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R02-01 | 每次执行追加一行 | 同一预注册跑两次 → 台账 2 行，`experiment_id` 两值不同且均非空（`TODO(QA-F8)`：生成规则待定义） | `test_backtest_prereg.py` |
| TC-R02-02 | 修改已写入的台账行被拒绝 | 手工改写 NDJSON 某行 `K` → 读取触发「台账已损坏」拒绝（`TODO(QA-F5)` 锁定异常类）；原文件其余行字节不变；拒绝动作留痕（拒绝记录行可数） | `test_backtest_prereg.py` |
| TC-R02-03 | 改假设必须新开实验 | 对已有 `experiment_id` 改 `params` 保存 → 拒绝；新实验必须写 `parent_experiment_id`，且原行 `params` 不变 | `test_backtest_prereg.py` |

#### R3 三段样本切分 — `test_backtest_segments.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R03-01 | 默认三段切分 | 默认配置输出含 3 段，`Segment` 三值齐全；每段有 `n`、`start`、`end`、`metrics`；年份边界与预注册一致（边界值从夹具配置取，不硬编码 2015/2020） | `test_backtest_segments.py` |
| TC-R03-02 | 区间不在任何段内被拒 | 传入横跨 `OUT_OF_SAMPLE` 与 `VALIDATION` 的区间且未声明跨段 → 拒绝，提示「按段拆分或声明跨段报告」；退出码非 0 | `test_backtest_segments.py` |
| TC-R03-03 | 训练段可重复使用 | 同一规则在训练段跑 3 次 → 全部成功；台账可读出该规则训练段评估次数 == 3（由台账行计数派生） | `test_backtest_segments.py` |

#### R4 样本外一次性烧毁 — `test_backtest_segments.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R04-01 | 首次使用样本外并烧毁 | 首次显式确认 → 执行成功；台账行 `burnt is True` 且 `timestamps` 有烧毁时刻与 `experiment_id`；导出（`ledger`）显示该实验样本外额度已用尽（`TODO(QA-F8)` 导出字段待定义） | `test_backtest_segments.py` |
| TC-R04-02 | 第二次请求样本外被拒绝 | 同实验第二次（换 `params` 或换 `metrics`）→ 拒绝、退出码非 0、提示含「样本外已烧毁」；台账新增一条拒绝记录且 `burnt` 标记仍唯一（计数 == 1） | `test_backtest_segments.py` |
| TC-R04-03 | 新实验拥有独立额度 | 新 `hypothesis_id` 首次请求样本外 → 允许；前后两实验的烧毁标记各自计数（互不重置） | `test_backtest_segments.py` |

#### R5 多重比较校正与 K 报告 — `test_backtest_multi_comparison.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R05-01 | 报告 K 与校正后显著性 | `p=0.01, K=30, method="bonferroni"` → 输出同时含原始 p、`K=30`、method 名、校正后判定；Bonferroni 校正值 ≈ `min(1, 0.01*30)=0.3` 且判定为不显著（如实标不显著） | `test_backtest_multi_comparison.py` |
| TC-R05-02 | 未报告 K 时禁止下结论 | 结果缺 K → 判定为 `Verdict.INCONCLUSIVE`，不得 `VALID`，输出说明缺 K（`TODO(QA-F8)`：`ExperimentRecord.K` 为必填 int，缺失不可表达） | `test_backtest_multi_comparison.py` |
| TC-R05-03 | K 增大导致判定翻转 | 同一 p 分别按 K=1 / K=50 评估 → 前者显著、后者不显著；两行都进台账，`K` 字段分别为 1 / 50 | `test_backtest_multi_comparison.py` |

#### R6 统计推断按有效样本 — `test_backtest_stat_inference.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R06-01 | 同组同涨同跌时按时间块计有效样本 | 30 只 × 100 日共因子序列（名义 n=3000）→ 报告名义 3000；有效样本 = 时间块数且 `< 名义样本量`；CI 由块重采样给出（`TODO(QA-F4)`：`EventStudyResult` 字段待定义） | `test_backtest_stat_inference.py` |
| TC-R06-02 | 默认推断不使用 iid 假设 | 预注册未指定推断口径 → 默认 block bootstrap，输出标注 `block_length` 与 `n_bootstrap`；两者之和不为空（不得静默用 iid） | `test_backtest_stat_inference.py` |

#### R7 成本与摩擦计入每笔成交 — `test_backtest_cost.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R07-01 | 单笔成交成本可分项复算 | 10 万买、11 万卖 → `cost.commission`（买+卖各一笔，含最低额判定）/ `stamp_tax` / `slippage` / `total` 四项分列，且与 §10.2 手算独立算式逐项 `approx` 相等（容差 1e-9） | `test_backtest_cost.py` |
| TC-R07-02 | 小额成交触发最低佣金 | 金额使 `amount*rate < min` → 佣金 == `min`，`notes` 含「触发最低佣金」 | `test_backtest_cost.py` |
| TC-R07-03 | 费率配置缺失时拒绝执行 | 配置删 `stamp_tax` / `commission.min` → 抛 `MissingBacktestConfigError`（design 已给名），退出码非 0，错误信息列出缺失键；**不得**产出任何 `Fill` | `test_backtest_cost.py` |
| TC-R07-04 | 流动性上限截断单笔金额 | 单笔 5 万、该标的 `amount=100 万`、夹具档位上限 1% → `filled_amount == 1 万`，`notes` 含「触及流动性上限」，剩余 4 万在新订单中顺延至下一可成交日 | `test_backtest_cost.py` |

#### R8 A 股撮合约束：封板顺延、T+1、停牌跳过 — `test_backtest_matching.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R08-01 | 一字涨停买不进顺延 | `PriceBar` 日终一字涨停（`open==high==low==close==limit_up_price`）→ 目标日失败记录存在（`FAILED_LIMIT_SEAL`），最终成交日 == 下一可成交日且非封板日，`delay_days >= 1` 并在明细可数（`TODO(QA-F7)`：失败与成交的 Fill 表达待定义） | `test_backtest_matching.py` |
| TC-R08-02 | 跌停卖不出顺延 | 连续 2 日跌停 → 卖单顺延，`delay_days == 2`，明细含「连续封板 2 日」 | `test_backtest_matching.py` |
| TC-R08-03 | 当日买入当日卖出被拒绝 | `Order.signal_date = t` 且同日卖出（同一 `trade_date`）→ `OrderStatus.REJECTED_T1`，`fill_date is None`，最早可卖日 == t 的下一交易日，拒绝原因入 `notes` | `test_backtest_matching.py` |
| TC-R08-04 | 停牌日跳过 | t+1 日 `suspended=True` → `SKIPPED_SUSPENDED`，不计为成交；成交日为复牌后首个可成交日 | `test_backtest_matching.py` |

#### R9 后复权（或分段复权）价格口径 — `test_backtest_adjust.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R09-01 | 前复权请求被拒 | `load_price_series(..., adjust="qfq")`（字符串绕过枚举 / 直接传非法值）→ 抛错（`TODO(QA-F5)`：应专用 `InvalidAdjustModeError`，当前只有 `BacktestDataGapError`），错误信息说明前复权会改写历史价；不返回任何 `PriceBar` | `test_backtest_adjust.py` |
| TC-R09-02 | 分红日无假跳空 | 构造现金分红（除权价跳空 + 派息）序列 → 后复权/分段复权下持有期收益在分红日前后连续；`abs(ret[t]) < 1e-6`（除权当日不产生假跌），而同一原始收盘价直接算会出现 > 阈值假跌（对照组证明用例有效） | `test_backtest_adjust.py` |
| TC-R09-03 | 输出记录口径元数据 | 任一结果含 `adjust_mode`（∈ `{hfq, segmented_hfq}`）、`data_version`、`snapshot_time` 三字段且非空；`adjust_mode` 不得为 `qfq` | `test_backtest_adjust.py` |

#### R10 信号纯函数与成交时点边界 — `test_backtest_no_future.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R10-01 | 信号在 t 日、成交在 t+1 | t 日信号 → 所有 `Fill.fill_date >= t` 的下一交易日（用夹具日历换算，不硬编码日期）；`fill_price` 取自 t+1 及之后的 bar（不等于 t 日 close） | `test_backtest_no_future.py` |
| TC-R10-02 | 越界访问抛错 | `PointInTimeSnapshot(as_of=t)` 内含 `trade_date=t+1` 的 bar → 抛 `FutureDataError`；含 `visible_from > as_of` 的财务记录 → 同样抛错；异常终止该次执行且在台账留下失败原因（依赖 `QA-F2`） | `test_backtest_no_future.py` |
| TC-R10-03 | 同输入同输出（纯函数可复现） | 同一 `PointInTimeSnapshot` 调 `evaluate_condition` 两次 → `EventSignal` 完全相等（含 `event_date`）；两次结果 `==`（frozen dataclass 值相等） | `test_backtest_no_future.py` |

#### R11 财务字段按公告日对齐 — `test_backtest_financial_timing.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R11-01 | 年报在 4 月底之后才可见 | 报告期 2023-12-31、`ann_date=2024-04-25` → `as_of=2024-04-24` 的 `build_point_in_time` 不含该记录；`as_of=2024-04-25` 含之；`visible_from == "2024-04-25"` | `test_backtest_financial_timing.py` |
| TC-R11-02 | 公告日缺失时回退并标注 | `ann_date=None`、报告期 2023-12-31 → 回退 `visible_from == "2024-04-30"`（年报 4 月底）；半年报 → `08-31`；三季报 → `10-31`；结果元数据含「公告日回退」标注 | `test_backtest_financial_timing.py` |

#### R12 生存偏差：退市、ST 与历史成分 — `test_backtest_survivorship.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R12-01 | 退市股在退市前仍被计入 | 2019 年退市标的、区间 2017–2019 → `build_universe` 含该 code；退市日前有成交，退市日后 `delisted=True` 且无新 `Fill` | `test_backtest_survivorship.py` |
| TC-R12-02 | ST 状态按时点判定 | 2024 年才 ST 的标的，评估 2015–2020 → 该段 `PriceBar.st == False`；用今日 ST 标签回填历史 → 用例断言为不合规（对照：构造回填数据必须被拒或标注 `TODO(QA-F4)` 字段） | `test_backtest_survivorship.py` |
| TC-R12-03 | 历史成分与当前成分不同 | 请求 2016 年沪深 300 成分、provider 给 2016 名单 → 返回名单 == 2016 名单（不等于当前名单夹具）；输出标注成分来源与生效日 | `test_backtest_survivorship.py` |
| TC-R12-04 | 名单不可得时报缺口 | provider 无退市/ST 名单 → 抛 `BacktestDataGapError`；错误说明含缺失项与影响范围；**不得**返回「已剔除退市股」的静默降级结果 | `test_backtest_survivorship.py` |

#### R13 基准对比与因子归因 — `test_backtest_benchmark.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R13-01 | 输出相对基准超额 | 验证段结果同时给「相对买入持有」与「相对市场组合」两套超额均值、分布、CI（`TODO(QA-F4)`：结果结构字段待定义） | `test_backtest_benchmark.py` |
| TC-R13-02 | 缺失基准时不出结论 | 预注册未指定基准 / 基准数据不可得 → `verdict == Verdict.INCONCLUSIVE`（不得 `VALID`）；台账记缺失原因 | `test_backtest_benchmark.py` |
| TC-R13-03 | 归因四项齐全 | 输出含 beta / 规模 / 价值 / 动量四项暴露系数与各自贡献，且注明未解释部分；四项键名齐全 | `test_backtest_benchmark.py` |

#### R14 稳定性分档检查 — `test_backtest_stability.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R14-01 | 全期显著但仅一段贡献 | 全样本显著但 80% 绝对贡献来自单一年度 → 结论列标注「仅在 <该年> 有效」，**不得**写「有效」 | `test_backtest_stability.py` |
| TC-R14-02 | 分档样本不足时报警 | 某市值档 < 30 只或跨度 < 3 年 → 该档标注「样本不足」且不参与显著性判定（该档 p 值不进入校正集合） | `test_backtest_stability.py` |

#### R15 标签准入与切点纪律 — `test_backtest_labels.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R15-01 | 软标签被拒绝进入分组 | 以「主题归属」请求分组 → 拒绝，提示「软标签只登记不参与」；登记请求留痕（台账/登记清单可数） | `test_backtest_labels.py` |
| TC-R15-02 | 用未来信息分组的请求被拒 | 以「事后涨跌幅」「当前行业成分」归组历史时点 → 拒绝并说明依赖未来信息；不产出 `GroupAssignment` | `test_backtest_labels.py` |
| TC-R15-03 | 季度重算不回改历史 | 2021Q2 重算新切点 → 2020 年及以前 `GroupAssignment.tiers` 与重算前逐字节相同；`effective_range` 标注各组生效区间 | `test_backtest_labels.py` |

#### R16 部分池化：输出组内分位而非绝对收益预测 — `test_backtest_labels.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R16-01 | 单票样本少时向组均值收缩 | 单票 12 观测、组均值 400 观测 → 输出组内分位 + 收缩后估计，且 `abs(收缩后估计 - 组均值) < abs(收缩后估计 - 单票原始估计)`；标注「样本少，估计接近组均值」 | `test_backtest_labels.py` |
| TC-R16-02 | 拒绝输出绝对收益预测 | 请求「该股票未来收益预测」字段 → 返回中不含该字段；只返回组内分位与样本量（键集合断言） | `test_backtest_labels.py` |

#### R17 事件研究为 MVP 主交付 — `test_backtest_event_study.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R17-01 | 条件成立后 20 / 60 日超额分布 | 「跌破 MA60」条件 → 输出含 20 日与 60 日两窗口，各含事件数、超额均值、中位数、标准差、CI、分年度、分市值组（`TODO(QA-F4)` 字段待定义） | `test_backtest_event_study.py` |
| TC-R17-02 | 事件数不足时不出结论 | 窗口内有效事件数 < 预注册阈值 → 标注「样本不足」，无 `valid/invalid` 判定（只允许 `INCONCLUSIVE` 或「样本不足」状态） | `test_backtest_event_study.py` |
| TC-R17-03 | 允许结论为无信号 | 超额 CI 含 0 且校正后不显著 → 结论「无信号」，且该结论与「有信号」同样计入台账行与 `K` | `test_backtest_event_study.py` |

#### R18 已知答案校准门禁 — `test_backtest_calibration.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R18-01 | 校准通过后允许出结论 | 合成校准题（构造「跌破 MA60」相对买入持有显著为负、CI 不含 0）→ `CalibrationResult.passed is True`；台子标记「可信」；随后研究结论可输出；校准结果入台账 | `test_backtest_calibration.py` |
| TC-R18-02 | 校准不通过时封锁输出 | 方向相反或不显著 → `passed is False`；`assert_calibrated` 使进程退出码非 0（`SystemExit` / CLI），提示含「先修台子」；台账记录校准失败与参数；`TODO(QA-F8)`：`CalibrationResult` 缺「校正后判定」字段 | `test_backtest_calibration.py` |
| TC-R18-03 | 校准失败不得解释为策略无效 | 校准失败路径的任何输出/文案**不含**「MA60 无效」「止损无效」类表述；只允许「台子不可信」；用字符串断言（对 `CalibrationResult` 全字段 + CLI stdout 做禁词扫描） | `test_backtest_calibration.py` |

#### R19 三级门禁状态机 — `test_backtest_gates.py`

| 用例 ID | Scenario | 断言要点 | 文件 |
| --- | --- | --- | --- |
| TC-R19-01 | 未过回测不得进入影子运行 | 状态 `BACKTEST_PENDING` 请求 `SHADOW_RUNNING` → 拒绝（退出码非 0 / 抛错），状态不变，拒绝记录入台账 | `test_backtest_gates.py` |
| TC-R19-02 | 影子期未满不得启用实盘 | 影子 2 个月请求 `LIVE_SMALL` → 拒绝，提示最低 6 个月 + 「方向一致」未满足 | `test_backtest_gates.py` |
| TC-R19-03 | 门禁状态可查询且唯一 | `current(rule_id)` 返回唯一 `GateRecord`；`stage_timestamps` 与 `evidence_experiment_ids` 逐级齐全（已通过级别），未通过级别为空 | `test_backtest_gates.py` |

**覆盖率自检**：56 个 `#### Scenario` → 56 个 TC ID（R1 3 / R2 3 / R3 3 / R4 3 / R5 3 / R6 2 / R7 4 / R8 4 / R9 3 / R10 3 / R11 2 / R12 4 / R13 3 / R14 2 / R15 3 / R16 2 / R17 3 / R18 3 / R19 3 = 56）。`3+3+3+3+3+2+4+4+3+3+2+4+3+2+3+2+3+3+3 = 56`。

---

## 2. proposal 成功/失败标准逐条核对

### 2.1 成功标准 5 条 → 一条可执行断言（落 `test_backtest_success_criteria.py`）

| # | proposal 成功标准 | 可执行断言（命令 + 期望） | 用例 ID |
| --- | --- | --- | --- |
| S1 | 校准题可复现（显著为负 + 报 K 与校正后 p） | `backtest calibrate`（CLI）退出码 0 且结果 JSON 满足：`direction` 为显著跑输；`ci[1] < 0`；`K >= 1`；`corrected_p` 存在且 `< 0.05`（`TODO(QA-F8)` 字段）；校准行在台账 | TC-SC-01 |
| S2 | 台账可审计（一条命令导出 6 类字段 + 改预注册被拒） | `backtest ledger --experiment <id>` 输出含 `hypothesis/params/segment/K/metrics/burnt/prereg_commit` 全部键，且 `hypothesis`、`params` 与预注册 YAML 逐字段一致（读真实 YAML 比对，不用自建 fixture）；篡改预注册后重跑 → 退出码非 0 + 台账留痕 | TC-SC-02 |
| S3 | 样本外只烧一次可机检 | 同假设二次请求样本外：退出码非 0、stderr 含「样本外已烧毁」、台账中该 `hypothesis_id` 的 `burnt is True` 行计数 == 1 | TC-SC-03 |
| S4 | 成本与撮合可手算复算（含封板 + 停牌样例） | 「1 笔涨停封板 + 1 笔停牌 + 1 笔正常」样例：成本四分量与 §10.2 手算一致（`approx` 1e-9）；封板订单 `delay_days >= 1` 且成交日为下一可成交日；停牌单不计成交 | TC-SC-04 |
| S5 | 无未来函数可证伪 + 财务按公告日 | 越界构造 `PointInTimeSnapshot` → `FutureDataError`（负向通过）；`ann_date` 前后可见性用例通过（TC-R11-01）；同时静态断言 `service/backtest/signal.py` 源码不出现 `data_provider` / `dao` / `datetime.now` | TC-SC-05 |

> S1 的「显著为负」在**离线单测**里用合成序列覆盖逻辑（TC-R18-01/02）；真实全 A 的结论级断言只在 T5 端到端取证（§7 未覆盖项 1）。

### 2.2 失败标准/反目标 8 条 → 一条证伪用例（落 `test_backtest_anti_goals.py`）

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

---

## 3. 八条硬约束的证伪用例（代码级）

> 统一纪律：
> 1. 全部使用 `tmp_path` 隔离（`QA-F6` 要求 registry 路径可注入），**不写** `data/backtest/` 真实目录。
> 2. 配置值一律来自**夹具显式声明的测试输入**（示例数值，非生产默认；Q4 未答复），期望值由测试内的独立算式得出，**禁止调用被测成本/统计函数反推期望**。
> 3. 断言只锚 `design.md` §4.1 的公开签名；契约缺口处以 `pytest.raises(Exception)` + 关键字断言 + `TODO(QA-Fx)` 标注，待契约补齐后由 QA 收紧。

### 3.1 预注册 / 台账：跑完后篡改假设或 K 必须被拒

```python
# test/qa/test_backtest_prereg.py
def test_tc_r02_02_tamper_k_rejected(appended_registry, registry_path, first_record):
    """R2 Scenario2：改写已落行 K → 读取即拒；原行不动；拒绝动作留痕。"""
    original = registry_path.read_bytes()
    lines = original.decode("utf-8").splitlines()
    assert '"K"' in lines[0], "夹具前置：首行必须含 K 字段"
    registry_path.write_text(
        "\n".join([lines[0].replace('"K": 1', '"K": 2')] + lines[1:]) + "\n", encoding="utf-8"
    )
    with pytest.raises(Exception) as exc:          # TODO(QA-F5): 锁定 RegistryCorruptedError
        appended_registry.get(first_record.experiment_id)
    assert ("台账" in str(exc.value)) or ("损坏" in str(exc.value))
    # 拒绝动作本身留痕（QA-F2 修复后收紧为：audit 拒绝行计数 == 1）
    assert appended_registry.audit_count() >= 1


def test_tc_r02_03_assumption_change_needs_new_experiment(appended_registry, first_record, prereg_yaml):
    """R2 Scenario3：改假设/参数 → 拒绝保存到原实验，必须新开并写 parent_experiment_id。"""
    with pytest.raises(Exception) as exc:
        appended_registry.append(replace(first_record, params={**first_record.params, "ma_days": 61},
                                         experiment_id=first_record.experiment_id))
    assert "新开" in str(exc.value) or "parent" in str(exc.value).lower()
    assert appended_registry.get(first_record.experiment_id).params == first_record.params
    # 合法路径：新实验必须带 parent_experiment_id
    child = replace(first_record, experiment_id="exp-child", parent_experiment_id=first_record.experiment_id,
                    params={**first_record.params, "ma_days": 61})
    appended_registry.append(child)
    assert appended_registry.get("exp-child").parent_experiment_id == first_record.experiment_id
```

### 3.2 样本外一次性：重复使用必须报错并留痕「已烧毁」

```python
# test/qa/test_backtest_segments.py
def test_tc_r04_02_second_oos_request_rejected(registry, oos_request):
    registry.mark_burnt(oos_request.hypothesis_id, "exp-001")
    with pytest.raises(Exception) as exc:          # 契约：assert_not_burnt 抛错（design §4.1）
        registry.assert_not_burnt(oos_request.hypothesis_id, Segment.OUT_OF_SAMPLE)
    assert "样本外已烧毁" in str(exc.value)
    # 二次请求：换参数、换指标的变体同样拒绝（R4 Scenario2 的两条支路）
    for variant in ({"params": {"ma_days": 61}}, {"metrics": ["sharpe"]}):
        with pytest.raises(Exception):
            registry.assert_not_burnt(oos_request.hypothesis_id, Segment.OUT_OF_SAMPLE)
    assert registry.burn_count(oos_request.hypothesis_id) == 1     # 标记唯一、不可撤销
    assert registry.audit_count() >= 1                             # 拒绝留痕
```

### 3.3 多重比较：只报告 1 个 K 的结果必须判「不可采信」

```python
# test/qa/test_backtest_multi_comparison.py
def test_tc_r05_02_missing_k_is_inconclusive(run_experiment, cfg):
    rec = run_experiment(cfg=cfg, k=None)          # 不提供 K
    assert rec.verdict is Verdict.INCONCLUSIVE     # 不得 VALID
    assert "K" in json.dumps(rec.audit, ensure_ascii=False)   # 说明缺 K

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
# test/qa/test_backtest_cost.py
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
# test/qa/test_backtest_matching.py
SEALED_UP = bar("2020-01-06", close=11.0, limit_up=11.0, open=11.0, high=11.0, low=11.0)  # 一字涨停
OPEN_NEXT = bar("2020-01-07", close=11.5)

def test_tc_r08_01_limit_up_buy_deferred(prices_two_days, cfg):
    fills = execute_orders([Order(code="000001", signal_date="2020-01-03", side=OrderSide.BUY,
                                  requested_amount=10_000, requested_qty=None)],
                           prices_two_days, cfg=cfg)
    failed = [f for f in fills if f.status is OrderStatus.FAILED_LIMIT_SEAL]
    filled = [f for f in fills if f.status is OrderStatus.FILLED]
    assert failed, "封板日必须留下失败记录（可数）"
    assert filled and filled[0].fill_date == "2020-01-07"
    assert filled[0].delay_days >= 1
    assert filled[0].fill_price != SEALED_UP.close

def test_tc_r08_03_t1_rejected(same_day_prices, cfg):
    fills = execute_orders([Order(code="000001", signal_date="2020-01-06", side=OrderSide.SELL,
                                  requested_amount=10_000, requested_qty=None)],
                           same_day_prices, cfg=cfg)   # 当日买入后当日卖出
    assert fills[0].status is OrderStatus.REJECTED_T1
    assert fills[0].fill_date is None
    assert any("T+1" in n or "当日" in n for n in fills[0].notes)

def test_tc_r08_04_suspended_skipped(suspended_next_day, cfg):
    fills = execute_orders([buy_order("2020-01-03")], suspended_next_day, cfg=cfg)
    assert fills[0].status is OrderStatus.SKIPPED_SUSPENDED
    assert fills[0].fill_date > "2020-01-06"       # 复牌后首个可成交日
    assert all(f.status is not OrderStatus.FILLED for f in fills if f.fill_date == "2020-01-06")

def test_tc_r08_max_delay_cap(prices_all_sealed, cfg):
    """反模式「无限循环」：连续封板超过最大顺延上限 → 订单终态失败并留痕（design §3H）。"""
    fills = execute_orders([buy_order("2020-01-03")], prices_all_sealed, cfg=cfg)
    assert fills[-1].status is not OrderStatus.FILLED
    assert "最大顺延" in " ".join(fills[-1].notes) or "上限" in " ".join(fills[-1].notes)
```

### 3.6 未来函数：把 t+1 数据喂进 signal 必须抛错或不改变 t 日决策

```python
# test/qa/test_backtest_no_future.py
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
# test/qa/test_backtest_survivorship.py
def test_tc_r12_04_missing_delisted_list_reports_gap(cfg, provider_without_delisted):
    with pytest.raises(BacktestDataGapError) as exc:
        build_universe("2019-12-31", universe_spec, provider=provider_without_delisted)
    msg = str(exc.value)
    assert "退市" in msg and "影响" in msg           # 缺失项 + 影响范围
    assert "剔除" not in msg                          # 不得静默降级为剔除

def test_tc_r12_00_delisted_present_warns(provider_missing_one_delisted, cfg):
    """对抗：名单少一只退市股 → 必须检出（告警/拒绝），不得当样本干净。"""
    res = build_universe_with_diagnostics("2019-12-31", universe_spec, provider=provider_missing_one_delisted)
    assert res.gaps, "应报告缺口（缺失标的/来源）"
    assert res.n_delisted_expected != res.n_delisted_found
```

### 3.8 基准与归因：无基准对比的结果必须判不可采信

```python
# test/qa/test_backtest_benchmark.py
def test_tc_r13_02_no_benchmark_inconclusive(events, cfg, registry):
    res = compute_event_study(events, benchmark=None, cfg=cfg)     # 基准缺失
    assert res.verdict is Verdict.INCONCLUSIVE
    assert res.verdict is not Verdict.VALID
    assert "基准" in json.dumps(res.__dict__, ensure_ascii=False, default=str)
    assert registry.latest().verdict is Verdict.INCONCLUSIVE       # 台账同步落不可判定
```

---

## 4. 已知答案校准（R18）的验收方式与断言顺序

### 4.1 断言顺序：先修台子，再谈策略（硬性排序）

```
step0  夹具自检：校准题参数（条件、区间、成本、T+1、顺延）全部来自夹具与配置，缺任何一项 → 用例 skip 并记为「配置未定」
step1  run_calibration(...)                    # 必须最先跑，先于任何研究结论用例
step2  assert cal.passed is True               # 不通过 → 台子不可信
step3  assert_calibrated(registry)             # 未过 → 进程退出码非 0，封锁研究输出
step4  只有 step2/step3 通过，后续研究结论用例（R14/R16/R17 的 positive 分支）才有意义
```

**失败时的唯一合法表述**：`台子不可信，先修台子`。**禁止**：把 `passed is False` 写成「MA60 止损无效」或「该规则无效」（TC-R18-03 的禁词扫描）。

落地方式：`test/qa/conftest.py` 提供 session 级 `calibration_gate`，研究结论类用例显式 `usefixtures("calibration_gate")`；校准未通过时这些用例 `pytest.fail("台子不可信：校准未通过，任何研究结论不可采信", pytrace=False)`——**红灯而不是 skip**（skip 会被误读为「不适用」）。

```python
# test/qa/test_backtest_calibration.py
def test_tc_r18_02_calibration_failure_blocks_output(registry, cfg_bullish_broken_loader):
    """校准复现不出「跌破 MA60 显著跑输」→ 封锁一切研究结论（退出码非 0）。"""
    cal = run_calibration(cfg=cfg_bullish_broken_loader, loader=cfg_bullish_broken_loader)
    assert cal.passed is False
    assert cal.direction != "显著跑输"
    with pytest.raises(SystemExit) as e:          # TODO(QA-F5/F8): 收紧为 CalibrationFailedError
        assert_calibrated(registry)
    assert e.value.code != 0
    assert registry.calibration_row().passed is False      # 校准结果入台账（含参数）
    blob = json.dumps(cal.__dict__, ensure_ascii=False, default=str)
    for banned in ("MA60 无效", "策略无效", "止损无效", "应卖"):
        assert banned not in blob

def test_tc_r18_01_calibration_pass_unlocks(registry, cfg_known_answer_loader):
    cal = run_calibration(cfg=cfg_known_answer_loader, loader=cfg_known_answer_loader)
    assert cal.passed is True and cal.ci[1] < 0 and cal.K >= 1
    assert_calibrated(registry)                   # 不抛 = 解锁
```

**校准题的真实结论（离线不可断言，见 §7）**：`跌破 MA60 跑全 A 应显著跑输买入持有`。单测只验证「判定链」（方向、CI 上界、K、封锁）；真实数值断言由 T5 在端到端取证中执行，证据形式为校准结果 JSON + 台账行。

---

## 5. 统计陷阱的对抗用例

### 5.1 同组同涨同跌 → t 值虚高，block bootstrap / cluster-robust SE 必须生效

```python
# test/qa/test_backtest_stat_inference.py
def test_tc_r06_01_block_bootstrap_effective_sample(common_factor_series, cfg_inference):
    """30 只 × 100 日同共因子：名义 n=3000，但有效样本只能是时间块数。"""
    res = compute_event_study(events_from(common_factor_series), benchmark=bench(cfg_inference), cfg=cfg_inference)
    assert res.nominal_n == 3000
    assert res.effective_n <= cfg_inference["n_time_blocks"]
    assert res.effective_n < 3000, "有效样本必须远小于名义样本（否则仍在用 iid）"
    assert res.inference_method == "block_bootstrap"
    assert res.block_length and res.n_bootstrap          # 必须标注块长与重采样次数

def test_tc_r06_01b_iid_t_is_inflated(common_factor_series):
    """对照组证明陷阱真实存在：iid t 值显著，块级 CI 不显著（用例本身有效）。"""
    t_iid = naive_iid_t(common_factor_series)            # QA 侧独立算式（对照，不测被测实现）
    ci_block = block_ci(common_factor_series, block_length=5, n_bootstrap=1000, seed=7)
    assert abs(t_iid) > 2.0 and ci_block[0] <= 0 <= ci_block[1]
```

> `block_ci` 是 QA 侧的**独立实现**（20 行内），用于证明夹具确实触发陷阱；断言被测实现时仍走 `compute_event_study` / `block_bootstrap`。若 T3 实现与 QA 独立实现在同一夹具上结论相反 → 报 finding，不改夹具。

### 5.2 分组换档也计入 K

```python
# test/qa/test_backtest_labels.py
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
# test/qa/test_backtest_labels.py
def test_tc_r15_02_today_grouping_rejected(cfg_labels, features_today):
    with pytest.raises(Exception) as exc:
        assign_groups(["000001"], "2015-06-30", features_today, cfg=cfg_labels)  # 传入今日截面
    assert "未来" in str(exc.value) or "时点" in str(exc.value)
    # 反向确认：同一标的用 2015 时点截面可以分组
    ok = assign_groups(["000001"], "2015-06-30", features_2015, cfg=cfg_labels)
    assert ok["000001"].as_of == "2015-06-30"

def test_tc_r15_03_quarterly_recompute_no_rewrite(assign_history):
    before = assign_groups(codes, "2020-06-30", features_2020, cfg=cfg_labels)
    assign_groups(codes, "2021-06-30", features_2021, cfg=cfg_labels)   # 重算新切点
    after = assign_history.snapshot("2020-06-30", codes)
    assert after == before, "季度重算不得回改历史分组"
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
# test/qa/test_backtest_gates.py
def test_tc_gate_04_no_stage_skipping(gate_sm, rule_id):
    gate_sm.transition(rule_id, GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})
    with pytest.raises(Exception) as exc:
        gate_sm.transition(rule_id, GateStage.LIVE_SMALL, evidence={"experiment_id": "exp-001"})
    assert "跳过" in str(exc.value) or "上一级" in str(exc.value)
    assert gate_sm.current(rule_id).stage is GateStage.BACKTEST_PASSED   # 状态不变
    assert gate_sm.audit_count() >= 1                                    # 留痕

def test_tc_r19_02_shadow_too_short(gate_sm, rule_id, cfg_gates):
    gate_sm.transition(rule_id, GateStage.BACKTEST_PASSED, evidence={"experiment_id": "exp-001"})
    gate_sm.transition(rule_id, GateStage.SHADOW_RUNNING, evidence={"experiment_id": "exp-002"})
    with pytest.raises(Exception) as exc:
        gate_sm.transition(rule_id, GateStage.LIVE_SMALL,
                           evidence={"experiment_id": "exp-002", "months": 2, "direction_agree": True})
    msg = str(exc.value)
    assert "6" in msg and ("方向" in msg or "月" in msg)
    assert gate_sm.current(rule_id).stage is GateStage.SHADOW_RUNNING
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

> 说明：**没有「因为难测所以不测」的项**；1–4 都是「数据/参数未定」或「需要真实时间」，已在用例里退化为可断言的判定链，并明确标注真实结论由 T5 取证。

---

## 8. 结构化 findings（契约缺口，T3 落地前须修）

> 格式：`id / severity / problem / requiredFix / 文件:行`。requiredFix 均为「改哪里、改什么、怎么验证」，可执行。

### QA-F1（medium）QA 用例目录与命名，design 与 T4 契约不一致

- **problem**：`design.md` §6.7 把 QA 用例落在子目录 `test/qa/backtest/test_*.py`，而 T4 任务契约与 `test/qa/README.md` 现行结构是扁平 `test/qa/test_backtest_<topic>.py`；两套并存会出现两份「QA 用例清单」，T5 执行时可能漏跑一半。
- **requiredFix**：captain 裁定唯一落位（建议按本设计：`test/qa/test_backtest_<topic>.py`），并由 T7 在 `design.md` §6.7 与 `test/qa/README.md` 同步该命名；验证方式：`ls test/qa` 结果与 `design.md` §6.7 清单逐条同名，`python -m pytest -q test/qa --collect-only` 收集数与 §1.1 一致。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:545-552`

### QA-F2（high）「失败/拒绝留痕」与「失败不落结果行」自相矛盾

- **problem**：`design.md` §3D 写「失败不落结果行（R1）」，但 spec R2 Scenario2（拒绝动作留痕）、R4 Scenario2（台账新增拒绝记录）、R10 Scenario2（台账记录失败原因）、R19 跳级（拒绝记录写入台账）都要求**拒绝/失败本身入台账**；`ExperimentRecord` 无 `status` 字段，`Verdict` 也没有「失败」值。T5 无法断言「台账里有这条失败记录」，只能断言「没写任何行」——与 spec 相反。
- **requiredFix**：`design.md` §4.1 增加「执行行」与「结果行」的区分与字段清单（例如 `RunRecord{run_id, experiment_id | None, status: run|rejected|failed, reason, at, prereg_commit}`，或给 `ExperimentRecord` 增 `status` 字段并允许 `metrics={}` 的失败行）；并在 §4.1「台账存储机制」写明两类行同文件 append、均逐行哈希。验证方式：TC-R02-02 / TC-R04-02 / TC-R10-02 能读到对应拒绝行且计数 == 1。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:117`、`design.md:317-333`

### QA-F3（medium）预注册的必填字段清单缺失，R1 的「提示缺失字段清单」无法实现

- **problem**：`design.md:424` 只给预注册文件路径 `config/backtest/preregistrations/<hypothesis_id>.yaml`，未定义必填字段（假设陈述 / 参数 / 指标 / 样本区间 / 基准 / 校正方法 / K 口径）。spec R1 Scenario2 要求拒绝时「提示缺失的预注册字段清单」，R5 还要求「校正方法与 K 的计算口径 MUST 在预注册中固定」——没有 schema 就没有清单，也没有校验。
- **requiredFix**：`design.md` §4.1 增 `PreregistrationSpec` 字段清单（至少：`hypothesis_id / statement / params / metrics / segments / benchmark / correction_method / k_definition / created_at`），并写明「校验入口 + 缺键报错文案含字段名」。验证方式：TC-R01-02 对 stderr 做逐字段 grep；`preregister` 子命令对缺字段 YAML 退出码非 0。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:424`、`design.md:439`

### QA-F4（high）R13/R14/R17 的结果 dataclass 未定义字段，且单基准签名表达不了 R13 双基准

- **problem**：`EventStudyResult` / `AttributionResult` / `StabilityResult` 在 `design.md:385/394/400` 被引用但 §4.1 无字段定义；而 spec R13 要求同时给「买入持有」与「市场组合」两个基准的超额，签名 `compute_event_study(events, benchmark, ...)`、`attribution(returns, factors, benchmark)` 只能传一个基准。T5 无法断言「事件数/均值/中位数/CI/分年度/分档」「四项暴露与贡献」「两个基准的超额」——这正是 R13/R14/R17 的全部验收面。
- **requiredFix**：`design.md` §4.1 补三个结果 dataclass 的字段清单（事件研究：`windows[20/60] → {n, mean, median, std, ci, by_year, by_cap_tier, effective_n, inference_method, block_length, n_bootstrap}`；归因：`beta/size/value/momentum` 暴露与贡献 + `unexplained`；稳定性：`by_year / by_market_state / by_cap_tier` + `scope_note`），并把 benchmark 参数改为 `benchmarks: Sequence[Benchmark]`（或在结果里固定两个基准字段）。验证方式：TC-R13-01 / TC-R14-01 / TC-R17-01 的键集合断言。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:385`、`design.md:394`、`design.md:400`

### QA-F5（medium）异常族不完整且语义重叠，负向用例只能弱断言

- **problem**：`BacktestDataGapError` 同时承载「前复权请求被拒」（R9 口径非法）与「数据缺失」（R12 缺口），T5 无法区分是「口径写错」还是「数据没有」，也就无法证明「不静默降级」；「台账已损坏」「校准未通过」「门禁跳级」均无专属异常类。design 只明确了 `FutureDataError`、`BacktestDataGapError`、`MissingBacktestConfigError` 三个。
- **requiredFix**：`design.md` §4.1 增「异常清单」小节，至少定义 `InvalidAdjustModeError`（R9）、`RegistryCorruptedError`（R2）、`CalibrationFailedError`（R18）、`GateSkipError`（R19）、`RegistryImmutableError`（R2 改假设），并约定「每类拒绝必须可由异常类型二分」。验证方式：本设计 8 处 `TODO(QA-F5)` 收紧为具体类型断言；若实现只用基类，T5 报 finding。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:28`、`design.md:357-358`、`design.md:404-420`

### QA-F6（medium）可测试性注入点缺失（registry 路径 / clock / data_version）

- **problem**：`ExperimentRegistry` 只有方法签名（`design.md:404-410`），无构造参数；`data_version` 与 `timestamps` 的产生方式也未定义。T5 只能用真实 `data/backtest/registry.ndjson`（污染工作区、用例互相干扰），且无法构造确定性时间戳来断言「时间戳存在/单调/烧毁时刻唯一」。
- **requiredFix**：`design.md` §4.1 明确 `ExperimentRegistry(store_path: Path, *, clock: Callable[[], str], data_version: str)` 的注入契约（`clock` 供测试注入固定时刻），`data_version` 由调用方/数据快照提供。验证方式：全部 `test/qa` 用例使用 `tmp_path` 上的 registry，且断言 `timestamps["created_at"]` 等于夹具注入时刻。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:404-410`、`design.md:326-331`

### QA-F7（medium）R8「失败 → 顺延成交」在单条 `Fill` 下不可表达

- **problem**：spec R8 要求「订单状态记为失败并顺延到下一个可成交日」，而 `Fill` 只有单个 `status` + 单个 `fill_date`（`design.md:306-315`）：若 `status=FAILED_LIMIT_SEAL` 则 `fill_date=None`（最终成交无处安放）；若 `status=FILLED` 则「失败」这一事实丢失、`delay_days` 只能隐式表达。T5 无法同时断言「目标日失败」与「下一日成交」两条。
- **requiredFix**：`design.md` §4.1 在 `Fill` 上增 `attempts: tuple[OrderAttempt, ...]`（每次目标日尝试的 `date/status/reason`），或把「失败尝试」与「成交」拆为两个 dataclass；并写明「顺延天数 = 首个成功 fill_date 与首个目标日的交易日差」。验证方式：TC-R08-01/02 分别断言 attempts 序列与最终 fill_date。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:306-315`、`design.md:430-433`

### QA-F8（low）三处字段级缺口：`experiment_id` 规则 / `K` 缺失不可表达 / 校准校正后判定

- **problem**：① `ExperimentRecord.experiment_id` 的生成规则未定义（`design.md:320`），R2 Scenario1 的「两次执行实验 ID 不同」无法稳定断言；② `K: int` 为必填，R5 Scenario2 的「结果缺失 K 字段」在契约上不可构造（只能靠调用方不传，而 dataclass 会报 TypeError）；③ spec R18 Scenario1 要求校准「报告 K 与校正后判定」，但 `CalibrationResult` 只有 `passed/direction/ci/K/params/notes`，无校正后 p / 判定字段。
- **requiredFix**：① 在 §4.1 写明 `experiment_id = f"{hypothesis_id}-{seq:04d}"`（或 UUID4）并把 `seq` 计入台账以便断言唯一；② `K: int | None`，或明确「缺失 K = `K=None` 拒绝构造 → 由 `metrics` 输出 `INCONCLUSIVE`」的二选一并写清；③ `CalibrationResult` 增 `corrected_p: float | None` 与 `verdict: Verdict`。验证方式：TC-R02-01 / TC-R05-02 / TC-R18-01 的对应断言。
- **文件:行**：`openspec/changes/add-backtest-engine/design.md:320`、`design.md:324`、`design.md:335-343`

---

## 9. T5 执行清单（本设计的交付判据）

```bash
# 1) QA 套件（本设计落位后应可收集全部 §1.2 用例）
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

---

## 10. 附录：夹具与独立算式

### 10.1 夹具（`test/qa/conftest.py`，未来文件）

| 夹具 | 作用 | 关键纪律 |
| --- | --- | --- |
| `cfg_raw` | 回测配置的**原始映射**（含 commission/stamp_tax/slippage_tiers/liquidity_cap/alpha/segments） | 数值是**测试输入**，非生产默认（Q4 未答复）；缺键变体由 `del cfg_raw[...]` 派生，用于 TC-R07-03 |
| `registry_path` / `appended_registry` | 在 `tmp_path` 上建台账，预置 1 行 | 禁止写真实 `data/backtest/`（QA-F6） |
| `bar(...)` / `prices_*` | 构造 `PriceBar`（含 `limit_up_price` / `suspended` / `delisted` / `st` / `amount`） | 封板日必须 `open==high==low==close==limit_up_price`（A3 一字板口径，Q5 未答复前） |
| `financials.*` | 构造 `FinancialRecord`（含 `ann_date=None` 的回退变体） | 覆盖 R11 两个 Scenario |
| `common_factor_series` | 30 只 × 100 日同共因子序列 | 名义 3000；用于 §5.1 |
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

| 断言锚点 | 出处 |
| --- | --- |
| `PointInTimeSnapshot.__post_init__` 抛 `FutureDataError` | `design.md:276-282`、`design.md:433` |
| `AdjustMode` 无 `qfq`；`load_price_series(adjust=...)` | `design.md:213-216`、`design.md:357-358` |
| `execute_orders(orders, prices, *, cfg)` + `OrderStatus` 五值 | `design.md:221-227`、`design.md:378-379` |
| `next_tradable_day` 递归顺延 + 最大顺延上限 | `design.md:381-382`、`design.md:157` |
| `CostBreakdown` 四分量 | `design.md:298-304` |
| `ExperimentRecord`（含 `burnt` / `audit` / `parent_experiment_id`） | `design.md:317-333` |
| `ExperimentRegistry.append/get/assert_not_burnt/mark_burnt/cumulative_K` | `design.md:404-409` |
| `block_bootstrap(excess, *, block_length, n_bootstrap, seed)` | `design.md:388-389` |
| `multiple_testing_correction(p_values, K, method, *, cfg)` | `design.md:391-392` |
| `compute_event_study` / `attribution` / `partial_pooling` / `stability` | `design.md:385-401` |
| `run_calibration(*, cfg, loader)` / `assert_calibrated(registry)` | `design.md:412-413` |
| `GateStateMachine.current/transition` + `GateStage` 五值 | `design.md:236-242`、`design.md:416-419` |
| `MissingBacktestConfigError`（缺键即拒绝） | `design.md:473`、`design.md:601` |
| `BacktestDataGapError`（数据缺口显式报错） | `design.md:28`、`design.md:186-189` |

---

## 自检记录（本波，T4）

| 检查 | 命令 / 方法 | 结果 |
| --- | --- | --- |
| Scenario 数核对 | 对 `spec.md` 逐条 `grep -c "^#### Scenario"` 汇总 | 56（与 §1.2 的 56 个 TC ID 一一对应） |
| 成功标准数 | `proposal.md` `## 成功标准` 列表 | 5，§2.1 逐条有断言 |
| 失败标准/反目标数 | `proposal.md` `## 失败标准/反目标` 列表 | 8，§2.2 逐条有证伪用例 |
| 八条硬约束 | 飞书 §二 八行 | 8/8 有 §3 代码级负向用例 |
| 是否越界写文件 | `git status --porcelain` + `git show --name-only`（见提交自检） | 本波仅新增本文件；`src/`、`test/`、`openspec/specs/`、`design.md` 未改 |
| 盲测合规 | 全程未打开 `src/`、`test/` 下任何实现文件 | 合规（仅读 spec/proposal/design/飞书/role/README） |
| 无「口头测试点」 | 逐条检查 §1.2 每行为「断言要点」而非「应当测试」 | 通过 |
| 未覆盖项 | §7 七条，均带原因与责任方 | 通过 |
