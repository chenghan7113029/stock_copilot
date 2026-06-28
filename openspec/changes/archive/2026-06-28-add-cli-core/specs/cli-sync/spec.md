## ADDED Requirements

### Requirement: sync 命令基础执行
`sync <code>` 命令 SHALL 对指定股票执行以下操作（顺序）：
1. 拉取价值面快照并写入 `StockSnapshotRepo`
2. 拉取技术面 K 线（最近 90 天）并写入 `KlineRepo`

#### Scenario: 正常 sync 单票
- **WHEN** 用户执行 `python -m apps.cli sync 600519`
- **THEN** 程序联网拉取 600519 的价值面快照与 K 线，写入默认 SQLite
- **THEN** stdout 输出「[sync] 600519 完成：价值快照 ✓ | K线 90行 ✓」
- **THEN** 程序以退出码 0 结束

#### Scenario: 代码自动格式化
- **WHEN** 用户传入 `600519`（无交易所前缀）
- **THEN** 内部使用 `sh.600519` 格式作为 key

### Requirement: sync --realtime 叠加当日报价
`sync --realtime` SHALL 在 K 线拉取完成后，通过 `RealtimeOverlayProvider` 叠加当日报价，并将结果（含当日行）持久化写入 `KlineRepo`（`persist_today=True`）。

#### Scenario: 盘中 sync --realtime
- **WHEN** 用户在盘中执行 `python -m apps.cli sync 600519 --realtime`
- **THEN** 当日 K 线行（含 realtime open/high/low/close/volume）写入 `kline` 表
- **THEN** stdout 额外输出「quote_mode: realtime」

#### Scenario: realtime 拉取失败降级
- **WHEN** AKShare 实时接口超时或返回空
- **THEN** 程序以 eod 模式完成 sync（不写当日行）
- **THEN** stdout 输出降级警告「[warn] realtime overlay failed，使用 eod 数据」
- **THEN** 退出码仍为 0

### Requirement: sync 错误处理
`sync` SHALL 在网络调用失败时输出清晰错误到 stderr，退出码为 1。

#### Scenario: 网络完全不可达
- **WHEN** 执行 sync 时网络不可达
- **THEN** stderr 输出「[error] 数据拉取失败：<异常信息>」
- **THEN** 退出码为 1
