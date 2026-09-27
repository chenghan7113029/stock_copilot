## Why

三维分析框架里，价值面、技术面、情绪面均已落地，但 `product-overview.md` §4.3「待补充信息面」中「公司治理与重大事件（减持、回购、诉讼）」「流动性与资金面（北向、板块轮动）」仍是空白（`roadmap-todo.md` PO-11，P2）。个股的减持/回购/解禁/质押/大宗是**可结构化、确定性可判**的高风险事件信号，北向资金是 A 股重要的边际流动性别——这些数据 `tushare-permission-scan.md` §4.1 已实测在 2000 积分档全部可用，且都属于「代码能算」的确定性范畴，无需 LLM。本 change 把它们收敛为一个「治理/事件面」维度，作为独立展示区块（不参与 `signal_score`），与筹码分布、资金面同范式。

## What Changes

- 新增 `service/event/` 事件面子域，新增 `EventAnalyzer`，输出 `EventResult`（确定性风险 flag，零 LLM）
- 新增 `data_provider` 适配 5 个治理事件接口（`stk_holdertrade` 增减持、`repurchase` 回购、`share_float` 解禁、`pledge_stat` 质押、`block_trade` 大宗）+ 1 个市场级流动性接口（`moneyflow_hsgt` 北向资金），复用 Router 能力链 + 离线缓存降级模式
- 新增 `dao` 持久化：5 张按 `(code, trade_date/ann_date)` 分区的治理事件表 + 1 张市场级北向资金日度表 + 对应 Repo
- 新增 CLI：`report events <code>`（严格离线，独立「治理/事件面」区块）
- **修改** `sync <code>`：追加拉取该股治理事件（失败降级，不阻断整次 sync）
- **修改** `DualTrackAnalyzer`/`DualTrackReport`：新增 `event_result: EventResult | None` 字段；`report dual`/`report dashboard` 追加「治理/事件面」区块（独立展示，不参与 `combined_signal` 融合）

## Capabilities

### New Capabilities
- `governance-event-data-provider`：治理事件（减持/回购/解禁/质押/大宗）与北向资金的数据采集与持久化，`EventProvider` Facade + Tushare Fetcher + dao 持久化，严格离线可读
- `governance-event-analyzer`：`EventAnalyzer.analyze(code)` / `analyze_offline(code)`，输出 `EventResult`（确定性风险 flag：近 90 日净减持、回购进行中、未来 30 日解禁、质押比例、大宗折价、北向近 5 日净流入）
- `cli-report-events`：`report events <code>` 子命令（严格离线）+ 治理/事件面区块在 `report dual`/`report dashboard` 的展示

### Modified Capabilities
- `cli-sync`：`sync <code>` 追加治理事件同步（新增 requirement，不改变既有步骤）
- `dual-track-analyzer`：`DualTrackReport` 新增 `event_result` 字段；`analyze()`/`analyze_offline()` 追加 `EventAnalyzer` 编排（新增 requirement，不改变既有融合）

## Impact

- **新增文件**：
  - `src/service/event/analyzer.py`、`src/service/event/rules.py`、`src/service/event/models/event_result.py`
  - `src/data_provider/event/`（tushare fetcher + provider）
  - `src/dao/event_repo.py`（或按接口拆分的多个 Repo）
  - `test/service/event/`、`test/data_provider/event/`、`test/dao/`、`test/apps/test_cli_report_events.py`
- **修改文件**：
  - `src/dao/models.py`：新增 `HolderTrade`、`Repurchase`、`ShareFloat`、`PledgeStat`、`BlockTrade`、`NorthboundFlow` ORM
  - `src/service/dual_track/analyzer.py`、`src/service/dual_track/models/report.py`：新增 `event_result` 字段与编排
  - `src/apps/cli.py`、`src/apps/formatters.py`：`sync <code>` 追加拉取、新增 `report events` 子命令、dual/dashboard 格式化追加治理/事件面区块
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/event/`
- **依赖**：无强制前置 change；复用 `data_provider/router.py` 与 `ChipDistributionProvider` 的降级模式；不依赖 LLM
- **文档**：`docs/mrd/roadmap-todo.md`（PO-11 状态更新）、`docs/mrd/product-overview.md` §4.3/§7（待补充信息面勾选治理 + 流动性）
