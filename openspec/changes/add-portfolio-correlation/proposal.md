## Why

`product-overview.md` §4.3「待补充信息面」与 §10 均将「持仓组合相关性（单票决策对整体组合的影响）」列为开放项，对应 `roadmap-todo.md` PO-10（P2）。当前所有分析能力（价值面、技术面、[待建]情绪面）都是**单票视角**：`report value/tech/dual <code>` 只回答"这只股票怎么样"，从不回答"如果我现在买/加仓这只股票，对我整个组合意味着什么"（如是否进一步集中在同一行业、单票占比是否已经过高）。这正是 US 场景中反复出现的"只看单票不看组合"的信息缺口。

**本 change 与 `add-trade-review-attribution` 存在相同性质的前置依赖问题**：要回答"组合"层面的问题，首先需要知道"组合是什么"，即用户当前的持仓列表——而这一基础设施目前完全不存在。若本 change 独立设计一套持仓表，会与 `add-trade-review-attribution`（同批提出，同样需要"当前持仓"数据）各自为政，产生两套相似但不一致的持仓模型，这是明确要避免的重复建设。因此本 change 在设计上**直接复用 `add-trade-review-attribution` 提出的 `TradeRecord` 表**（当前持仓 = 按 `code` 汇总该表中未被 FIFO 配对掉的 `BUY` 剩余数量），不新建独立的持仓表。

## What Changes

- 新增 `service/portfolio/` 组合分析子域，**复用** `add-trade-review-attribution` 的 `TradeRecord`/`trade_record_repo` 获取当前持仓（不新建持仓表），新增：
  - **持仓集中度**：单票市值占比（`position_value / portfolio_total_value`）、前 N 大持仓占比
  - **行业暴露度粗估**：按 `StockSnapshot.industry`（价值面已采集的行业文本字段，如"银行""白酒"）对当前持仓分组，计算目标股票所属行业在组合中的现有占比，回答"如果买入这只股票，是否进一步加重了某个行业的集中暴露"
- 新增 CLI：`python -m apps.cli report portfolio [--code <code>] [--add-quantity <n>]`（严格离线）：不带 `--code` 时展示当前组合的集中度与行业分布概览；带 `--code`（可选 `--add-quantity` 模拟加仓数量）时额外展示"该标的当前占比 + 若按当前价加仓 N 股后的边际集中度变化"
- **明确排除**（Non-Goals，见 design.md）：不做协方差矩阵、组合优化（均值方差模型、有效前沿等机构级量化方法），不做真正的统计学"相关性"（股价收益率相关系数矩阵），V1 的"相关性粗估"仅指"同行业暴露度"这一代理指标

## Capabilities

### New Capabilities
- `portfolio-analyzer`：持仓集中度计算、行业暴露度粗估（`PortfolioAnalyzer` + `PortfolioAnalysisResult`），纯确定性统计，零 LLM
- `cli-report-portfolio`：`report portfolio` 子命令，严格离线，支持"若加仓 N 股"边际影响模拟

### Modified Capabilities
（无——本 change 不修改现有 capability 的既有需求，`TradeRecord`/`trade_record_repo` 由 `add-trade-review-attribution` 定义并交付，本 change 仅作为消费方）

## Impact

- **新增文件**：
  - `src/service/portfolio/analyzer.py`、`src/service/portfolio/models/portfolio_result.py`
  - `test/service/portfolio/`、`test/apps/test_cli_report_portfolio.py`
- **修改文件**：
  - `src/apps/cli.py`、`src/apps/formatters.py`：新增 `report portfolio` 子命令
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/portfolio/`
- **依赖（本 change 的实施前提，须在 Impact 中明确写出）**：
  - **强依赖 `add-trade-review-attribution` 的 `TradeRecord` 表与 `trade_record_repo`** 已实现（本 change 不重新定义持仓/交易记录模型）；若 `add-trade-review-attribution` 尚未落地，本 change 无法实现（无数据来源），应等待其至少完成 §1 数据模型部分后再排期本 change
  - 依赖价值面已采集的 `StockSnapshot.industry` 字段（现状：自由文本，非标准化行业代码，见 design.md 已知局限，交叉引用 `roadmap-todo.md` T-7「行业代码映射 Router」待建项）
- **文档**：`docs/mrd/product-overview.md` §4.3/§7（PO-10 状态更新）、`docs/mrd/roadmap-todo.md`（新增变更记录，交叉引用 `add-trade-review-attribution` 与 T-7）
