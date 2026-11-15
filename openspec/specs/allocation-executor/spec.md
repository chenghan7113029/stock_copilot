# allocation-executor Specification

## Purpose
一期 P0 的「配置执行器」：在每个固定执行日，把 IPS 的目标配置、投放期限与当次手工快照做纯算术运算，产出一条「当月买多少、买什么类别」的可复核指令；权益超限时顺延、快照过期时拒绝、桶位偏离与现金不足只提示。不做下单、选股、账本重建、持仓体检，也不使用 LLM。

> 溯源说明：`docs/mrd/mrd-v1.md` **仍是骨架、MRD v1 未定稿**，本 spec 不引用任何 MRD 编号；每条 Requirement 的来源锚点 = 飞书《投资Agent》v2 章节（见 `docs/cases/case-20261115-allocation-executor/annotations.md`）或 `config/ips.yaml` 行号。

## Requirements

### Requirement: R1 政策与快照单一来源

系统 SHALL 只从 `config/ips.yaml`（政策）与 `config/ips.local.yaml`（快照：`pool.total`、`allocation.current`、`holdings.total_market_value`、`holdings.as_of`）读取输入，MUST NOT 硬编码任何政策值；快照派生字段 `deployment.gap_to_target` / `deployment.monthly_amount` MUST NOT 作为输入，结果必须由政策与原始市值重算；指令 SHALL 回显目标比例、投放期限、阈值与 `as_of` 供人工核对「与 ips 一致」。

来源锚点：飞书《投资Agent》v2 §三 验收标准（`docs/cases/case-20261115-allocation-executor/annotations.md:15`）；Owner 2026-11-15 答复 #1/#4（同文件 :23、:26）；`config/ips.yaml:25-30`（目标配置）、`:45-53`（投放政策）、`:57-67`（规则）。

#### Scenario: 政策值改动后金额随之重算

- **WHEN** 把 `allocation.target.equity` 从 0.35 改为 0.40、其余输入不变，重跑同一执行日
- **THEN** 输出中的权益目标与缺口按新政策重算，当月金额随之变化，且输出回显「目标比例 0.40」的来源为 `config/ips.yaml`

#### Scenario: 派生字段不得被当结果抄出

- **WHEN** 在快照中把 `deployment.gap_to_target` 与 `deployment.monthly_amount` 改成任意错误值，其余输入不变，重跑同一执行日
- **THEN** 输出的缺口与当月金额不变（由政策与原始市值重算），且输出不引用这两个派生字段作为结果来源

### Requirement: R2 固定执行日与指令时点

系统 SHALL 把执行日固定为「当月最后一个周四」（`deployment.execution_day: last_thursday`）；指令对应的执行月与执行日 SHALL 取「计算日当日或之后最近的固定执行日」（计算日当天即执行日时取当天），并在指令中标注该日期。系统 MUST NOT 依据行情、当日涨跌或任何外部信息择时，也 MUST NOT 因当日价格改变金额。

来源锚点：Owner 2026-11-15 答复 #2（annotations.md:24）；`config/ips.yaml:50`。

#### Scenario: 计算日所在月有未到来的最后一个周四

- **WHEN** 计算日为 2026-11-15 且请求当月指令
- **THEN** 指令标注执行日为 2026-11-26（2026-11 的最后一个周四）

#### Scenario: 当月执行日已过则取下一月

- **WHEN** 计算日为 2026-12-01 且请求当月指令
- **THEN** 指令标注执行日为 2026-12-31（2026-12 的最后一个周四），执行月为 2026-12

#### Scenario: 不择时

- **WHEN** 同一快照在同一执行日的前一天与当天分别请求同一执行月指令（金额输入相同）
- **THEN** 两次输出的金额、类别与顺延判定完全一致，输出不含任何行情判断

### Requirement: R3 缺口与剩余投放月数可复算

