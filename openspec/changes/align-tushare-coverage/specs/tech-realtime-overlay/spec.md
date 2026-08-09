## MODIFIED Requirements

### Requirement: RealtimeOverlayProvider 可使用 Tushare rt_k
`RealtimeOverlayProvider` 的 failover 链 SHALL 包含已启用且实现 `fetch_realtime_quote` 的 Tushare 源。Baostock MUST NOT 作为实时报价成功源。叠加成功/失败时的 `quote_mode` 语义（`realtime` / `eod_fallback`）保持不变。

#### Scenario: Tushare rt_k 成功叠加
- **WHEN** Tushare `rt_k` 返回有效报价
- **THEN** DataFrame 末端为当日实时行，`quote_mode = "realtime"`

#### Scenario: rt_k 失败降级
- **WHEN** Tushare 实时失败且无其他实时源
- **THEN** `quote_mode = "eod_fallback"`，warnings 含原因
