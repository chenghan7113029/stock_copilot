# tech-realtime-overlay Specification

## Purpose
实时行情叠加：通过 AKShare 拉取当日报价，注入 K 线 DataFrame 末端，使盘中分析基于最新价格；失败时安全降级为 EOD。

## Requirements

### Requirement: RealtimeQuoteFetcher 拉取当日实时报价
`AKShareFetcher.fetch_realtime_quote(code)` SHALL 调用 AKShare `stock_zh_a_spot_em` 接口，返回字典 `{"date": str, "open": float, "high": float, "low": float, "close": float, "volume": float}`，其中 `close` 为最新价（当前报价）。接口失败时 SHALL 抛出 `DataProviderError`。

#### Scenario: 正常返回实时报价
- **WHEN** 交易时段内调用 `fetch_realtime_quote("600519")`
- **THEN** 返回当日最新价格字典，`close > 0`，`date` 为今日日期字符串

#### Scenario: 非交易时段或接口不可用
- **WHEN** `stock_zh_a_spot_em` 调用失败或返回空数据
- **THEN** 抛出 `DataProviderError`，携带失败原因

---

### Requirement: RealtimeOverlayProvider 叠加实时价格到 K 线末端
`RealtimeOverlayProvider.overlay(df, code)` SHALL 将 `fetch_realtime_quote()` 返回的当日报价注入 DataFrame 末端：若末端已存在今日日期行则替换，否则追加。返回修改后的 DataFrame 和 `quote_mode: str = "realtime"`。实时报价获取失败时 SHALL 返回原始 DataFrame 和 `quote_mode = "eod_fallback"`，并将失败原因追加至 warnings。

#### Scenario: 成功叠加当日实时价格
- **WHEN** 今日已存在历史 K 线末端行（昨日收盘）
- **THEN** 末端行被替换为实时报价行，`quote_mode = "realtime"`

#### Scenario: 今日无历史行时追加
- **WHEN** DataFrame 末端最新日期为昨日（今日无缓存行）
- **THEN** 追加一行今日实时报价，行数增加 1，`quote_mode = "realtime"`

#### Scenario: 实时报价获取失败安全降级
- **WHEN** `fetch_realtime_quote()` 抛出 `DataProviderError`
- **THEN** 返回原始 DataFrame 不变，`quote_mode = "eod_fallback"`，warnings 含失败原因

#### Scenario: 非交易时段价格为零的防护
- **WHEN** 实时接口返回 `close = 0` 或 `close` 为 NaN
- **THEN** 视为无效，降级为 `eod_fallback`

---

### Requirement: KlineProvider 支持 use_realtime 参数
`KlineProvider.get_kline(code, days, use_realtime=False)` SHALL 在 `use_realtime=True` 时，于正常流程结束后调用 `RealtimeOverlayProvider.overlay()`，将叠加结果一并返回；`use_realtime=False`（默认）时行为与当前完全一致。返回签名扩展为 `(DataFrame, list[str], str)`，第三个元素为 `quote_mode`。

#### Scenario: 默认 EOD 模式向后兼容
- **WHEN** 调用 `get_kline("600519", days=90)`（不传 use_realtime）
- **THEN** 返回与现有行为完全一致，`quote_mode = "eod"`

#### Scenario: 实时模式叠加
- **WHEN** 调用 `get_kline("600519", days=90, use_realtime=True)`
- **THEN** 末端行为今日实时价格，`quote_mode = "realtime"` 或 `"eod_fallback"`

---

### Requirement: TechAnalyzer 透传 use_realtime 参数
`TechAnalyzer.analyze(code, use_realtime=False)` SHALL 将 `use_realtime` 透传至 `KlineProvider.get_kline()`，并将 `quote_mode` 赋值给 `TechAnalysisResult.quote_mode`。

#### Scenario: use_realtime=True 时结果含 quote_mode
- **WHEN** 调用 `analyze("600519", use_realtime=True)`
- **THEN** `TechAnalysisResult.quote_mode` 为 `"realtime"` 或 `"eod_fallback"`

#### Scenario: 默认 use_realtime=False
- **WHEN** 调用 `analyze("600519")` 不传参数
- **THEN** `TechAnalysisResult.quote_mode = "eod"`