系统 SHALL 按 `权益缺口 = allocation.target.equity × pool.total − holdings.total_market_value` 计算缺口（可为负），并按政策常量推导 `首个定投月 = target_date 所在月 − horizon_months + 1`、`目标月 = target_date 所在月`、`剩余投放月数 = max(当前执行月, 首个定投月) 到目标月的含端点月份数`；指令 SHALL 回显公式输入使金额可手算到元，同一输入 MUST 幂等，缺 `holdings.total_market_value` MUST 拒绝执行。

来源锚点：annotations.md §5 判据 1（:36）；`config/ips.yaml:48-49`（`horizon_months` / `target_date`）；`docs/design/portfolio-plan-v0.1.md:87`（缺口口径）。

#### Scenario: 缺口与月数手算一致

- **WHEN** 快照为 `pool.total=1,000,000`、`holdings.total_market_value=250,000`、执行月为 2026-12
- **THEN** 输出缺口 `100,000`、剩余投放月数 `24`，并回显 `0.35 × 1,000,000 − 250,000 = 100,000` 与 `2026-12 → 2028-11（24 个月）`

#### Scenario: 幂等可复算

- **WHEN** 同一快照、同一执行月连续执行两次
- **THEN** 两次输出的缺口、剩余投放月数与当月金额逐字段一致

#### Scenario: 缺权益市值时拒绝

- **WHEN** 快照只有 `allocation.current.equity` 占比而没有 `holdings.total_market_value`
- **THEN** 以非零退出码结束并说明缺少权益市值字段，不产出金额与类别

### Requirement: R4 当月金额、取整与期末归零

系统 SHALL 按 `当月权益买入额 = 权益缺口 ÷ 剩余投放月数` 计算，并四舍五入到元（.5 向上）；当剩余投放月数为 1（目标月）时，SHALL 把当期全部缺口计入当月，使按该快照估值的权益缺口归零，并标注「投放期结束」；执行月晚于目标月时当月金额 SHALL 为 0 并标注「投放期已结束」，MUST NOT 再产出买入建议。缺口为负或 0 时当月买入额 SHALL 为 0（不产出卖出）。取整规则 MUST 在输出中写明，且 MUST NOT 因取整使某一月超出当期缺口。

来源锚点：annotations.md §5 判据 1（:36）；`config/ips.yaml:48-49`；`docs/design/portfolio-plan-v0.1.md:87`。

#### Scenario: 常规月按缺口均摊到元

- **WHEN** 权益缺口 `100,000`、剩余投放月数 `24`
- **THEN** 当月权益买入额为 `4,167` 元（`100,000 ÷ 24 = 4,166.67` 四舍五入到元），并回显取整规则

#### Scenario: 目标月补齐使缺口归零

- **WHEN** 执行月为目标月 2028-11、当期权益缺口为 `4,159`
- **THEN** 当月权益买入额为 `4,159`，买入后按该快照估值的权益缺口为 `0`，并标注「投放期结束」

#### Scenario: 投放期结束后不再出买入建议

- **WHEN** 执行月晚于目标月（如 2028-12）
- **THEN** 当月权益买入额为 `0`，输出说明「投放期已结束」，不产出任何买入金额或类别建议

#### Scenario: 缺口为负不出卖出

- **WHEN** 权益市值高于目标（缺口为负）
- **THEN** 当月权益买入额为 `0`，输出说明缺口为负，不产出卖出或减仓金额

### Requirement: R5 类别分配

系统 SHALL 按权益 / 固收 / 现金三桶输出类别与金额：权益金额只投**宽基 ETF** 类别（MUST NOT 指定 ETF 代码或个股）；固收 SHALL 仅在迁移月（`首个定投月 − (start_month − 1)`）输出「固收迁移」金额 `= allocation.target.fixed_income × pool.total × migration.trial_ratio`，该月权益为 0；现金当月新增为 0；首个定投月之前 MUST NOT 产出权益买入。

