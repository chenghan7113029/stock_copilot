## MODIFIED Requirements

### Requirement: K 线数据获取（Baostock 主，AKShare 备）
`KlineProvider` 的 `get_kline(code, days, use_realtime=False)` 方法 SHALL 优先调用 `BaostockFetcher.fetch_kline()`；若 Baostock 拉取失败，SHALL 自动 fallback 到 `AKShareFetcher.fetch_kline()`；两者均失败时 SHALL 抛出 `KlineUnavailableError`。

当 `use_realtime=True` 时，SHALL 在正常流程完成后调用 `RealtimeOverlayProvider.overlay()` 将实时价格叠加到 DataFrame 末端。

返回的 DataFrame SHALL 包含列：`date`（str，YYYY-MM-DD）、`open`、`high`、`low`、`close`、`volume`（均为 float），按 `date` 升序排列，且为前复权数据。返回签名为 `(DataFrame, list[str], str)`，第三元素为 `quote_mode`（`"eod"` / `"realtime"` / `"eod_fallback"`）。

#### Scenario: Baostock 正常返回（EOD 模式）
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 可用
- **THEN** 返回包含约 60 行（交易日）的 DataFrame，列完整，按日期升序排列，`quote_mode = "eod"`

#### Scenario: 实时叠加模式
- **WHEN** `get_kline("600519", days=90, use_realtime=True)` 被调用
- **THEN** 末端行为当日实时价格，`quote_mode = "realtime"`；其余行为历史缓存/API 数据

#### Scenario: Baostock 失败自动切换 AKShare
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 抛出异常
- **THEN** 自动调用 AKShare fetcher，返回相同格式的 DataFrame

#### Scenario: 两者均失败
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 与 AKShare 均失败
- **THEN** 抛出 `KlineUnavailableError`，携带失败原因信息
