## MODIFIED Requirements

### Requirement: K 线数据获取（配置化 Failover）
在阶段 A Router 语义基础上，`KlineProvider.get_kline`（非 offline）的 Failover 链 SHALL 能调用已启用的 `TushareFetcher.fetch_kline`。当更高 priority 源失败或未启用时，Tushare 成功即视为 K 线获取成功，缓存契约（列名、SQLite upsert）保持不变。

#### Scenario: Tushare 作为 failover 成功
- **WHEN** Baostock K 线失败且 Tushare 启用并成功
- **THEN** 返回合法 OHLCV DataFrame，`offline=False` 路径可写入缓存

#### Scenario: offline 仍不联网
- **WHEN** `offline=True`
- **THEN** 不调用 Tushare 或任何外部源，仅读 `KlineRepo`
