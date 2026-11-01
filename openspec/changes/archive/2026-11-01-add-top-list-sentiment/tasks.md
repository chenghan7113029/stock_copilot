## 1. 数据源可行性与口径验证（前置阻断）

- [x] 1.1 用一次性脚本（`python -c`，不入库）验证 Tushare `top_list(trade_date=<最近交易日>)` 在 2000 积分 Token 下返回非空，记录实际字段、单位（`net_amount`/`l_buy`/`l_sell`/`l_amount` 单位元，`pct_change`/`turnover_rate` 单位 %）与每日行数量级
- [x] 1.2 验证 `top_inst(trade_date=<最近交易日>)` 是否可用；若返回权限错误，记录错误码与实际积分档，并确认「仅 `top_list`」降级路径可在无机构数据时正常出报告（对照 spec `top-list-data-provider` 降级 requirement）
- [x] 1.3 将 1.1/1.2 实测口径写入 `docs/mrd/tushare-permission-scan.md` §4.1（`top_inst` 官方 5000 / 本项目实测 2000 的差异与降级说明）
- [x] 1.4 若 `top_list` 在 2000 积分档不可用 → 停止实现，回到 design.md 重新评估范围（阻断性任务，不得跳过）

## 2. 数据持久化（dao）

- [x] 2.1 Modify `src/dao/models.py`：新增 `StockTopList`（`code, trade_date, reason` 主键；`close/pct_change/turnover_rate/amount/l_sell/l_buy/l_amount/net_amount/net_rate/amount_rate/float_values/fetched_at` 列 + `ix_stock_top_list_code_date` 索引）
- [x] 2.2 Modify `src/dao/models.py`：新增 `StockTopInst`（`code, trade_date, side, exalter` 主键；`buy/buy_rate/sell/sell_rate/net_buy/reason/fetched_at` + `ix_stock_top_inst_code_date` 索引）
- [x] 2.3 Modify `src/dao/models.py`：新增 `TopListSyncMarker`（`trade_date` 主键 + `source` + `fetched_at`）
- [x] 2.4 Create `src/dao/top_list_repo.py`：`StockTopListRepo` / `StockTopInstRepo`（`upsert_batch(later rows overwrite)`、`query_range(code, since_date)`、`count_distinct_trade_dates(code, since_date)`）、`TopListSyncMarkerRepo`（`mark(trade_date, source)`、`has(trade_date)`、`covered_dates(since_date)`）
- [x] 2.5 Create `test/dao/test_top_list_repo.py`：覆盖 upsert 幂等（重复写入不增加行）、同股同日多 `reason` 多行、`query_range` 按窗口过滤、「未上榜 ≠ 未拉取」（无记录 + 无水位 vs 无记录 + 有水位）
- [x] 2.6 验证：`pytest test/dao/test_top_list_repo.py -q` 全部通过后再勾选本组

## 3. 数据源适配（`src/data_provider/toplist/`）

- [x] 3.1 Create `src/data_provider/toplist/tushare_top_list_fetcher.py`：`fetch_top_list(trade_date) -> pd.DataFrame`、`fetch_top_inst(trade_date) -> pd.DataFrame`，复用 `retry_with_backoff` 与 `_to_ts_code` 风格，异常包装为 `DataProviderError`
- [x] 3.2 Create `src/data_provider/toplist/provider.py`：`TopListProvider.from_config(config, repos)`（仅 tushare 启用且有 token 时实例化 fetcher）、`resolve_latest_trade_date()`（`trade_cal` 优先、退化探测 5 个自然日）、`sync_trade_date(trade_date)`（`top_list` 必成、`top_inst` 尽力；空结果不写水位）、`get_offline(code, window_days)`、`covered_dates(since_date)`
- [x] 3.3 Create `test/data_provider/toplist/test_provider.py`：mock Tushare 覆盖成功、空结果不写水位、`top_inst` 权限失败降级、未启用数据源返回 warning、重复 `sync_trade_date` 幂等
- [x] 3.4 验证：`pytest test/data_provider/toplist -q` 全部通过后再勾选本组

## 4. TopListAnalyzer（`src/service/toplist/`）

- [x] 4.1 Create `src/service/toplist/models/top_list_result.py`：`ActiveLevel`（未上榜/偶发/活跃）、`NetAmountLevel`（大额净买入/大额净卖出/中性）、`InstParticipation`（机构买入/机构卖出/无机构席位）枚举 + `TopListResult` dataclass（字段对齐 spec `top-list-analyzer`）
- [x] 4.2 Create `src/service/toplist/rules.py`：模块常量（`WINDOW_DAYS=90`、`ACTIVE_MIN_APPEARANCES=3`、`LARGE_NET_BUY_10K=5000`）+ 纯函数（按 `trade_date` 去重计数、理由关键词分类、净买额分档、机构席位净买判定、覆盖不足告警文本）
- [x] 4.3 Create `src/service/toplist/analyzer.py`：`TopListAnalyzer.from_config(config)`、`analyze(code)`（联网）、`analyze_offline(code) -> TopListResult | None`（严格离线，无缓存返回 `None`）
- [x] 4.4 Create `test/service/toplist/test_rules.py`：同日多条理由只计 1 次、阈值边界（`>=3` 判活跃、`>=5000 万` 判大额）、理由分类、负净买、机构净买正负号
- [x] 4.5 Create `test/service/toplist/test_analyzer.py`：离线成功、无缓存返回 `None`、`top_inst` 缺失时机构字段为 `None` 且 `reasons` 无机构陈述、覆盖不足 warning
- [x] 4.6 验证：`pytest test/service/toplist -q` 全部通过后再勾选本组

