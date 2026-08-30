## 1. Evidence 序号契约

- [x] 1.1 扩展 dual JSON 序列化：bull/bear evidence 含 `index` + `text`
- [x] 1.2 更新 `format_dual_report` 文本模式渲染序号
- [x] 1.3 单测：同一 report 两次分桶 index 稳定

## 2. Confrontation 数据层

- [x] 2.1 `dao/models.py` 新增 `ConfrontationRecord`（evidence_json、narrative_json、narrate_status、created_at）
- [x] 2.2 `dao/engine.py` 建表 + `ConfrontationRepo` save/get/list_by_code
- [x] 2.3 单测 repo 读写

## 3. ConfrontationNarrator

- [x] 3.1 `service/guard/confrontation_narrator.py`：schema、prompt、grounded 重试
- [x] 3.2 集成 `LLMNarrateCache` cache key（evidence hash）
- [x] 3.3 单测：mock LLM 成功/grounded 失败/缓存命中

## 4. CLI report confront

- [x] 4.1 `run_report_confront` + argparse 子命令
- [x] 4.2 `format_confront_report` text/json
- [x] 4.3 单测 CLI：离线 Level 0、`--narrate` mock、无 LLM 降级

## 5. 文档

- [x] 5.1 更新 `roadmap-todo.md` PO-03 进行中状态
- [x] 5.2 Skill README 标注 API 为产品主路径

## 6. 归档前

- [x] 6.1 `pytest test/ -q -m "not network"` 通过（本 change 相关全绿；2 个既有无关失败：`test_cli_value_override` / migration baseline drift）
- [x] 6.2 手动：`report confront 600519` Level 0 OK（confrontation_id=1）；`--narrate` 在无 LLM 配置下降级 failed + exit 1（符合 spec）
