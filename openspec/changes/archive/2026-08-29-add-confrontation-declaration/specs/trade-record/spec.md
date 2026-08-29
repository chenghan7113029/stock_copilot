# trade-record Delta Specification

## MODIFIED Requirements

### Requirement: Optional confrontation association

`trade record` SHALL 接受可选 `--confrontation-id <int>` 并写入 `TradeRecord.confrontation_id`。

#### Scenario: 复盘可读到 declare
- **WHEN** trade record 关联含 declare 的 confrontation
- **THEN** `report trade-review` MAY 在 badcase 条目中展示 declare stance 摘要（只读）
