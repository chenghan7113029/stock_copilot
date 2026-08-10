## ADDED Requirements

### Requirement: sync market 基于已配置数据源
`sync market`（及写入市场情绪快照的等价 CLI）SHALL 根据 DataFetcherRouter 判断是否存在至少一个可用的情绪数据源；当 AKShare 未启用但 Tushare（或其他支持源）可用时，SHALL 允许执行。系统 MUST NOT 仅因 `akshare` 未启用而 exit 1。若无任何情绪源可用，SHALL 以明确错误退出并提示配置数据源。

#### Scenario: 仅 tushare 可 sync market
- **WHEN** 配置启用 tushare、未启用 akshare，且 Tushare 情绪路径可用
- **THEN** `sync market` 不因缺少 akshare 失败

#### Scenario: 无任何情绪源
- **WHEN** 所有情绪相关源均未启用或不可用
- **THEN** 命令失败并提示需配置可用数据源（文案不限定为「必须启用 AKShare」）

## MODIFIED Requirements

### Requirement: sync --realtime 叠加当日报价
`sync --realtime` SHALL 在 K 线拉取完成后，通过经 Router 注入的 `RealtimeOverlayProvider` 叠加当日报价，并将结果（含当日行）持久化写入 `KlineRepo`（`persist_today=True`）。实时源按配置 failover（如 Tushare `rt_k`）；MUST NOT 假定唯一依赖 AKShare。

#### Scenario: 盘中 sync --realtime
- **WHEN** 用户在盘中执行 `python -m apps.cli sync 600519 --realtime` 且某启用实时源成功
- **THEN** 当日 K 线行（含 realtime open/high/low/close/volume）写入 `kline` 表
- **THEN** stdout 额外输出「quote_mode: realtime」

#### Scenario: realtime 拉取失败降级
- **WHEN** 所有启用实时源超时或返回空
- **THEN** 程序以 eod 模式完成 sync（不写当日行或按既有 eod_fallback 行为）
- **THEN** stdout 输出降级警告（标明实时不可用，不限定文案必须含 AKShare）
- **THEN** 退出码仍为 0
