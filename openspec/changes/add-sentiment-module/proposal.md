## Why

`product-overview.md` §4.2/§5.1.3 将「情绪面」列为三维分析框架的第三维（价值面、技术面均已交付，见 `service/value/`、`service/tech/`），但仓库目前**零情绪面能力**：无数据源适配、无 `service/sentiment/`、`DualTrackReport` 只融合价值+技术两维。`roadmap-todo.md` PO-06（P1）明确要求「融资融券、涨跌停、恐慌贪婪等；须与技术+价值联合解读」。

MRD 对情绪面有一条**硬约束**（§5.1.3 缓解策略）：「情绪过热/过冷可持续较久（情绪钝化），单独使用易被打脸……**强制**在报告中标注：须结合技术面反转确认+价值面底价支撑；**禁止单独作为买卖唯一依据**」。这意味着情绪面不是一个可以独立交付、独立呈现的报告，其唯一合法的呈现形态是「与价值+技术联合」。这是本 change 需要优先解决的架构问题，而不是先接数据源。

「情绪面（整模块）」在 roadmap 中标注为**整模块级别工作量**（融资融券 + 涨跌停 + 恐慌贪婪 + 龙虎榜 + 社媒文本挖掘等），若一次性覆盖 MRD §5.1.3 列出的全部方法论范围，change 会过大、难以在合理周期交付且难以验收。因此本 change 明确收敛 V1 范围为 1-2 个最核心、数据可得性最高的指标，其余方法论项留作后续迭代（见 design.md Open Questions）。

## What Changes

- 新增 `service/sentiment/` 情绪面分析子域，仿照 `service/value/analyzer.py`、`service/tech/analyzer.py` 的 Facade 模式，新增 `SentimentAnalyzer`，输出 `SentimentAnalysisResult`（`code`、`market_sentiment_status` 枚举、`market_sentiment_score`、`reasons[]`、`warnings[]`，字段命名对齐 `ValueAnalysisResult`/`TechAnalysisResult` 习惯）
- 新增 `data_provider/sentiment/` 数据源适配，仿照 `data_provider/akshare/`、`data_provider/baostock/` 的 Fetcher 模式，新增市场情绪数据 Fetcher（涨跌停家数、恐慌贪婪代理指数的输入分量）
- 新增 `dao` 持久化：市场级情绪快照表（按交易日聚合，非按股票代码），新增对应 Repo
- 新增 CLI：`python -m apps.cli sync market`（联网拉取当日市场情绪快照并落库）、`python -m apps.cli report sentiment <code>`（严格离线，输出情绪面报告 + 强制免责声明）
- **修改** `DualTrackAnalyzer`/`DualTrackReport`：新增 `sentiment_result: SentimentAnalysisResult | None` 字段，`analyze_offline()` 总是尝试计算情绪面并纳入 `analysis_summary` 的三维联合解读文本；不新增独立的"情绪面单独可脱离价值+技术呈现"入口（`report sentiment` 输出中强制附加"须结合 `report dual` 联合解读"提示，不作为决策唯一依据）
- **V1 范围（仅 2 个核心指标）**：
  1. 涨跌停家数比（市场广度，衡量当日极端情绪的直接信号）
  2. 恐慌贪婪代理指数（复合指标：涨跌停家数比 + 两融余额环比变化 + 换手率分位，0–100 分，自建代理，非官方指数）
- **不包含 V1**（留待后续迭代，见 design.md Open Questions）：个股融资融券余额明细、龙虎榜、认沽认购比、社媒/新闻文本挖掘情绪分析

## Capabilities

### New Capabilities
- `sentiment-analyzer`：`SentimentAnalyzer.analyze(code)` / `analyze_offline(code)`，输出 `SentimentAnalysisResult`（确定性计算，零 LLM）
- `sentiment-data-provider`：情绪面市场数据采集（涨跌停家数、恐慌贪婪代理指数输入分量），`MarketSentimentProvider` Facade + AKShare Fetcher + 市场级 dao 持久化
- `cli-sync-market`：`sync market` 子命令，联网拉取市场情绪快照并落库
- `cli-report-sentiment`：`report sentiment <code>` 子命令，严格离线，强制携带"须联合解读"免责声明

### Modified Capabilities
- `dual-track-analyzer`：`DualTrackReport` 新增 `sentiment_result` 字段；`analyze_offline()` 新增情绪面计算与三维联合解读文本，`analyze()`（联网版）同步新增（保持两方法字段对等，行为不因此改变既有 `combined_signal` 数值融合逻辑）

## Impact

- **新增文件**：
  - `src/service/sentiment/analyzer.py`、`src/service/sentiment/scorer.py`、`src/service/sentiment/models/sentiment_result.py`
  - `src/data_provider/sentiment/akshare_sentiment_fetcher.py`、`src/data_provider/sentiment/provider.py`
  - `src/dao/market_sentiment_repo.py`
  - `test/service/sentiment/`、`test/data_provider/sentiment/`、`test/apps/test_cli_sync_market.py`、`test/apps/test_cli_report_sentiment.py`
- **修改文件**：
  - `src/dao/models.py`：新增 `MarketSentimentSnapshot` ORM
  - `src/service/dual_track/analyzer.py`、`src/service/dual_track/models/report.py`：新增 `sentiment_result` 字段与联合解读文本
  - `src/apps/cli.py`、`src/apps/formatters.py`：新增 `sync market`、`report sentiment` 子命令与格式化函数
  - `docs/dev/engineering-conventions.md` §3.2：`service` 子域表补充 `service/sentiment/`
- **依赖**：无强制前置 change；不依赖 `add-llm-narrative-core`（情绪面结论全部为确定性计算 + 规则化联合解读文本，不调用 LLM）
- **文档**：`docs/mrd/product-overview.md` §5.1.3/§7（PO-06 状态更新）、`docs/mrd/roadmap-todo.md`（新增变更记录、PO-06 状态更新）
