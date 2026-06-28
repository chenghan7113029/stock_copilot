## ADDED Requirements

### Requirement: offline 模式（仅读缓存）
`get_kline(code, days, offline: bool = False)` 新增 `offline` 参数。当 `offline=True` 时，SHALL 仅从 `KlineRepo` 查询缓存，不调用任何外部 API 或 `RealtimeOverlayProvider`。

#### Scenario: offline=True 且缓存有数据
- **WHEN** `get_kline("600519", 90, offline=True)` 被调用且 KlineRepo 有缓存
- **THEN** 返回缓存 DataFrame，不触发任何网络调用，`quote_mode = "eod"`

#### Scenario: offline=True 且缓存为空
- **WHEN** `get_kline("600519", 90, offline=True)` 被调用且 KlineRepo 无数据
- **THEN** 返回空 DataFrame（0 行），warnings 含「无缓存数据」，`quote_mode = "eod"`
- **THEN** 不抛异常

### Requirement: persist_today 模式（sync 路径写当日行）
`get_kline()` 内部在 `use_realtime=True` 且 `persist_today=True` 时，SHALL 将最终末行（实时叠加后的当日行）写入 `KlineRepo`（upsert 语义，`trade_date = today`）。

**注**：`persist_today=False` 为默认值，保持现有行为（当日不写缓存）不变。

#### Scenario: sync --realtime 后当日行持久化
- **WHEN** `get_kline("600519", 90, use_realtime=True, persist_today=True)` 被调用
- **THEN** 当日行写入 `kline` 表（upsert）
- **THEN** 后续 `get_kline("600519", 90, offline=True)` 能读到该行

#### Scenario: persist_today=False（默认）不写当日行
- **WHEN** `get_kline("600519", 90, use_realtime=True)` 被调用（默认 persist_today=False）
- **THEN** 当日行不写入缓存，现有行为不变

## MODIFIED Requirements

### Requirement: K 线数据获取（Baostock 主，AKShare 备）
`KlineProvider` 的 `get_kline(code, days, use_realtime=False, offline=False, persist_today=False)` 方法 SHALL 优先调用 `BaostockFetcher.fetch_kline()`；若 Baostock 拉取失败，SHALL 自动 fallback 到 `AKShareFetcher.fetch_kline()`；两者均失败时 SHALL 抛出 `KlineUnavailableError`。

当 `offline=True` 时，SHALL 跳过所有外部调用，仅读缓存（见「offline 模式」需求）。

当 `use_realtime=True` 时，SHALL 在正常流程完成后调用 `RealtimeOverlayProvider.overlay()` 将实时价格叠加到 DataFrame 末端。

当 `persist_today=True` 且 `use_realtime=True` 时，SHALL 将当日行写入 `KlineRepo`（upsert）。

返回签名保持为 `(DataFrame, list[str], str)`。

#### Scenario: Baostock 正常返回（EOD 模式）
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 可用
- **THEN** 返回包含约 60 行（交易日）的 DataFrame，列完整，按日期升序排列，`quote_mode = "eod"`

#### Scenario: 实时叠加模式
- **WHEN** `get_kline("600519", days=90, use_realtime=True)` 被调用
- **THEN** 末端行为当日实时价格，`quote_mode = "realtime"` 或 `"eod_fallback"`

#### Scenario: Baostock 失败自动切换 AKShare
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 抛出异常
- **THEN** 自动调用 AKShare fetcher，返回相同格式的 DataFrame

#### Scenario: 两者均失败
- **WHEN** `get_kline("600519", days=90)` 被调用且 Baostock 与 AKShare 均失败
- **THEN** 抛出 `KlineUnavailableError`，携带失败原因信息
