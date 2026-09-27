## 1. 数据源可行性验证（实现前置）

- [x] 1.1 用临时脚本逐接口验证 Tushare 2000 积分 Token 下 `stk_holdertrade`、`repurchase`、`share_float`、`pledge_stat`、`block_trade`、`moneyflow_hsgt` 可用性与实际字段名/单位（`change_vol`/`change_ratio`、`proc`/`vol`/`amount`、`float_date`/`float_share`/`float_ratio`、`pledge_ratio`、`price`/`vol`/`amount`、`north_money`/`south_money` 等）
- [x] 1.2 将验证结果记录到 `docs/design/data-source-field-matrix.md` 或本 change 实现笔记
- [x] 1.3 若任一接口不可用，回到 design.md 评估是否剔除该接口（阻断性任务）

## 2. 数据持久化（dao）

- [x] 2.1 `src/dao/models.py` 新增 5 张治理事件 ORM：`HolderTrade`、`Repurchase`、`ShareFloat`、`PledgeStat`、`BlockTrade`（主键/索引 `(code, 事件日期)`，字段见 design.md 决策 1）
- [x] 2.2 `src/dao/models.py` 新增市场级 `NorthboundFlow` ORM（主键 `trade_date`，`north_money`/`south_money`/`fetched_at`）
- [x] 2.3 新建 `src/dao/event_repo.py`（或按接口拆分多个 Repo）：`upsert_batch`、`query_latest(code)`、`query_range(code, days)`、`query_northbound(days)`
- [x] 2.4 单测 `test/dao/test_event_repo.py`：覆盖各表 upsert、`query_latest`、`query_range`、北向 `query_northbound` 过滤

## 3. 数据源适配（data_provider/event/）

- [x] 3.1 新建 `src/data_provider/event/tushare_event_fetcher.py`：`fetch_holder_trade(code)`、`fetch_repurchase(code)`、`fetch_share_float(code)`、`fetch_pledge_stat(code)`、`fetch_block_trade(code)`、`fetch_northbound_flow()`，复用 `retry_with_backoff` 与异常处理
- [x] 3.2 新建 `src/data_provider/event/provider.py`：`EventProvider`，`from_config(config, repos)` 经 `DataFetcherRouter.fetchers_with_method(...)` 收集 fetcher，`sync(code)`（逐接口降级）、`get_latest(code, offline=False)`、`get_latest_offline(code)`、`fetch_northbound_flow()`
- [x] 3.3 单测 `test/data_provider/event/test_provider.py`：mock Tushare 返回值，覆盖全部成功、单接口失败部分成功、无缓存返回空集合三种场景

## 4. EventAnalyzer

- [x] 4.1 新建 `src/service/event/models/event_result.py`：`EventResult` dataclass（`code`、`holder_net_sell_90d`、`repurchase_active`、`upcoming_unlock_30d`、`pledge_ratio`、`block_trade_discount`、`northbound_net_inflow_5d`、`reasons`、`warnings`、`data_timestamp`）
- [x] 4.2 新建 `src/service/event/rules.py`：减持方向聚合、回购进行中判定、未来 30 日解禁占比、质押比例读取、大宗折价、北向近 5 日净流入（阈值均为模块内可调常量）
- [x] 4.3 新建 `src/service/event/analyzer.py`：`EventAnalyzer`，`analyze(code)`（联网）、`analyze_offline(code)`（严格离线，无缓存返回 `None`）
- [x] 4.4 单测 `test/service/event/test_rules.py`：覆盖减持聚合、回购状态、解禁窗口、质押读取、大宗折价、北向累计与数据不足降级
- [x] 4.5 单测 `test/service/event/test_analyzer.py`：覆盖 `analyze_offline` 成功、无缓存返回 `None` 两种场景

## 5. DualTrackAnalyzer 集成

- [x] 5.1 `src/service/dual_track/models/report.py`：`DualTrackReport` 新增 `event_result: EventResult | None = None`
- [x] 5.2 `src/service/dual_track/analyzer.py`：`analyze()` 与 `analyze_offline()` 追加 `EventAnalyzer` 编排调用；缺失时 `event_result=None` 并记 warning
- [x] 5.3 单测 `test/service/dual_track/test_analyzer.py`：新增事件面成功、事件面缺失显式降级、`combined_signal`/`value_rating` 不受影响（回归）三种场景

## 6. CLI：sync 追加 + `report events`

- [x] 6.1 `src/apps/cli.py`：`run_sync()` 在筹码/资金面提交后追加 `EventProvider.sync(code)` 并独立 commit；失败仅打印降级警告
- [x] 6.2 `src/apps/cli.py`：`build_parser()` 新增 `report events <code> [--json] [--output] [--quiet]` 子命令与 `run_report_events()`
- [x] 6.3 `src/apps/formatters.py`：新增 `format_event_report(result, as_json)`，文本模式固定追加「事件面数据为观察维度，不构成买卖建议」提示
- [x] 6.4 `src/apps/formatters.py`：扩展 `format_dual_report`/`format_dashboard_report`，展示「治理/事件面」区块（若 `event_result` 非空）
- [x] 6.5 单测 `test/apps/test_cli_report_events.py`：覆盖成功输出、`--json`、无缓存报错三种场景
- [x] 6.6 单测 `test/apps/test_cli_sync.py`：覆盖 sync 追加治理事件成功、治理接口失败不阻断 sync（退出码 0）

## 7. 端到端验证

- [x] 7.1 `python -m apps.cli sync 600519` 后 `python -m apps.cli report events 600519`，人工核对减持/回购/解禁/质押/大宗/北向是否为合理事实值
- [x] 7.2 `python -m apps.cli report dual 600519` 与 `report dashboard 600519`，确认包含「治理/事件面」区块且 `combined_signal` 未变
- [x] 7.3 清空治理事件缓存后重跑 `report dual 600519`，确认事件面显式降级且不影响 `combined_signal`
- [x] 7.4 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 8. 文档

- [x] 8.1 更新 `docs/dev/engineering-conventions.md` §3.2：`service` 子域表新增 `service/event/` 行
- [x] 8.2 更新 `docs/mrd/roadmap-todo.md`：PO-11 状态更新为「治理 + 流动性已实现，宏观政策事件仍待规划」，新增变更记录
- [x] 8.3 更新 `docs/mrd/product-overview.md` §4.3/§7：待补充信息面勾选治理事件与流动性资金面，宏观政策事件仍列为开放项

## 9. 归档

- [x] 9.1 确认 `tasks.md` 全部任务完成，`pytest test/ -q -m "not network"` 门禁通过（保留命令输出）
- [x] 9.2 运行 `openspec archive add-governance-flow-events`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`，并合并设计要点到 `docs/design/` 与 `docs/mrd/`
