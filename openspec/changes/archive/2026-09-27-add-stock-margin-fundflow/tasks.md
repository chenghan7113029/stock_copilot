## 1. 数据源可行性验证（实现前置）

- [x] 1.1 用临时脚本（`scripts/` 或一次性 `python -c`）验证 Tushare `margin_detail`（`ts_code` + `trade_date` 参数）与 `moneyflow` 接口在 2000 积分 Token 下可用，记录实际字段名与单位（`rzye`/`rqye`/`rzrqye`/`rzmre`/`rzche`/`rqyl`/`rqmcl`；`net_mf_amount`/`buy_elg_amount`/`buy_lg_amount` 等）
- [x] 1.2 将验证结果（接口名、字段、单位、是否需 `trade_date=最近交易日`）记录到 `docs/design/data-source-field-matrix.md` 或本 change 实现笔记
- [x] 1.3 若 `margin_detail` 或 `moneyflow` 不可用，回到 design.md 重新评估范围（阻断性任务）

## 2. 数据持久化（dao）

- [x] 2.1 `src/dao/models.py` 新增 `StockMarginDetail` ORM：`code`、`trade_date`、`rzye`、`rqye`、`rzrqye`、`rzmre`、`rzche`、`rqyl`、`rqmcl`、`fetched_at`，主键/索引 `(code, trade_date)`
- [x] 2.2 `src/dao/models.py` 新增 `StockMoneyFlow` ORM：`code`、`trade_date`、`net_mf_amount`、`buy_elg_amount`、`sell_elg_amount`、`buy_lg_amount`、`sell_lg_amount`、`fetched_at`，主键/索引 `(code, trade_date)`
- [x] 2.3 新建 `src/dao/fund_flow_repo.py`（或 `stock_margin_repo.py` + `stock_moneyflow_repo.py`）：`upsert_batch(records)`、`query_latest(code)`、`query_range(code, days)`
- [x] 2.4 单测 `test/dao/test_fund_flow_repo.py`：覆盖 upsert 新增/更新、`query_latest` 空表与多条、`query_range` 按交易日过滤

## 3. 数据源适配（data_provider/fundflow/）

- [x] 3.1 新建 `src/data_provider/fundflow/tushare_fundflow_fetcher.py`：`fetch_margin_detail(code) -> pd.DataFrame`、`fetch_moneyflow(code) -> pd.DataFrame`，复用 `retry_with_backoff` 与异常处理模式
- [x] 3.2 新建 `src/data_provider/fundflow/provider.py`：`FundFlowProvider`，`from_config(config, repos)` 经 `DataFetcherRouter.fetchers_with_method(...)` 收集 fetcher，`get_latest(code, offline=False, on_progress=None)`（联网 + 缓存降级）、`get_latest_offline(code)`
- [x] 3.3 单测 `test/data_provider/fundflow/test_provider.py`：mock Tushare 返回值，覆盖成功、单接口失败降级、无缓存返回 None 三种场景

## 4. FundFlowAnalyzer

- [x] 4.1 新建 `src/service/fundflow/models/fund_flow_result.py`：`LeverageDirection` 枚举（加杠杆/去杠杆/平稳）、`FundFlowResult` dataclass（`code`、`margin_balance_change_pct`、`short_balance_change_pct`、`main_net_inflow_5d`、`leverage_direction`、`reasons`、`warnings`、`data_timestamp`）
- [x] 4.2 新建 `src/service/fundflow/rules.py`：两融/融券近 5 日变化率计算（含除零与数据不足保护）、主力资金近 5 日净流入累计、融券突增阈值判断
- [x] 4.3 新建 `src/service/fundflow/analyzer.py`：`FundFlowAnalyzer`，`analyze(code)`（联网）、`analyze_offline(code)`（严格离线，无缓存返回 `None`）
- [x] 4.4 单测 `test/service/fundflow/test_rules.py`：覆盖变化率正常/除零/数据不足、主力净流入累计、融券突增阈值边界
- [x] 4.5 单测 `test/service/fundflow/test_analyzer.py`：覆盖 `analyze_offline` 成功、无缓存返回 `None` 两种场景

## 5. DualTrackAnalyzer 集成

- [x] 5.1 `src/service/dual_track/models/report.py`：`DualTrackReport` 新增 `fund_flow_result: FundFlowResult | None = None`
- [x] 5.2 `src/service/dual_track/analyzer.py`：`analyze()` 与 `analyze_offline()` 追加 `FundFlowAnalyzer` 编排调用；缺失时 `fund_flow_result=None` 并记 warning
- [x] 5.3 单测 `test/service/dual_track/test_analyzer.py`：新增资金面成功、资金面缺失显式降级、`combined_signal`/`value_rating` 不受影响（回归）三种场景

## 6. CLI：sync 追加 + `report fundflow`

- [x] 6.1 `src/apps/cli.py`：`run_sync()` 在筹码分布提交后追加 `FundFlowProvider.get_latest(code, offline=False)` 并独立 commit；失败仅打印降级警告
- [x] 6.2 `src/apps/cli.py`：`build_parser()` 新增 `report fundflow <code> [--json] [--output] [--quiet]` 子命令与 `run_report_fundflow()`
- [x] 6.3 `src/apps/formatters.py`：新增 `format_fund_flow_report(result, as_json)`，文本模式固定追加「资金面数据为观察维度，不构成买卖建议」提示
- [x] 6.4 `src/apps/formatters.py`：扩展 `format_dual_report`/`format_dashboard_report`，展示「个股资金面」区块（若 `fund_flow_result` 非空）
- [x] 6.5 单测 `test/apps/test_cli_report_fundflow.py`：覆盖成功输出、`--json`、无缓存报错三种场景
- [x] 6.6 单测 `test/apps/test_cli_sync.py`：覆盖 sync 追加资金面成功、资金面接口失败不阻断 sync（退出码 0）

## 7. 端到端验证

- [x] 7.1 `python -m apps.cli sync 600519` 后 `python -m apps.cli report fundflow 600519`，人工核对两融余额变化、主力净流入是否为合理数值
- [x] 7.2 `python -m apps.cli report dual 600519` 与 `report dashboard 600519`，确认包含「个股资金面」区块且 `combined_signal` 未变
- [x] 7.3 清空资金面缓存后重跑 `report dual 600519`，确认资金面显式降级且不影响 `combined_signal`
- [x] 7.4 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 8. 文档

- [x] 8.1 更新 `docs/dev/engineering-conventions.md` §3.2：`service` 子域表新增 `service/fundflow/` 行
- [x] 8.2 更新 `docs/mrd/roadmap-todo.md`：PO-12 状态更新为已实现，新增变更记录
- [x] 8.3 更新 `docs/mrd/product-overview.md` §5.1.3/§7/§8.1：情绪面补充「个股资金面（两融 + 主力资金流）」维度说明

## 9. 归档

- [x] 9.1 确认 `tasks.md` 全部任务完成，`pytest test/ -q -m "not network"` 门禁通过（保留命令输出）
- [x] 9.2 运行 `openspec archive add-stock-margin-fundflow`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`，并合并设计要点到 `docs/design/` 与 `docs/mrd/`
