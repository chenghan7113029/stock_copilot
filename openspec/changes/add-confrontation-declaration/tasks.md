## 1. 依赖

- [ ] 1.1 确认 `add-confrontation-narrate-api` 已交付 `ConfrontationRecord` 与 numbered evidence

## 2. Declare 模型与校验

- [ ] 2.1 `service/guard/models/confrontation_declaration.py` dataclass + JSON schema 常量
- [ ] 2.2 `ConfrontationDeclarationValidator`：ref 范围、rationale、stance 枚举
- [ ] 2.3 单测：越界 ref、缺 rationale、成功路径、重复 declare 拒绝

## 3. DAO 扩展

- [ ] 3.1 `ConfrontationRecord` 增加 declare_json、declare_status、declared_at
- [ ] 3.2 `ConfrontationRepo.update_declare(id, declaration)`
- [ ] 3.3 `ChecklistRecord.confrontation_id`、`TradeRecord.confrontation_id` 迁移

## 4. CLI

- [ ] 4.1 `confront declare <id>` 交互式 + `--json-file`
- [ ] 4.2 `confront show <code> [--json]`
- [ ] 4.3 `checklist submit --confrontation-id`、`trade record --confrontation-id`
- [ ] 4.4 单测 CLI 四种场景

## 5. 复盘只读增强

- [ ] 5.1 `report trade-review` badcase 展示 declare stance（有则展示，无则跳过）

## 6. 文档

- [ ] 6.1 更新 `product-overview.md` §8.2 declare 验收项
- [ ] 6.2 更新 `roadmap-todo.md` PO-03/PO-09 关联说明

## 7. 归档前

- [ ] 7.1 手动：confront → declare → checklist → trade record 链路 ID 关联
