## 1. KlineProvider 扩展：offline + persist_today

- [x] 1.1 Modify `src/data_provider/kline_provider.py`：为 `get_kline()` 添加 `offline: bool = False` 和 `persist_today: bool = False` 参数
- [x] 1.2 Modify `src/data_provider/kline_provider.py`：实现 `offline=True` 分支——仅读 `KlineRepo` 缓存，跳过 API 调用
- [x] 1.3 Modify `src/data_provider/kline_provider.py`：实现 `persist_today=True` 分支——在 `use_realtime=True` 时将当日行 upsert 写入 `KlineRepo`
- [x] 1.4 Test `test/data_provider/test_kline_provider.py`：添加 `test_offline_mode_reads_cache_only`、`test_offline_mode_empty_cache`、`test_persist_today_writes_row`

## 2. StockDataProvider 离线重建

- [x] 2.1 Modify `src/data_provider/provider.py`：添加 `get_stock_data_offline(code: str) -> StockData | None` 方法
- [x] 2.2 Modify `src/data_provider/provider.py`：提取 `_merge_fields()` 共享方法，online/offline 合并路径共用，保持字段优先级一致
- [x] 2.3 Test `test/data_provider/test_provider.py`：添加 `test_get_stock_data_offline_has_data`、`test_get_stock_data_offline_empty`

## 3. CLI Formatter

- [x] 3.1 Create `src/apps/formatters.py`：实现 `format_tech_report(result: TechAnalysisResult, as_json: bool = False) -> str`
- [x] 3.2 Create `src/apps/formatters.py`：实现 `format_value_report(result: ValueAnalysisResult, as_json: bool = False) -> str`
- [x] 3.3 Implement `src/apps/formatters.py`：自定义 `json_default` 序列化器（处理 `date`、`Enum`、`None`）
- [x] 3.4 Test `test/apps/test_formatters.py`：添加 text 与 json 输出的 smoke 测试、None 字段安全测试

## 4. CLI 入口：sync 命令

- [x] 4.1 Create `src/apps/cli.py`：使用 `argparse` 构建主程序框架，注册 `sync` 子命令
- [x] 4.2 Modify `src/apps/cli.py`：实现 `sync <code>` 主流程（价值面快照拉取 + K 线拉取写缓存）
- [x] 4.3 Modify `src/apps/cli.py`：实现 `sync --realtime` 分支，调用 `get_kline(use_realtime=True, persist_today=True)`
- [x] 4.4 Modify `src/apps/cli.py`：实现 sync 错误处理——网络失败写 stderr，退出码 1
- [x] 4.5 Test `test/apps/test_cli_sync.py`：mock 外部调用，测试正常 sync、--realtime、错误退出码

## 5. CLI 入口：report tech 命令

- [x] 5.1 Modify `src/apps/cli.py`：注册 `report tech` 子命令
- [x] 5.2 Modify `src/apps/cli.py`：实现 `report tech` 主流程——`get_kline(offline=True)` → `TechAnalyzer.analyze()` → `format_tech_report()`
- [x] 5.3 Modify `src/apps/cli.py`：检测空缓存，打印「请先运行 sync」提示，退出码 1
- [x] 5.4 Modify `src/apps/cli.py`：实现 `--json` 和 `--output <path>` 参数
- [x] 5.5 Test `test/apps/test_cli_report.py`：使用 seed DB fixture，测试正常输出、json 模式、无缓存提示

## 6. CLI 入口：report value 命令

- [x] 6.1 Modify `src/apps/cli.py`：注册 `report value` 子命令
- [x] 6.2 Modify `src/apps/cli.py`：实现 `report value` 主流程——`get_stock_data_offline()` → `ValueAnalyzer.analyze()` → `format_value_report()`
- [x] 6.3 Modify `src/apps/cli.py`：检测 offline 返回 None，打印「请先运行 sync」提示，退出码 1
- [x] 6.4 Modify `src/apps/cli.py`：实现 `--json` 和 `--output <path>` 参数
- [x] 6.5 Test `test/apps/test_cli_report.py`：mock `get_stock_data_offline`，测试正常输出、json 模式、无缓存提示

## 7. scripts/fetch_value_data.py 重构

- [x] 7.1 Modify `scripts/fetch_value_data.py`：重构为薄包装，内部委托调用 `sync` 逻辑（复用 `src/apps/cli.py` 中 sync 的核心函数）
- [x] 7.2 验证 `scripts/fetch_value_data.py` 仍可独立运行 `python scripts/fetch_value_data.py 600519`

## 8. 文档更新与归档

- [x] 8.1 Modify `docs/mrd/roadmap-todo.md`：CLI 小节补充设计决策与命令签名
- [x] 8.2 Run `py -m pytest test/apps/ -v` 验证新增测试全部通过
- [x] 8.3 Run `py -m ruff check src/apps/ src/data_provider/provider.py src/data_provider/kline_provider.py` 确认无 lint 错误
- [x] 8.4 Archive this change：将 proposal/design/specs 合并至 `docs/mrd/` 与 `docs/design/`
