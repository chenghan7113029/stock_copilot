# tushare-kline Specification

## Purpose
TBD - created by archiving change align-tushare-coverage. Update Purpose after archive.
## Requirements
### Requirement: Tushare 前复权日 K 线
`TushareFetcher` SHALL 实现 `fetch_kline(code, start_date, end_date)`（或与 Router 约定的等价签名），调用 Tushare `pro_bar`（`adj='qfq'`）或文档批准的等价日线接口，返回列名为 `date,open,high,low,close,volume` 且按 `date` 升序的 DataFrame。接口失败时 SHALL 抛出 `DataProviderError`，供 FailoverStrategy 继续下一源。

#### Scenario: 正常拉取
- **WHEN** Token 有效且调用 `fetch_kline` 请求 600519 近 90 日
- **THEN** 返回非空 DataFrame，列完整，`close > 0`

#### Scenario: 接口失败
- **WHEN** Tushare API 抛错或返回空
- **THEN** 抛出 `DataProviderError`，不返回残缺成功结果冒充完整 K 线

### Requirement: Baostock 失败时 Tushare 可独立完成 K 线缓存
当配置启用 `tushare` 且 Baostock K 线不可用时，`KlineProvider.get_kline`（非 offline）SHALL 能通过 Tushare 成功拉取并写入 `KlineRepo`（满足 Issue #1）。

#### Scenario: 仅 Tushare 可用
- **WHEN** 配置启用 tushare，Baostock `fetch_kline` 失败，Tushare 成功
- **THEN** `get_kline` 返回非空 DataFrame 且历史行可被 upsert 到缓存