来源锚点：Owner 2026-11-15 答复 #3（annotations.md:25）；`config/ips.yaml:26-29`、`:41`（`trial_ratio`）、`:47`（`start_month`）、`:52`（`new_money_vehicle`）。

#### Scenario: 迁移月只做固收迁移

- **WHEN** 执行月为 2026-11 且 `pool.total=1,000,000`
- **THEN** 权益买入额为 `0`，固收迁移金额为 `135,000`（`0.45 × 1,000,000 × 0.30`），并标注「定投自 2026-12 起」

#### Scenario: 定投月只买宽基 ETF 类别

- **WHEN** 执行月为 2026-12 且未触发顺延
- **THEN** 权益类别的金额等于当月权益买入额，投向类别为「宽基 ETF」，输出不含任何具体代码或个股名称

#### Scenario: 定投开始后不再输出迁移金额

- **WHEN** 执行月为 2026-12 及之后
- **THEN** 固收迁移金额不再出现，现金新增额保持为 0

### Requirement: R6 权益超限顺延

当快照的权益占比高于 `deployment.skip_if_equity_above`（0.35）时，系统 SHALL 把当月权益买入额置为 0，输出「顺延」及理由（含当前占比与阈值），且 MUST NOT 仍给出买入金额。顺延 MUST NOT 单独记账或累积待补额度，SHALL 通过剩余投放月数递减在后续月份重新均摊。权益占比高于 `rules.R1_equity_cap`（0.40）时，系统 SHALL 追加一条**提示**（说明超过未经回测验证的上限），但该提示 MUST NOT 改变顺延判定、MUST NOT 产出减仓或调仓金额。

来源锚点：annotations.md §5 判据 2（:37）；`config/ips.yaml:51`（`skip_if_equity_above`）、`:57`（`R1_equity_cap`）；飞书 v2 §三 修订（annotations.md:16：40% 上限只能作提示）。

#### Scenario: 权益超 35% 时顺延

- **WHEN** 快照权益占比为 `0.36`（高于 0.35）且存在正缺口
- **THEN** 当月权益买入额为 `0`，输出「顺延」并给出理由（权益占比 36% 高于 35%），不出现买入金额

#### Scenario: 权益超 40% 只加提示

- **WHEN** 快照权益占比为 `0.42`
- **THEN** 仍输出顺延与理由，并追加「权益超过 R1 上限 40%（未经回测验证，仅提示）」；输出不含减仓或调仓金额

#### Scenario: 顺延不产生独立待补额度

- **WHEN** 2026-12 因权益超限顺延、2027-01 权益回落至 0.34 且缺口为正
- **THEN** 2027-01 的剩余投放月数为 `23`，当月金额按更新后的缺口与剩余月数计算，输出不含「上期待补」之类的独立额度

### Requirement: R7 快照时效拒绝

系统 SHALL 在计算前校验快照 `as_of` 与计算日的天数差；当 `as_of` 距计算日超过 `rules.R8_stale_days`（7 天）时 MUST 拒绝产出指令，以非零退出码结束，并在错误输出中说明「数据过期」、`as_of`、天数差与阈值。`as_of` 缺失或晚于计算日时 MUST 同样拒绝。天数差恰好为 7 天 SHALL 允许执行。系统 MUST NOT 用过期快照给出任何金额或类别。

来源锚点：Owner 2026-11-15 答复 #4（annotations.md:26）；annotations.md §5 判据 3（:38）；`config/ips.yaml:67`（`R8_stale_days`）、`:11`（快照日期见 `ips.local.yaml`）。

#### Scenario: 快照过期拒绝

- **WHEN** `as_of=2026-11-01`、计算日为 2026-11-15（相差 14 天）
- **THEN** 以非零退出码结束，错误输出说明「数据过期：as_of 2026-11-01 距计算日 14 天 > R8_stale_days 7」，且不产出金额与类别

#### Scenario: 恰好 7 天允许执行

- **WHEN** `as_of` 距计算日恰好 7 天
- **THEN** 正常产出指令，不出现过期拒绝

