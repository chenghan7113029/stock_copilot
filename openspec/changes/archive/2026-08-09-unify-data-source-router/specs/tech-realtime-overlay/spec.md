## MODIFIED Requirements

### Requirement: RealtimeOverlayProvider 叠加实时价格到 K 线末端
`RealtimeOverlayProvider` SHALL 由 DataFetcherRouter / 配置注入报价 fetcher 链（Failover），MUST NOT 在无参构造时默认 `AKShareFetcher()`。`overlay(df, code)` SHALL 按 priority 依次尝试 `fetch_realtime_quote`，将成功返回的当日报价注入 DataFrame 末端：若末端已存在今日日期行则替换，否则追加。返回修改后的 DataFrame 和 `quote_mode: str = "realtime"`。全部报价源失败时 SHALL 返回原始 DataFrame 和 `quote_mode = "eod_fallback"`，并将失败原因追加至 warnings。Baostock MUST NOT 作为盘中实时源（无实时能力时跳过或视为不支持）。

#### Scenario: 成功叠加当日实时价格
- **WHEN** 今日已存在历史 K 线末端行（昨日收盘）且某启用源返回有效实时报价
- **THEN** 末端行被替换为实时报价行，`quote_mode = "realtime"`

#### Scenario: 今日无历史行时追加
- **WHEN** DataFrame 末端最新日期为昨日（今日无缓存行）且实时报价成功
- **THEN** 追加一行今日实时报价，行数增加 1，`quote_mode = "realtime"`

#### Scenario: 实时报价获取失败安全降级
- **WHEN** 所有启用且支持实时报价的源均失败
- **THEN** 返回原始 DataFrame 不变，`quote_mode = "eod_fallback"`，warnings 含失败原因

#### Scenario: 非交易时段价格为零的防护
- **WHEN** 实时接口返回 `close = 0` 或 `close` 为 NaN
- **THEN** 视为无效，继续 failover 或最终降级为 `eod_fallback`

#### Scenario: 未启用 AKShare 时可用其他源
- **WHEN** 配置未启用 `akshare` 且存在其他支持 `fetch_realtime_quote` 的启用源
- **THEN** Overlay 使用该源，不构造 `AKShareFetcher`
