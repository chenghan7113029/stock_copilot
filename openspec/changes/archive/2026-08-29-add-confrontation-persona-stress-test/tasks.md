## 1. 依赖

- [x] 1.1 确认 `add-confrontation-narrate-api` numbered evidence + narrate 管道可用

## 2. PersonaNarrator

- [x] 2.1 `persona_stress_narrator.py`：三 persona prompt + schema
- [x] 2.2 分 persona cache key；单 persona grounded 失败隔离
- [x] 2.3 单测 mock 三 persona 成功/部分失败

## 3. 持久化

- [x] 3.1 `ConfrontationRecord.persona_stress_json` 字段 + repo 更新方法
- [x] 3.2 `--confrontation-id` 更新 vs 新建 record 逻辑

## 4. CLI

- [x] 4.1 `report persona-stress` 子命令 + formatter
- [x] 4.2 单测 CLI json/text 输出

## 5. 文档

- [x] 5.1 `roadmap-todo.md` 新增 PO-03b persona
- [x] 5.2 `competitive-reference.md` §4.1 标注已立项

## 6. 归档前

- [x] 6.1 手动：`report persona-stress 600519 --narrate --confrontation-id N`
