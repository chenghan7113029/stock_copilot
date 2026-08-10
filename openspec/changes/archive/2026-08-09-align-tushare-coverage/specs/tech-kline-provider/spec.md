## MODIFIED Requirements

### Requirement: K 线数据获取（Baostock 主，AKShare 备）
`KlineProvider` 的 `get_kline(code, days, use_realtime=False, offline=False, persist_today=False)` 方法 SHALL 通过 DataFetcherRouter / FailoverStrategy，按配置 `priority` 依次调用已启用源上可用的 `fetch_kline`（或等价），**首次成功即停止**；全部失败时 SHALL 抛出 `KlineUnavailableError`。系统 MUST NOT 无条件实例化 `BaostockFetcher()` 或硬编码「仅 Baostock→AKShare」顺序；未启用的源 MUST NOT 被调用。Failover 链 SHALL 能调用已启用的 `TushareFetcher.fetch_kline`；当更高 priority 源失败或未启用时，Tushare 成功即视为 K 线获取成功，缓存契约（列名、SQLite upsert）保持不变。

当 `offline=True` 时，SHALL 跳过所有外部调用，仅读缓存（见「offline 模式」需求）。

当 `use_realtime=True` 时，SHALL 在正常流程完成后调用经 Router 注入的 `RealtimeOverlayProvider.overlay()` 将实时价格叠加到 DataFrame 末端。

当 `persist_today=True` 且 `use_realtime=True` 时，SHALL 将当日行写入 `KlineRepo`（upsert）。

返回的 DataFrame SHALL 包含列：`date`（str，YYYY-MM-DD）、`open`、`high`、`low`、`close`、`volume`（均为 float），按 `date` 升序排列，且为前复权数据。返回签名为 `(DataFrame, list[str], str)`，第三元素为 `quote_mode`（`"eod"` / `"realtime"` / `"eod_fallback"`）。实现 SHOULD 在日志或进度回调中暴露实际 `kline_source`。

#### Scenario: 最高 priority 源正常返回（EOD 模式）
- **WHEN** `get_kline("600519", days=90)` 被调用且最高 priority 且支持 K 线的源可用
- **THEN** 返回包含约 60 行（交易日）的 DataFrame，列完整，按日期升序排列，`quote_mode = "eod"`

#### Scenario: 实时叠加模式
- **WHEN** `get_kline("600519", days=90, use_realtime=True)` 被调用
- **THEN** 末端行为当日实时价格，`quote_mode = "realtime"` 或 `"eod_fallback"`

#### Scenario: 高优先级失败自动切换下一源
- **WHEN** `get_kline("600519", days=90)` 被调用且最高 priority 源抛出异常、下一启用源成功
- **THEN** 返回相同格式的 DataFrame，且不调用未启用源

#### Scenario: Tushare 作为 failover 成功
- **WHEN** Baostock K 线失败且 Tushare 启用并成功
- **THEN** 返回合法 OHLCV DataFrame，`offline=False` 路径可写入缓存

#### Scenario: 全部启用源均失败
- **WHEN** `get_kline("600519", days=90)` 被调用且所有启用且支持 K 线的源均失败
- **THEN** 抛出 `KlineUnavailableError`，携带失败原因信息

#### Scenario: 未启用 AKShare 时不调用
- **WHEN** 配置未启用 `akshare` 且 Baostock（或其他启用源）成功
- **THEN** 不实例化、不调用 `AKShareFetcher`

#### Scenario: offline 仍不联网
- **WHEN** `offline=True`
- **THEN** 不调用 Tushare 或任何外部源，仅读 `KlineRepo`
