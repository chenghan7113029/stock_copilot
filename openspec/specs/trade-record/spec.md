# trade-record Specification

## Purpose
TBD - created by archiving change add-trade-review-attribution. Update Purpose after archive.
## Requirements
### Requirement: TradeRecord 最小交易记录模型
系统 SHALL 提供 `TradeRecord` 持久化模型，字段至少包含 `id`（主键）、`code`（股票代码）、`action`（枚举 `BUY`/`SELL`）、`trade_date`、`price`、`quantity`、`checklist_id`（可空整数，软引用未来 `ChecklistRecord.id`，不建数据库外键约束）、`note`（可空文本）、`created_at`。

#### Scenario: 录入不关联 Checklist 的交易记录
- **WHEN** 用户执行 `trade record 600519 buy 1500.0 100`（不带 `--checklist-id`）
- **THEN** SHALL 成功写入一条 `checklist_id=NULL` 的 `TradeRecord`

#### Scenario: 录入关联 Checklist 的交易记录
- **WHEN** 用户执行 `trade record 600519 buy 1500.0 100 --checklist-id 42`
- **THEN** SHALL 成功写入 `checklist_id=42` 的 `TradeRecord`，即使当前系统中不存在 `ChecklistRecord` 表或该 ID 不存在（软引用不做存在性校验）

### Requirement: 交易记录录入的 Input Guard
CLI `trade record` 命令 SHALL 在写入数据库前校验：`action` 必须是 `buy`/`sell` 之一（大小写不敏感）、`price > 0`、`quantity > 0`、`code` 必须通过既有 A 股代码校验（`is_a_share`）。校验失败 SHALL 立即拒绝并提示具体错误，不写入数据库。

#### Scenario: 非法 action 被拒绝
- **WHEN** 执行 `trade record 600519 hold 1500.0 100`
- **THEN** SHALL 拒绝并提示"action 必须为 buy 或 sell"，不写入数据库

#### Scenario: 非正数价格被拒绝
- **WHEN** 执行 `trade record 600519 buy -1 100`
- **THEN** SHALL 拒绝并提示"price 必须大于 0"，不写入数据库

#### Scenario: 非 A 股代码被拒绝
- **WHEN** 执行 `trade record AAPL buy 150 10`
- **THEN** SHALL 拒绝（沿用既有 `UnsupportedMarketError` 语义），不写入数据库

### Requirement: Optional confrontation association

`trade record` SHALL 接受可选 `--confrontation-id <int>` 并写入 `TradeRecord.confrontation_id`。

#### Scenario: 复盘可读到 declare
- **WHEN** trade record 关联含 declare 的 confrontation
- **THEN** `report trade-review` MAY 在 badcase 条目中展示 declare stance 摘要（只读）

