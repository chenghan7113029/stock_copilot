## 1. 数据模型

- [x] 1.1 `src/dao/models.py` 新增 `ChecklistRecord` ORM：`code`/`action`/`value_reasons_json`/`tech_alignment`/`sentiment_position`/`stop_loss_price`/`take_profit_price`/`passed`/`rejection_reasons_json`/`created_at`
- [x] 1.2 `src/dao/engine.py` 的 `ensure_sqlite_schema()` 补充 `checklist_records` 兜底建表逻辑（参考 `llm_narrate_cache` 模式）
- [x] 1.3 新建 `src/dao/checklist_repo.py`：`ChecklistRepo.save(submission, result) -> None` / `list_by_code(code) -> list[ChecklistRecord]`
- [x] 1.4 单测 `test/dao/test_checklist_repo.py`：覆盖保存后可读回、JSON 字段正确序列化/反序列化

## 2. 校验逻辑（service/guard）

- [x] 2.1 新建 `src/service/guard/__init__.py`、`src/service/guard/models/__init__.py`
- [x] 2.2 新建 `src/service/guard/models/checklist.py`：`ChecklistSubmission`（用户输入字段）、`ChecklistValidationResult`（`passed`/`rejection_reasons`）dataclass
- [x] 2.3 新建 `src/service/guard/checklist_validator.py`：`_AVAILABILITY_KEYWORDS`/`_GROUNDED_KEYWORDS` 关键词表 + `_MIN_REASON_CHARS` 阈值常量
- [x] 2.4 实现 `ChecklistValidator.validate(submission) -> ChecklistValidationResult`：价值理由条数门槛、单条有效性判定、必填字段完整性校验（按决策 1-2 顺序执行，累积所有拒绝原因而非遇到第一个就短路）
- [x] 2.5 单测 `test/service/guard/test_checklist_validator.py`：覆盖 spec 中列出的全部场景（理由不足、可得性单一来源、正常通过、必填字段缺失）

## 3. CLI `checklist submit` / `checklist show`

- [x] 3.1 `src/apps/cli.py` 新增 `run_checklist_submit(code, action=None, config=None)`：交互式 prompt 采集字段（价值理由循环输入直到空行、技术面配合、情绪位置、止损点、止盈点）
- [x] 3.2 实现采集后调用 `ChecklistValidator.validate()` + `ChecklistRepo.save()`，`passed=False` 时打印拒绝原因列表与「本次提交不构成合规 Checklist」提示
- [x] 3.3 新增 `run_checklist_show(code, config=None)`：读取 `ChecklistRepo.list_by_code()` 并格式化输出（`--json` 可选）
- [x] 3.4 `build_parser()` 新增 `checklist` 子命令组：`submit`（`code`/`--action`）、`show`（`code`/`--json`）
- [x] 3.5 `src/apps/formatters.py` 新增 `format_checklist_records()`：text/JSON 双格式
- [x] 3.6 单测 `test/apps/test_cli_checklist.py`：mock `input()`，覆盖提交通过、提交被拒绝仍留痕、`checklist show` 有/无记录四种场景

## 4. 端到端验证

- [x] 4.1 手动运行 `checklist submit 600519 --action buy`，分别测试「填两条新闻感觉理由被拒绝」与「填两条引用价值面数据的理由通过」两种路径
- [x] 4.2 运行 `checklist show 600519` 确认两次提交记录（含 `passed=False` 与 `passed=True`）均可查询到
- [x] 4.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 5. 文档更新

- [x] 5.1 更新 `docs/mrd/product-overview.md` §5.2：PO-04「结构化 Checklist」机制说明更新为「已实现（CLI 交互式命令 + 硬拦截 + 留痕）」
- [x] 5.2 更新 `docs/mrd/product-overview.md` §8.1：勾选「买入/卖出意图触发 Checklist，缺字段或仅可得性原因时系统拒绝提交」验收项
- [x] 5.3 更新 `docs/mrd/roadmap-todo.md`：PO-04 状态更新为「已实现」+ 新增变更记录

## 6. 归档

- [ ] 6.1 确认 `tasks.md` 全部任务完成
- [ ] 6.2 运行 `/opsx-archive add-decision-checklist` 归档，同步 specs 到 `openspec/specs/`