## 5. DualTrackAnalyzer 集成

- [x] 5.1 Modify `src/service/dual_track/models/report.py`：`DualTrackReport` 新增 `top_list_result: TopListResult | None = None`
- [x] 5.2 Modify `src/service/dual_track/analyzer.py`：构造参数新增 `top_list_analyzer`，`from_config` 接线；`analyze()` 与 `analyze_offline()` 追加编排（离线无缓存时置 `None` + warning，异常仅记 warning）
- [x] 5.3 Test `test/service/dual_track/test_analyzer.py`：新增「龙虎榜成功」「龙虎榜缺失显式降级」「`combined_signal`/`value_rating` 不受影响（回归）」三个用例
- [x] 5.4 验证：`pytest test/service/dual_track -q` 全部通过后再勾选本组

## 6. CLI（`src/apps/`）

- [x] 6.1 Modify `src/apps/cli.py` `run_sync()`：在治理事件之后追加龙虎榜同步（解析最近交易日 → 已覆盖则跳过 → `top_list` + 尽力 `top_inst` → 独立 `session.commit()`），失败仅 warn 不阻断，并在完成摘要中输出「龙虎榜 OK/已降级」
- [x] 6.2 Modify `src/apps/cli.py` `run_sync_market()`：新增 `--top-list-days`（默认 20）回填逐交易日龙虎榜；`<=0` 跳过并提示
- [x] 6.3 Modify `src/apps/cli.py`：`build_parser()` 新增 `report toplist <code> [--json] [--output] [--quiet]`，实现 `run_report_toplist()` 并在子命令注册表加入 `"toplist"`
- [x] 6.4 Modify `src/apps/formatters.py`：新增 `format_top_list_report(result, as_json)`（文本固定附「龙虎榜为观察维度，不构成买卖建议」）；扩展 `format_dual_report`/`format_dashboard_report` 增加「龙虎榜/席位」区块（新参数默认 `None`，保证既有调用零漂移）
- [x] 6.5 Create `test/apps/test_cli_report_toplist.py`：成功输出、`--json` 字段、无缓存报错（退出码非 0）
- [x] 6.6 Test `test/apps/test_cli_sync.py`：新增「已覆盖事件跳过」「`top_list` 失败不阻断（退出码 0）」用例；`test/apps/test_cli_sync_market.py` 新增「回填 2 日」「`--top-list-days 0` 跳过」用例
- [x] 6.7 验证：`pytest test/apps -q` 全部通过后再勾选本组

## 7. 端到端验证（真实数据，命令与输出留存）

- [x] 7.1 `python -m apps.cli sync market --top-list-days 5`：确认 `top_list_sync_marker` 写入、`stock_top_list` 行数与当日真实榜单一致
- [x] 7.2 `python -m apps.cli sync 600519`：确认走「已覆盖跳过」分支（无重复网络调用）且退出码 0
- [x] 7.3 `python -m apps.cli report toplist <近期上榜股>`：人工核对 `net_amount`、机构净买与该股在东财/同花顺龙虎榜页面一致；`report dashboard`/`report dual` 出现「龙虎榜/席位」区块
- [x] 7.4 清空 `stock_top_inst` 后重跑 `report toplist`：确认机构维度显式降级、无机构结论性文案
- [x] 7.5 门禁：`pytest -q -m "not network"` 全量通过（保留输出）
- [x] 7.6 门禁：`python scripts/compare_migration_baseline.py` 退出码 0（双轨新增字段不得改变既有 baseline JSON；若漂移 MUST 修 formatter 默认路径，不得直接 re-baseline）
- [x] 7.7 若 7.5/7.6 存在失败且需继续，MUST 由 Owner 在对话中显式豁免具体失败项，并在本文件与 PR 记录豁免项与原因（禁止默认放行）

## 8. 文档

- [x] 8.1 Modify `docs/dev/engineering-conventions.md` §3.2：`service` 子域表新增 `service/toplist/` 行，`data_provider` 子域表新增 `data_provider/toplist/`
- [x] 8.2 Modify `docs/mrd/roadmap-todo.md`：PO-13 标为已实现、§8 统计摘要与「变更记录」追加一行
- [x] 8.3 Modify `docs/mrd/product-overview.md`：§5.1.3 / §7 / §8.1 情绪面补充「龙虎榜/席位」维度说明
- [x] 8.4 Modify `docs/mrd/tushare-permission-scan.md`：`top_inst` 积分口径与降级说明（同 1.3）
- [x] 8.5 Modify `docs/user-guide.md`：§1.1 命令表新增 `report toplist`、§1.2「尚未交付」列表移除龙虎榜、附录新增一节龙虎榜用法（含首次建库 `--top-list-days` 建议）
- [x] 8.6 Create `docs/design/top-list-sentiment.md`：合并 design.md 的决策与口径（表结构、阈值表、覆盖水位语义），供归档后长期引用

## 9. 归档

- [x] 9.1 确认 1–8 全部完成，`pytest -q -m "not network"` 与 `python scripts/compare_migration_baseline.py` 门禁通过（输出已留存）
- [x] 9.2 运行 `openspec archive add-top-list-sentiment`，确认 `openspec/specs/` 同步新增 `top-list-data-provider`/`top-list-analyzer`/`cli-report-toplist` 并更新 `cli-sync`/`cli-sync-market`/`dual-track-analyzer`
- [x] 9.3 合并 delta spec 到 `docs/mrd/roadmap-todo.md` 与 `docs/design/top-list-sentiment.md`，并在 `propose_list.md` D 区移除已交付项
