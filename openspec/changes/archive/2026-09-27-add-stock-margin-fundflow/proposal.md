## Why

情绪面 V1（`add-sentiment-module`）已交付**市场级**快照（涨跌停家数比 + 恐慌贪婪代理指数），但 `roadmap-todo.md` PO-12（P2）明确的「个股融资融券余额」仍缺失：现有 `margin` 只取沪深合计的环比变化，无法回答「某只个股的杠杆资金在加仓还是去杠杆、主力在吸筹还是派发」。`tushare-permission-scan.md` §4.1 已实测 `margin_detail`（个股两融明细）与 `moneyflow`（个股主力资金流）在 2000 积分档可用，数据可得性无阻塞。二者同属「个股级资金面」，可一次补齐，作为独立展示维度（不参与 `signal_score`，与筹码分布 F-17 同范式）。

## What Changes

- 新增 `service/fundflow/` 资金面子域，仿照 `service/value/`、`service/tech/` 的 Facade 模式，新增 `FundFlowAnalyzer`，输出 `FundFlowResult`（确定性计算，零 LLM）
- 新增 `data_provider` 适配 `margin_detail` + `moneyflow`，仿照 `ChipDistributionProvider` 的「Router 能力链 + 离线缓存降级」模式
- 新增 `dao` 持久化：`stock_margin_detail`、`stock_moneyflow` 两张按 `(code, trade_date)` 分区的表 + 对应 Repo
- 新增 CLI：`report fundflow <code>`（严格离线，独立「个股资金面」区块）
- **修改** `sync <code>`：在价值快照 + K 线 + 筹码分布之后，追加拉取个股两融 + 资金流（失败走缓存降级，不阻断整次 sync）
- **修改** `DualTrackAnalyzer`/`DualTrackReport`：新增 `fund_flow_result: FundFlowResult | None` 字段；`report dual`/`report dashboard` 追加「个股资金面」区块（独立展示，不参与 `combined_signal` 数值融合）

## Capabilities

### New Capabilities
- `fund-flow-data-provider`：个股两融（`margin_detail`）+ 主力资金流（`moneyflow`）数据采集与持久化，`FundFlowProvider` Facade + Tushare Fetcher + dao 持久化，严格离线可读
- `fund-flow-analyzer`：`FundFlowAnalyzer.analyze(code)` / `analyze_offline(code)`，输出 `FundFlowResult`（确定性规则：两融余额近 5 日变化、融券余额突增、主力资金近 5 日净流入）
- `cli-report-fundflow`：`report fundflow <code>` 子命令（严格离线）+ 个股资金面区块在 `report dual`/`report dashboard` 的展示

### Modified Capabilities
- `cli-sync`：`sync <code>` 追加个股两融 + 主力资金流同步（新增 requirement，不改变既有价值快照/K 线步骤）
- `dual-track-analyzer`：`DualTrackReport` 新增 `fund_flow_result` 字段；`analyze()`/`analyze_offline()` 追加 `FundFlowAnalyzer` 编排（新增 requirement，不改变既有 `combined_signal`/`value_rating` 融合）

## Impact

- **新增文件**：
  - `src/service/fundflow/analyzer.py`、`src/service/fundflow/rules.py`、`src/service/fundflow/models/fund_flow_result.py`
  - `src/data_provider/fundflow/`（tushare fetcher + provider）
  - `src/dao/fund_flow_repo.py`（或 `stock_margin_repo.py` + `stock_moneyflow_repo.py`）
  - `test/service/fundflow/`、`test/data_provider/fundflow/`、`test/dao/`、`test/apps/test_cli_report_fundflow.py`
- **修改文件**：
  - `src/dao/models.py`：新增 `StockMarginDetail`、`StockMoneyFlow` ORM
  - `src/service/dual_track/analyzer.py`、`src/service/dual_track/models/report.py`：新增 `fund_flow_result` 字段与编排
  - `src/apps/cli.py`、`src/apps/formatters.py`：`sync <code>` 追加拉取、新增 `report fundflow` 子命令、dual/dashboard 格式化追加资金面区块
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/fundflow/`
- **依赖**：无强制前置 change；复用 `data_provider/router.py`（`fetchers_with_method`）、`ChipDistributionProvider` 的降级模式；不依赖 LLM（纯确定性）
- **文档**：`docs/mrd/roadmap-todo.md`（PO-12 状态更新）、`docs/mrd/product-overview.md` §5.1.3/§7（情绪面补充个股资金面维度）
