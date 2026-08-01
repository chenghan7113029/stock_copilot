## 1. 数据源可行性验证（实现前置）

- [x] 1.1 用临时脚本验证候选 AKShare 接口是否存在与可用：涨跌停家数（候选 `stock_market_activity_legu` 或等价接口）、两融余额（候选 `stock_margin_underlying_info_szse`/`stock_margin_sse`）、全市场成交额/换手率
- [x] 1.2 记录实际可用接口名、返回字段与调用频率限制到 `docs/design/` 或本 change 的实现笔记中，若候选接口不可用则在本任务中确定替代接口
- [x] 1.3 若关键接口（涨跌停家数）完全不可用，回到 design.md 重新评估 V1 范围（阻断性任务，须先完成再继续）

## 2. 数据持久化

- [x] 2.1 `src/dao/models.py` 新增 `MarketSentimentSnapshot` ORM：`trade_date`（主键）、`limit_up_count`、`limit_down_count`、`up_count`、`down_count`、`margin_balance_change_pct`（可空）、`turnover_percentile`（可空）、`fear_greed_index`（可空）、`fetched_at`
- [x] 2.2 新建 `src/dao/market_sentiment_repo.py`：`upsert(snapshot_data)`、`get_latest() -> MarketSentimentSnapshot | None`、`get_by_date(trade_date)`
- [x] 2.3 单测 `test/dao/test_market_sentiment_repo.py`：覆盖 upsert 新增/更新、`get_latest` 空表与多条记录场景

## 3. 情绪面数据源适配（data_provider/sentiment/）

- [x] 3.1 新建 `src/data_provider/sentiment/akshare_sentiment_fetcher.py`：`fetch_market_breadth() -> FetchResult`（涨跌停家数）、`fetch_margin_change() -> FetchResult`（两融余额环比，可选分量）、`fetch_turnover_percentile() -> FetchResult`（换手率分位，可选分量），复用 `data_provider/base.py` 的 `retry_with_backoff` 与异常处理模式
- [x] 3.2 新建 `src/data_provider/sentiment/provider.py`：`MarketSentimentProvider`，`fetch_and_persist_today()`（联网+落库）、`get_latest_offline()`（纯离线读取，不联网）
- [x] 3.3 单测 `test/data_provider/sentiment/test_akshare_sentiment_fetcher.py`：mock AKShare 返回值，覆盖成功、单分量失败降级、全部失败三种场景
- [x] 3.4 单测 `test/data_provider/sentiment/test_provider.py`：覆盖 `fetch_and_persist_today` 落库正确性、`get_latest_offline` 离线读取不触发网络调用（mock 断言未调用 fetcher）

## 4. SentimentAnalyzer

- [x] 4.1 新建 `src/service/sentiment/models/sentiment_result.py`：`SentimentStatus` 枚举（极度恐慌/恐慌/中性/贪婪/极度贪婪）、`SentimentAnalysisResult` dataclass（`code`、`market_sentiment_status`、`market_sentiment_score`、`limit_updown_ratio`、`reasons: list[str]`、`warnings: list[str]`、`data_timestamp`）
- [x] 4.2 新建 `src/service/sentiment/scorer.py`：涨跌停家数比计算（含除零保护）、恐慌贪婪代理指数加权计算（含分量缺失降级重新归一化逻辑）、指数到 `SentimentStatus` 枚举的分档映射
- [x] 4.3 新建 `src/service/sentiment/analyzer.py`：`SentimentAnalyzer`，`analyze(code)`（联网，内部触发 `MarketSentimentProvider.fetch_and_persist_today()` 后计算）、`analyze_offline(code)`（纯离线，读取 `get_latest_offline()` 后计算，无快照返回 `None`）
- [x] 4.4 单测 `test/service/sentiment/test_scorer.py`：覆盖涨跌停比正常计算、除零降级、复合指数全分量/部分分量/全缺失三种场景、分档映射边界值
- [x] 4.5 单测 `test/service/sentiment/test_analyzer.py`：覆盖 `analyze_offline` 成功、无快照返回 `None` 两种场景

## 5. DualTrackAnalyzer 集成（三维联合解读）

- [x] 5.1 `src/service/dual_track/models/report.py`：`DualTrackReport` 新增 `sentiment_result: SentimentAnalysisResult | None = None` 字段
- [x] 5.2 `src/service/dual_track/analyzer.py`：`analyze_offline()` 与 `analyze()` 均新增 `SentimentAnalyzer` 编排调用；`build_analysis_summary()` 扩展情绪面段落生成逻辑（成功/缺失两种文案分支、极端情绪+对应价值/技术状态的联合解读规则）
- [x] 5.3 单测 `test/service/dual_track/test_analyzer.py`：新增覆盖 `sentiment_result` 计算成功、情绪面缺失时的显式降级文案、`combined_signal`/`value_rating` 不受影响（回归）三种场景
- [x] 5.4 单测 `test/service/dual_track/test_signal_fusion.py`：确认 `SignalFusion.fuse()` 无需改动即可通过既有测试（回归验证决策 3 的 Non-Goal）

## 6. CLI：`sync market` 与 `report sentiment`

- [x] 6.1 `src/apps/cli.py`：`build_parser()` 新增 `sync market` 子命令（不接受 `<code>` 参数）与 `run_sync_market()`
- [x] 6.2 `src/apps/cli.py`：`build_parser()` 新增 `report sentiment <code> [--json] [--output] [--quiet]` 子命令与 `run_report_sentiment()`（严格离线）
- [x] 6.3 `src/apps/formatters.py`：新增 `format_sentiment_report(result, as_json)`，文本模式固定追加联合解读免责声明；`--json` 模式包含 `disclaimer` 字段
- [x] 6.4 `src/apps/formatters.py`：扩展 `format_dual_report`/双轨文本格式化，展示 `sentiment_result` 概要（若存在）
- [x] 6.5 单测 `test/apps/test_cli_sync_market.py`：覆盖成功同步、数据源失败错误提示
- [x] 6.6 单测 `test/apps/test_cli_report_sentiment.py`：覆盖成功输出含免责声明、`--json` 含 `disclaimer` 字段、无缓存报错三种场景

## 7. 端到端验证

- [x] 7.1 `python -m apps.cli sync market` 后运行 `python -m apps.cli report sentiment 600519`，人工核对涨跌停家数比、恐慌贪婪指数是否为合理数值（与当日实际市场情况粗略对照）
- [x] 7.2 运行 `python -m apps.cli report dual 600519`，确认输出包含情绪面联合解读段落
- [x] 7.3 清空 `market_sentiment_snapshot` 表后重跑 `report dual 600519`，确认显式降级文案正确出现且不影响 `combined_signal`
- [x] 7.4 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 8. 文档

- [x] 8.1 更新 `docs/dev/engineering-conventions.md` §3.2：`service` 子域表新增 `service/sentiment/` 行
- [x] 8.2 更新 `docs/mrd/product-overview.md` §5.1.3/§7/§8.1：PO-06 状态更新为「V1 已实现：涨跌停家数比 + 恐慌贪婪代理指数，个股融资余额/龙虎榜/社媒文本挖掘待后续迭代」；§8.1 验收准则勾选"情绪指标出现时，报告内必须含与技术/价值的联合解读段落"
- [x] 8.3 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，PO-06 状态更新，补充遗留子项（个股融资余额、龙虎榜、社媒文本挖掘）为新的待办 ID

## 9. 归档

- [ ] 9.1 确认 `tasks.md` 全部任务完成
- [ ] 9.2 运行 `openspec archive add-sentiment-module`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`
