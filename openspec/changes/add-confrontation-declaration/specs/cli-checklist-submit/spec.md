# cli-checklist-submit Delta Specification

## MODIFIED Requirements

### Requirement: Optional confrontation association

`checklist submit` SHALL 接受可选参数 `--confrontation-id <int>` 并写入 `ChecklistRecord.confrontation_id`。

#### Scenario: 关联成功
- **WHEN** `checklist submit 600519 --action buy --confrontation-id 12`
- **THEN** 保存的 record SHALL 含 confrontation_id=12

#### Scenario: ID 不存在
- **WHEN** confrontation_id 不存在
- **THEN** SHALL 拒绝提交并说明 id 无效
