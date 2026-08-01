## Why

`product-overview.md` §5.2 将「假设今日首开仓」列为 P0 决策护航机制（PO-05），用于对抗沉没成本谬误：「定期隐藏成本价/盈亏%，提问『若无仓位今日是否仍愿买入』；否 → 减仓/止损警报」。§3.2 US-02 描述的典型场景是「持仓被套，犹豫是否加仓」时触发该评估。当前仓库完全没有「用户持仓」这个概念——没有持仓成本价的数据模型，也没有任何隐藏成本价重新评估的呈现逻辑。

## What Changes

- 新增最小化持仓记录表 `PositionRecord`（`src/dao/models.py`）：`code`/`cost_price`/`shares`/`opened_at`/`updated_at`，按 `code` 唯一（一个代码只保留一条当前持仓，覆盖式更新，不做多次加仓的历史流水）
- 新增 CLI 录入命令 `python -m apps.cli position set <code> --cost <price> --shares <n>`：录入/更新持仓成本价
- 新增 `src/service/guard/fresh_entry_check.py::FreshEntryCheck.build(code) -> FreshEntryView`：复用 `DualTrackAnalyzer.analyze_offline()` 的价值面+技术面结果，呈现时**不包含**成本价与盈亏百分比，改用「若从零开始，现价是否仍值得买入」的框架提问文本
- 新增 CLI 命令 `python -m apps.cli entry-check <code>`：输出隐藏成本价的三维分析摘要 + 框架提问，由用户在会话中自行回答「是/否」；「否」时输出提醒文案（非自动交易动作，只是提示）

**不包含（明确推迟）：**
- 不做完整持仓管理系统（不支持多次加仓的历史流水、不支持批量持仓、不做盈亏自动计算展示——`cost_price`/`shares` 只用于内部隐藏判断，V1 甚至不强制要求已录入持仓才能使用 `entry-check`，未录入时直接跳过「隐藏」步骤，正常展示三维分析）
- 不做定时/后台调度（无 cron/scheduler 基建），「定期」由用户自行手动重复运行 `entry-check` 命令
- 不持久化用户对「是/否」框架提问的回答（与 Checklist 的持久化职责边界区分，见 design.md 决策 4）
- 不依赖 `add-decision-checklist`（两者独立可用，互不阻塞）

## Capabilities

### New Capabilities
- `position-tracking`：`PositionRecord` 最小持仓数据模型 + `position set` CLI 录入命令
- `fresh-entry-check`：隐藏成本价/盈亏%的框架提问呈现逻辑 + `entry-check` CLI 命令

### Modified Capabilities
（无——不修改 `dual-track-analyzer`、`decision-checklist` 等既有/并行 capability 的既定需求）

## Impact

- **新增文件**：
  - `src/dao/position_repo.py`（`PositionRepo.upsert()`/`get_by_code()`）
  - `src/service/guard/fresh_entry_check.py`（`FreshEntryCheck.build(code) -> FreshEntryView`）
  - `src/service/guard/models/fresh_entry_view.py`（`FreshEntryView` dataclass）
  - `src/apps/cli.py`：新增 `position set`/`entry-check` 子命令
  - `src/apps/formatters.py`：新增 `format_entry_check_report()`
  - `test/dao/test_position_repo.py`
  - `test/service/guard/test_fresh_entry_check.py`
  - `test/apps/test_cli_entry_check.py`
- **修改文件**：
  - `src/dao/models.py`：新增 `PositionRecord` ORM
  - `src/dao/engine.py`：`ensure_sqlite_schema()` 补充建表逻辑
- **依赖**：无新增第三方依赖；功能上依赖已实现的 `DualTrackAnalyzer.analyze_offline()`；不依赖 `add-decision-checklist`（并行独立）
- **文档**：`docs/mrd/product-overview.md` §5.2（PO-05 状态更新为「已实现」）、`docs/mrd/roadmap-todo.md`（PO-05 状态更新 + 变更记录）
