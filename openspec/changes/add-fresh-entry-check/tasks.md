## 1. 持仓数据模型

- [x] 1.1 `src/dao/models.py` 新增 `PositionRecord` ORM：`code`（唯一）/`cost_price`/`shares`/`opened_at`/`updated_at`
- [x] 1.2 `src/dao/engine.py` 的 `ensure_sqlite_schema()` 补充 `position_records` 兜底建表逻辑
- [x] 1.3 新建 `src/dao/position_repo.py`：`PositionRepo.upsert(code, cost_price, shares) -> None` / `get_by_code(code) -> PositionRecord | None`
- [x] 1.4 单测 `test/dao/test_position_repo.py`：覆盖首次插入、更新已有记录（`opened_at` 不变）两种场景

## 2. CLI `position set`

- [x] 2.1 `src/apps/cli.py` 新增 `run_position_set(code, cost_price, shares, config=None)`
- [x] 2.2 `build_parser()` 新增 `position` 子命令组：`set`（`code`/`--cost`/`--shares`）
- [x] 2.3 单测 `test/apps/test_cli_position.py`：覆盖首次录入、更新已有持仓两种场景

## 3. FreshEntryCheck 呈现逻辑

- [x] 3.1 新建 `src/service/guard/models/fresh_entry_view.py`：`FreshEntryView` dataclass（`code`/`current_price`/`value_summary`/`tech_summary`/`framing_question`/`has_position`/`reminder_text`）
- [x] 3.2 新建 `src/service/guard/fresh_entry_check.py`：`FreshEntryCheck.build(code) -> FreshEntryView`，内部调用 `DualTrackAnalyzer.analyze_offline()` + `PositionRepo.get_by_code()`
- [x] 3.3 实现字段过滤：确保输出结构中不含 `cost_price`/`margin_of_safety` 百分比等易反推持仓盈亏的字段
- [x] 3.4 实现框架提问文本拼装（含现价插值）与持仓存在/不存在两种提醒文案分支
- [x] 3.5 单测 `test/service/guard/test_fresh_entry_check.py`：覆盖已录入持仓、未录入持仓、本地无价值快照或K线数据（错误路径）三种场景，并显式断言输出中不包含 `cost_price` 字面值

## 4. CLI `entry-check`

- [x] 4.1 `src/apps/cli.py` 新增 `run_entry_check(code, as_json=False, output=None, config=None)`：严格离线
- [x] 4.2 `build_parser()` 新增 `entry-check` 子命令：`code`/`--json`/`--output`/`--quiet`
- [x] 4.3 `src/apps/formatters.py` 新增 `format_entry_check_report(view: FreshEntryView, as_json: bool) -> str`
- [x] 4.4 单测 `test/apps/test_cli_entry_check.py`：覆盖成功输出（断言不含成本价字样）、无本地数据报错两种场景

## 5. 端到端验证

- [x] 5.1 `sync 600519` + `position set 600519 --cost <price> --shares 100` 后运行 `entry-check 600519`，人工确认输出不含成本价与盈亏百分比
- [x] 5.2 对未录入持仓的代码运行 `entry-check`，确认输出「未检测到本地持仓记录」提示且正常展示三维分析
- [x] 5.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/product-overview.md` §5.2：PO-05「假设今日首开仓」机制说明更新为「已实现（CLI 手动命令 + 最小持仓表）」
- [x] 6.2 更新 `docs/mrd/roadmap-todo.md`：PO-05 状态更新为「已实现」+ 新增变更记录

## 7. 归档

- [x] 7.1 确认 `tasks.md` 全部任务完成（归档任务除外）
- [ ] 7.2 运行 `/opsx-archive add-fresh-entry-check` 归档，同步 specs 到 `openspec/specs/`
