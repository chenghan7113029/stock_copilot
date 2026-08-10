## Why

`product-overview.md` §6「系统流程（全周期）」将「交易后」阶段定义为「历史决策胜率、Badcase 偏差归因、规则反哺 Checklist」，对应 `roadmap-todo.md` PO-09（P2）。这是产品全周期闭环（交易前信息沉淀 → 交易中决策审计 → 交易后复盘归因）的最后一环，目前完全空白：仓库内**没有任何交易记录持久化能力**（`src/dao/models.py` 现有 `StockSnapshot`/`Kline`/`LLMNarrateCache` 三张表，均不承载"用户买了什么、什么时候买的、当时决策依据是什么"这类信息），也没有 Checklist 记录（`add-decision-checklist`/PO-04 尚未立项实现）。

**本 change 存在一个无法回避的前置依赖问题，必须在 proposal 阶段就说清楚**：复盘归因需要两类输入——(1) 交易记录（买卖时间点、价格、数量）；(2) 决策审计记录（Checklist 是否通过，用于判定"当时是否合规决策"）。前者当前完全没有基础设施；后者依赖 `add-decision-checklist`（PO-04，P0，尚未实现）。因此本 change **明确不是一个可以独立、立即实现的 change**，而是一个"设计先行、待前置条件就绪后再排期实现"的提案，proposal/design 阶段即诚实标注依赖阻塞，避免团队误判为"可以马上开工"。

## What Changes

- 新增最小交易记录数据模型 `TradeRecord`（本 change 自建，因为当前无任何持仓/交易记录基础设施可复用）：记录买卖时间点、价格、数量，并预留（非强制外键）与未来 `ChecklistRecord` 的关联方式
- 新增 `service/trade_review/` 复盘归因子域：纯统计计算（**不引入 LLM**），V1 归因逻辑仅覆盖最简单的规则统计：
  - 胜率 = 盈利平仓交易数 / 总平仓交易数（按 FIFO 配对买卖记录计算已实现盈亏）
  - Badcase = 当时关联的 Checklist 已通过（`passed=True`）但实际亏损超过可配置阈值的交易
- 新增 CLI：`trade record <code> <buy|sell> <price> <quantity> [--date] [--checklist-id]`（录入交易记录，纯本地写库，Input Guard 校验）与 `report trade-review [--code <code>]`（严格离线，输出胜率统计 + badcase 列表）
- **明确降级路径**：若调用时 `add-decision-checklist` 尚未实现（`checklist_id` 恒为空），复盘归因**仍可运行**，但退化为"仅基于价格的胜率统计"，不产出 badcase 归因（因为 badcase 判定依赖 Checklist 通过状态），报告中显式提示该降级
- **"规则反哺 Checklist"范围收敛**：V1 **不做**任何自动化机制（不做规则挖掘、不做机器学习权重调整），仅在报告中输出统计摘要（如"N 次 badcase 中，M 次缺少明确止损点"这类基于 Checklist 字段的描述性统计），供人工阅读后自行决定是否修改 Checklist 规则；不实现"系统自动更新 Checklist 必填项"这类自动化能力

## Capabilities

### New Capabilities
- `trade-record`：交易记录的录入、校验与持久化（`TradeRecord` 模型 + Repo + CLI `trade record`）
- `trade-review-attribution`：复盘归因统计计算（胜率、Badcase 判定、描述性统计摘要），纯规则/统计，零 LLM
- `cli-report-trade-review`：`report trade-review` 子命令，严格离线

### Modified Capabilities
（无——本 change 不修改现有 capability 的既有需求）

## Impact

- **新增文件**：
  - `src/dao/models.py` 新增 `TradeRecord` ORM
  - `src/dao/trade_record_repo.py`
  - `src/service/trade_review/analyzer.py`、`src/service/trade_review/attribution.py`、`src/service/trade_review/models/trade_review_result.py`
  - `test/dao/test_trade_record_repo.py`、`test/service/trade_review/`、`test/apps/test_cli_trade_record.py`、`test/apps/test_cli_report_trade_review.py`
- **修改文件**：
  - `src/apps/cli.py`、`src/apps/formatters.py`：新增 `trade record`、`report trade-review` 子命令
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/trade_review/`
- **依赖（本 change 的实施前提，须在 Impact 中明确写出）**：
  - **强依赖 `add-decision-checklist`（PO-04）** 才能完整实现"Badcase = 当时 Checklist 通过但结果亏损"这一归因逻辑；若该 change 未完成，本 change 仅能交付"纯价格胜率统计"子集，Badcase 归因功能不可用（非阻塞性降级，见 design.md 决策 2）
  - 与 `add-portfolio-correlation` **共享** `TradeRecord` 表的设计意图（两者都需要"当前持仓是什么"这一底层信息）；本 change 是两者中率先定义该最小交易记录模型的一方，`add-portfolio-correlation` 应复用本表而非重新建表（交叉引用见该 change 的 design.md）
- **文档**：`docs/mrd/product-overview.md` §6/§7（PO-09 状态更新，标注依赖 PO-04）、`docs/mrd/roadmap-todo.md`（新增变更记录）
