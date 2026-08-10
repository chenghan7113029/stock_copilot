# trade-review-attribution Specification

## Purpose
TBD - created by archiving change add-trade-review-attribution. Update Purpose after archive.
## Requirements
### Requirement: FIFO 配对与胜率统计
系统 SHALL 按 `code` 分组，将 `BUY`/`SELL` 记录按 `trade_date` 排序后用 FIFO 规则配对，计算每笔已平仓配对的已实现收益率 `(sell_price - buy_price) / buy_price`。胜率 SHALL 定义为收益率大于 0 的配对数除以总配对数；未平仓的 `BUY` 记录不计入分母。此计算 MUST 为确定性代码逻辑，MUST NOT 使用 LLM。

#### Scenario: 简单配对胜率计算
- **WHEN** 某 `code` 有两笔已平仓交易，一笔盈利一笔亏损
- **THEN** 胜率 SHALL 计算为 `1/2 = 50%`

#### Scenario: 部分平仓的 FIFO 拆分配对
- **WHEN** 一笔 `BUY 100股` 被两笔 `SELL 50股` 分批卖出
- **THEN** SHALL 拆分为两笔独立的配对交易分别计算收益率，均计入胜率分母

#### Scenario: 未平仓记录不计入统计
- **WHEN** 某 `code` 存在一笔 `BUY` 但无对应 `SELL`
- **THEN** 该笔 `BUY` SHALL 不计入胜率分母，报告 SHALL 标注当前持仓（未平仓）数量

### Requirement: Badcase 判定与 Checklist 数据可用性降级
系统 SHALL 提供 Badcase 判定：某笔已配对交易的 `BUY` 记录关联的 `checklist_id` 能解析到 `passed=True` 的 `ChecklistRecord`，且该笔交易已实现收益率低于可配置阈值（默认 `-8%`）时，判定为 Badcase。当系统中不存在任何可解析的 `ChecklistRecord`（`add-decision-checklist` 未实现或用户从未关联）时，SHALL 跳过 Badcase 判定并在报告中显式声明降级原因，SHALL 仍然正常输出胜率等纯价格统计。

#### Scenario: 有 Checklist 数据时判定 Badcase
- **WHEN** 某笔已平仓交易关联的 `ChecklistRecord.passed=True`，已实现收益率为 `-15%`（低于 `-8%` 阈值）
- **THEN** SHALL 判定为 Badcase 并计入 `badcase_list`

#### Scenario: Checklist 记录未通过时不计入 Badcase
- **WHEN** 某笔已平仓交易关联的 `ChecklistRecord.passed=False`，已实现收益率为 `-15%`
- **THEN** SHALL 不判定为 Badcase（因为决策本身未通过合规审计，不属于"合规决策仍亏损"的 Badcase 定义）

#### Scenario: 无 Checklist 数据时降级但胜率仍可用
- **WHEN** 系统中所有 `TradeRecord.checklist_id` 均为 `NULL` 或均无法解析到 `ChecklistRecord`
- **THEN** `badcase_list` SHALL 为空且报告 SHALL 包含"⚠ 当前无关联 Checklist 记录，无法判定 Badcase"提示；胜率、平均收益率等统计 SHALL 正常计算并展示

### Requirement: 规则反哺仅提供描述性统计，不做自动化
系统 SHALL 在 Badcase 数据可用时提供描述性统计摘要（如按 Checklist 字段维度统计缺失项分布），MUST NOT 自动修改任何 Checklist 规则、MUST NOT 引入机器学习权重调整机制。

#### Scenario: 描述性统计摘要
- **WHEN** 存在 3 笔 Badcase，其中 2 笔关联的 Checklist 记录缺少止损点填写
- **THEN** 报告 SHALL 输出类似"3 次 Badcase 中，2 次未填写止损点"的描述性统计，MUST NOT 自动生成或应用新的 Checklist 规则

