## Why

`DualTrackAnalyzer`、`TechAnalyzer`、`ValueAnalyzer` 已完整实现，但 `src/apps/` 几乎是空壳——用户无法在不写 Python 代码的情况下触发分析或更新数据。将核心能力暴露为 CLI 是让整个应用「先用起来」的最低成本路径。

## What Changes

- 新增 `src/apps/cli.py`：实现三条子命令 `sync`、`report tech`、`report value`
- 新增 `sync` 命令：单票联网拉取价值面快照 + 技术面 K 线并写入 SQLite；支持 `--realtime` 叠加当日报价（仅限 sync，report 不提供此参数）
- 新增 `report tech` 命令：**离线**读 K 线缓存 → 运行 `TechAnalyzer` → 输出人类可读文本或 JSON
- 新增 `report value` 命令：**离线**读价值面快照 → 运行 `ValueAnalyzer` → 输出人类可读文本或 JSON
- 新增 `StockDataProvider.get_stock_data_offline(code)`：从 `StockSnapshotRepo` 合并读取 `StockData`，不触发网络请求
- 修改 `KlineProvider.get_kline()`：新增 `offline=True` 模式，仅读 SQLite 缓存；修改 `sync` 路径允许持久化当日 K 线（含 realtime overlay）
- 委托 `scripts/fetch_value_data.py` 至 `sync` 逻辑（脚本保留为 CI 薄包装）

## Capabilities

### New Capabilities

- `cli-sync`：单票数据同步命令——联网拉取价值面 + 技术面 K 线并落库；`--realtime` 叠加当日报价
- `cli-report-tech`：离线技术面报告命令——读缓存 → 指标计算 → 格式化输出（text / JSON）
- `cli-report-value`：离线价值面报告命令——读快照 → 估值计算 → 格式化输出（text / JSON）
- `cli-formatter`：报告文本格式化层——`TechAnalysisResult` / `ValueAnalysisResult` → 人类可读字符串

### Modified Capabilities

- `tech-kline-provider`：`get_kline()` 新增 `offline: bool = False` 参数；`sync` 路径持久化当日 K 线（设计 D-5）
- `value-data-provider`：新增 `get_stock_data_offline(code)` 方法，从 snapshot 合并读取，不联网

## Impact

- `src/apps/cli.py`：新建，CLI 入口（`python -m apps.cli`）
- `src/data_provider/kline_provider.py`：新增 `offline` 参数 + sync 写当日行
- `src/data_provider/provider.py`：新增 `get_stock_data_offline()`
- `src/dao/stock_snapshot_repo.py`：可能补充 `merge_to_stock_data()` 辅助方法
- `scripts/fetch_value_data.py`：重构为薄包装，委托至 `sync` 逻辑
- `test/apps/test_cli.py`：新建，使用 seed DB fixture
- `docs/mrd/roadmap-todo.md`：CLI 小节补充设计决策
