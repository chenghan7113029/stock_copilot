## Why

情绪面目前只有**市场级**视角（涨跌停家数比 + 恐慌贪婪代理指数），个股级只有资金面（PO-12 两融 + 主力资金流）与治理事件面（PO-11）。`roadmap-todo.md` PO-13「龙虎榜情绪信号」仍是空缺：现有维度无法回答「谁是这波的买家——机构还是游资、上榜理由是什么、净买额多大」，而这类信息恰是市场级情绪指标结构上给不出的个股级证据。数据可得性已确认：`tushare-permission-scan.md` §4.1 实测 `top_list` 与 `top_inst` 在 2000 积分档可用，无需额外开通。

## What Changes

- 新增 `src/service/toplist/`：`TopListAnalyzer`（纯确定性规则，零 LLM），输出 `TopListResult`（近 90 日上榜次数、最近上榜日与净买额、机构席位净买、上榜理由分类、活跃度分级、`reasons`/`warnings`）
- 新增 `src/data_provider/toplist/`：`TopListProvider` + `TushareTopListFetcher`，适配市场级每日接口 `top_list`（必选 `trade_date`）与 `top_inst`（机构席位，可降级），并维护**交易日覆盖水位**（区分「未上榜」与「未拉取」）
- 新增 `dao`：`stock_top_list`、`stock_top_inst`、`top_list_sync_marker` 三张表 + Repo（upsert / 按票查询 / 覆盖水位查询）
- 新增 CLI：`report toplist <code>`（严格离线，独立「龙虎榜/席位」区块，文本固定附「观察维度，不构成买卖建议」）
- **修改** `sync <code>`：在既有价值/K线/筹码/资金面/治理事件之后，追加「尚未覆盖的最近交易日」全市场龙虎榜拉取（按水位跳过已完成交易日，失败降级不阻断）
- **修改** `sync market`：回填最近 N 个交易日（默认 20）龙虎榜与机构席位，作为首次建库与增量补齐入口
- **修改** `DualTrackAnalyzer`/`DualTrackReport`：新增 `top_list_result` 字段；`report dual`/`report dashboard` 追加「龙虎榜/席位」独立区块（不参与 `signal_score`/`combined_signal` 融合）
- **明确不做**（V1 边界）：不注入 LLM ContextPack / grounding / `report briefing`；不做席位名称的游资身份标注（需外部名录，另立 change）；不做市场级「当日上榜家数」聚合指标
- 修正 `roadmap-todo.md` PO-13 状态与 `tushare-permission-scan.md` 的 `top_inst` 积分口径差异（官方文档 5000 vs 本项目实测 2000，按「可降级」处理）

## Capabilities

### New Capabilities

- `top-list-data-provider`：龙虎榜（`top_list` + `top_inst`）采集、交易日覆盖水位与本地持久化，严格离线可读
- `top-list-analyzer`：`TopListAnalyzer.analyze(code)` / `analyze_offline(code)`，确定性规则输出 `TopListResult`（上榜频次、净买额、机构席位、理由分类、活跃度）
- `cli-report-toplist`：`report toplist <code>` 子命令与 dual/dashboard 的「龙虎榜/席位」区块

### Modified Capabilities

- `cli-sync`：`sync <code>` 追加「未覆盖最近交易日」全市场龙虎榜同步（新增 requirement，不改既有价值快照/K线/筹码/资金面/事件步骤）
- `cli-sync-market`：`sync market` 追加龙虎榜回填（新增 requirement，不改既有情绪快照与北向资金行为）
- `dual-track-analyzer`：`DualTrackReport` 新增 `top_list_result` 字段与编排（新增 requirement，不改 `SignalFusion.fuse()` 与既有字段）

## Impact

- **新增文件**
  - `src/service/toplist/analyzer.py`、`src/service/toplist/rules.py`、`src/service/toplist/models/top_list_result.py`
  - `src/data_provider/toplist/tushare_top_list_fetcher.py`、`src/data_provider/toplist/provider.py`
  - `src/dao/top_list_repo.py`
  - `test/service/toplist/`、`test/data_provider/toplist/`、`test/dao/test_top_list_repo.py`、`test/apps/test_cli_report_toplist.py`
- **修改文件**
  - `src/dao/models.py`：新增 `StockTopList`、`StockTopInst`、`TopListSyncMarker` ORM
  - `src/service/dual_track/analyzer.py`、`src/service/dual_track/models/report.py`：`top_list_result` 字段与编排
  - `src/apps/cli.py`：`sync`/`sync market` 追加拉取、新增 `report toplist` 子命令与注册表
  - `src/apps/formatters.py`：新增 `format_top_list_report`，扩展 `format_dual_report`/`format_dashboard_report`
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/toplist/`
- **文档**
  - `docs/mrd/roadmap-todo.md`：PO-13 标记实现 + 变更记录
  - `docs/mrd/product-overview.md`：§5.1.3 / §7 情绪面补充「龙虎榜/席位」维度
  - `docs/mrd/tushare-permission-scan.md`：`top_inst` 积分口径与降级说明
  - `docs/mrd/features/data-source-migration.md`（若新增契约测试工件则同步）
- **依赖与风险**：无强制前置 change；`top_list` 必须传 `trade_date`（市场级日接口，故按交易日循环拉取，单次最多 10000 行）；`top_inst` 官方最低 5000 积分、本项目实测 2000 可用，权限不足时 MUST 降级为「仅 `top_list` 净买额」，不得阻断分析
- **形态**：不引入 LLM，不改变 `signal_score`、`combined_signal`、`value_rating` 的任何数值路径
