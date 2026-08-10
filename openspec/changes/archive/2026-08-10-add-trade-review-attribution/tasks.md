## 0. 前置依赖确认（阻断性 Gate）

- [x] 0.1 确认 `add-decision-checklist`（PO-04）的实现状态：若已实现，记录其 `ChecklistRecord` 表结构（`id`/`passed`/`code`/`action` 等字段名），供本 change 归因逻辑的软引用查询对齐；若未实现，继续按"无 Checklist 数据"降级模式实现本 change 的胜率统计子集，Badcase 归因相关任务（第 4 节）标记为待 `add-decision-checklist` 就绪后再执行
- [x] 0.2 若 `add-decision-checklist` 尚未实现，与用户/团队确认是否仅交付"纯价格胜率统计"子集作为本次范围，Badcase 相关任务延后（不适用：PO-04 已实现）

## 1. TradeRecord 数据模型

- [x] 1.1 `src/dao/models.py` 新增 `TradeRecord` ORM：`id`（自增主键）、`code`、`action`（`String`，存储 `"BUY"`/`"SELL"`）、`trade_date`、`price`、`quantity`、`checklist_id`（可空 `Integer`，无 `ForeignKey` 约束）、`note`（可空）、`created_at`
- [x] 1.2 新建 `src/dao/trade_record_repo.py`：`add(record)`、`find_by_code(code)`、`find_all()`、`find_open_positions(code=None)`（按 FIFO 剩余未平仓数量计算）
- [x] 1.3 单测 `test/dao/test_trade_record_repo.py`：覆盖新增、按 code 查询、未平仓持仓计算

## 2. CLI `trade record`（录入交易记录）

- [x] 2.1 `src/apps/cli.py`：新增 `trade` 子命令组，`trade record <code> <buy|sell> <price> <quantity> [--date] [--checklist-id] [--note]`
- [x] 2.2 实现 Input Guard：`action` 枚举校验、`price > 0`、`quantity > 0`、`code` 通过 `is_a_share` 校验；校验失败立即拒绝并提示，不写库
- [x] 2.3 单测 `test/apps/test_cli_trade_record.py`：覆盖成功录入（含/不含 `--checklist-id`）、各类非法输入拒绝场景

## 3. FIFO 配对与胜率统计（不依赖 Checklist）

- [x] 3.1 新建 `src/service/trade_review/models/trade_review_result.py`：`TradeReviewResult`（`win_rate`、`avg_return`、`total_trades`、`open_positions`、`badcase_list`、`checklist_data_available: bool`、`warnings`）
- [x] 3.2 新建 `src/service/trade_review/attribution.py`：FIFO 配对函数（支持部分平仓拆分）、已实现收益率计算、胜率统计
- [x] 3.3 单测 `test/service/trade_review/test_attribution.py`：覆盖简单配对、部分平仓拆分配对、未平仓记录不计入分母三种场景

## 4. Badcase 归因（依赖 add-decision-checklist，可延后执行）

- [x] 4.1 实现 `ChecklistRecord` 软引用查询：给定 `checklist_id`，尝试查询是否存在对应记录及其 `passed` 状态；查不到（表不存在或 ID 不存在）统一返回"不可用"
- [x] 4.2 实现 Badcase 判定逻辑：`passed=True` 且收益率低于阈值（默认 `-8%`，模块内常量）判定为 Badcase；`passed=False` 不计入
- [x] 4.3 实现"无 Checklist 数据时降级"逻辑：`checklist_data_available=False` 时跳过 Badcase 计算，`warnings` 中追加降级说明
- [x] 4.4 实现描述性统计摘要：按 Checklist 字段维度统计 Badcase 分布（具体统计维度依赖 `add-decision-checklist` 实际字段，若尚未实现则本任务占位，待其落地后补充实现）
- [x] 4.5 单测 `test/service/trade_review/test_attribution.py`：覆盖有 Checklist 数据时的 Badcase 判定、`passed=False` 不计入、无 Checklist 数据时的降级三种场景

## 5. SentimentAnalyzer 依赖检查（占位，防止误引入 LLM）

- [x] 5.1 Code Review 检查点：确认 `src/service/trade_review/` 全部计算路径不引入任何 LLM 调用（本 change 明确 Non-Goal），仅保留一个标注"可选增强，非 V1 范围"的接口占位注释供未来参考

## 6. CLI `report trade-review`

- [x] 6.1 `src/apps/cli.py`：新增 `report trade-review [--code <code>] [--json] [--output] [--quiet]` 子命令
- [x] 6.2 `src/apps/formatters.py`：新增 `format_trade_review_report(result, as_json)`
- [x] 6.3 单测 `test/apps/test_cli_report_trade_review.py`：覆盖全量报告、指定 code、无交易记录报错三种场景

## 7. 端到端验证

- [x] 7.1 手动录入若干笔模拟交易记录（含盈利、亏损、部分平仓），运行 `report trade-review`，人工核对胜率/收益率计算正确
- [x] 7.2 若 `add-decision-checklist` 已就绪，补充录入关联 Checklist 的交易记录，验证 Badcase 判定正确；若未就绪，验证降级提示正确出现
- [x] 7.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 8. 文档

- [x] 8.1 更新 `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/trade_review/`
- [x] 8.2 更新 `docs/mrd/product-overview.md` §6/§7：PO-09 状态更新，明确标注"完整 Badcase 归因依赖 add-decision-checklist"
- [x] 8.3 更新 `docs/mrd/roadmap-todo.md`：新增变更记录；若 Badcase 相关任务因依赖未就绪而延后交付，在 roadmap 中明确记录"胜率统计已交付，Badcase 归因待 PO-04 就绪后补充"这一部分完成状态

## 9. 归档

- [x] 9.1 确认 `tasks.md` 全部任务完成（若第 4 节因依赖阻塞被拆分为单独后续 change 交付，需在归档说明中注明范围调整）
- [ ] 9.2 运行 `openspec archive add-trade-review-attribution`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`
