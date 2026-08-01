## 0. 前置依赖确认（阻断性 Gate）

- [x] 0.1 确认 `add-trade-review-attribution` 至少已完成 §1（`TradeRecord` 数据模型 + `trade_record_repo`）并合入主干；若未完成，本 change 暂停实现，仅保留设计文档
- [x] 0.2 冻结 `trade_record_repo.find_open_positions()` 的方法签名与返回结构，作为本 change 的输入契约基线，避免后续两个 change 并行演进导致接口不一致

## 1. PortfolioAnalyzer 数据模型

- [x] 1.1 新建 `src/service/portfolio/models/portfolio_result.py`：`PortfolioAnalysisResult`（`total_value`、`positions: list[PositionSummary]`、`single_stock_weight: dict[str, float]`、`top_n_concentration: dict[int, float]`、`industry_exposure: dict[str, float]`、`warnings: list[str]`）；`PositionSummary`（`code`、`quantity`、`market_value`、`weight`、`industry`、`price_as_of`）

## 2. 持仓集中度计算

- [x] 2.1 新建 `src/service/portfolio/analyzer.py`：`PortfolioAnalyzer.analyze_offline() -> PortfolioAnalysisResult`，调用 `trade_record_repo.find_open_positions()` + 本地价值快照最新价格计算各持仓市值
- [x] 2.2 实现 `single_stock_weight`、`top_n_concentration(n)` 计算，空组合安全返回
- [x] 2.3 实现价格时效标注（`price_as_of` + 过期 warning，阈值模块内常量，默认 7 天）
- [x] 2.4 单测 `test/service/portfolio/test_analyzer.py`：覆盖多持仓占比计算、前 N 大占比计算、空组合、价格过期提示

## 3. 行业暴露度粗估

- [x] 3.1 `src/service/portfolio/analyzer.py` 新增 `industry_exposure(code) -> float | None`：按 `stock_snapshots.industry` 字符串分组计算目标行业在组合中的现有占比
- [x] 3.2 目标股票无本地快照/`industry` 为空时返回 `None` 并记录 warning
- [x] 3.3 结果固定携带"行业分类为原始文本粗匹配，非标准化分类"局限提示
- [x] 3.4 单测 `test/service/portfolio/test_analyzer.py`：覆盖有暴露度、无行业信息两种场景

## 4. 加仓边际影响模拟

- [x] 4.1 `PortfolioAnalyzer.simulate_add(code, quantity) -> PortfolioAnalysisResult`：不写入任何 `TradeRecord`，纯内存重新计算加仓后的占比与行业暴露度
- [x] 4.2 单测 `test/service/portfolio/test_analyzer.py`：覆盖模拟加仓后占比正确上升、且断言未调用任何写库方法（mock repo 断言）

## 5. CLI `report portfolio`

- [x] 5.1 `src/apps/cli.py`：新增 `report portfolio [--code <code>] [--add-quantity <n>] [--json] [--output] [--quiet]` 子命令
- [x] 5.2 `src/apps/formatters.py`：新增 `format_portfolio_report(result, as_json)`，模拟场景固定输出"以下为模拟计算，不代表任何实际交易操作"提示
- [x] 5.3 单测 `test/apps/test_cli_report_portfolio.py`：覆盖组合整体概览、指定标的边际模拟、无持仓报错三种场景

## 6. 端到端验证

- [x] 6.1 基于 `add-trade-review-attribution` 录入的模拟交易记录，运行 `report portfolio`，人工核对占比计算与行业分组正确
- [x] 6.2 运行 `report portfolio --code <目标股票> --add-quantity <n>`，核对模拟前后占比变化与固定提示均正确
- [x] 6.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 7. 文档

- [x] 7.1 更新 `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/portfolio/`
- [x] 7.2 更新 `docs/mrd/product-overview.md` §4.3/§7：PO-10 状态更新，明确标注"持仓集中度+行业暴露度粗估已实现，协方差/组合优化类方法明确排除"
- [x] 7.3 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，交叉引用 `add-trade-review-attribution`（持仓数据来源）与 T-7（行业标准化，影响未来精度提升）

## 8. 归档

- [ ] 8.1 确认 `tasks.md` 全部任务完成
- [ ] 8.2 运行 `openspec archive add-portfolio-correlation`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`