#### Scenario: 缺 as_of 拒绝

- **WHEN** 快照未提供 `as_of`
- **THEN** 以非零退出码结束并说明缺少快照日期，不产出指令

### Requirement: R8 再平衡提示

系统 SHALL 计算三桶「当前占比 − 目标占比」；当任一桶的绝对偏离大于 `rules.R4_rebalance_band`（5pp = 0.05）时，输出再平衡**提示**（桶名、当前占比、目标占比、偏离 pp、方向）。该提示 MUST NOT 自动调仓，MUST NOT 产出调仓、买卖或减仓金额，也 MUST NOT 改变当月权益买入额。

来源锚点：annotations.md §5 判据 4（:39）；`config/ips.yaml:61`（`R4_rebalance_band`）。

#### Scenario: 偏离超 5pp 触发提示

- **WHEN** 固收当前占比 `0.30`、目标 `0.45`（偏离 −15pp）
- **THEN** 输出「固收低于目标 15pp」的再平衡提示，且当月权益买入额与无提示时相同

#### Scenario: 偏离在带内不提示

- **WHEN** 三桶偏离绝对值均不超过 5pp
- **THEN** 输出「无再平衡提示」，且不产生任何调仓建议或金额

### Requirement: R9 现金不足提示

系统 SHALL 在指令中报告现金桶当前占比与目标占比；当现金市值低于 `rules.R7_cash_floor`（0.20）× `pool.total` 时，输出「现金不足」提示，给出补足到下限所需金额 `= 0.20 × pool.total − 当前现金市值`，并说明「按 R7 应优先补现金、权益买入需人工确认」。本波该提示 MUST NOT 自动把当月权益买入额改为 0，也 MUST NOT 改数或产出调仓金额（不得把未验证阈值升格为硬门禁）。

来源锚点：`config/ips.yaml:66`（`R7_cash_floor`）、`:29`（现金目标）；`docs/design/portfolio-plan-v0.1.md:113`（R7 动作）；annotations.md:16（未验证阈值只作提示的同一口径）。

#### Scenario: 现金不足给出补足金额

- **WHEN** `pool.total=1,000,000`、现金市值 `150,000`（15% < 20%）
- **THEN** 输出「现金不足」提示与补足金额 `50,000`，说明权益买入需人工确认；当月权益买入额仍按缺口公式输出

#### Scenario: 现金充足不提示

- **WHEN** 现金占比为 0.22
- **THEN** 不输出现金不足提示，也不出现补足金额

### Requirement: R10 零 LLM 与工单边界

系统 SHALL 以确定性代码完成全部数值与判定，MUST NOT 调用任何 LLM，MUST NOT 联网取数（仅读取本地 `config/`）；输出 SHALL 仅为人类可读的「当月买多少、买什么类别」工单文本与理由。系统 MUST NOT 生成下单指令、具体标的（个股或 ETF 代码）、账本重建结果，或持仓「持有/减仓/清仓」体检结论。

来源锚点：飞书 v2 §五 明确不做（annotations.md:17）；annotations.md §5 判据 5（:40）、§6 已知边界（:44-46）；`docs/dev/engineering-conventions.md` §9.2（数值不得由 LLM 生成）。

#### Scenario: 零 LLM 与离线

- **WHEN** 执行当月指令计算
- **THEN** 全过程不发起网络请求、不调用 LLM，输出金额只由本次输入与 `config/ips.yaml` 决定

#### Scenario: 不越界到下单与选股

- **WHEN** 正常产出月指令
- **THEN** 输出只含类别（宽基 ETF / 固收迁移 / 现金）与金额，不含任何具体代码、下单指令或交易动作

#### Scenario: 不重建账本与体检

- **WHEN** 快照只提供三桶占比、`pool.total` 与权益总市值，不提供任何成交明细
- **THEN** 指令照常产出，且不要求、不推导逐笔成交、持仓成本或「持有/减仓/清仓」结论
