# tushare-realtime-quote Specification

## Purpose
TBD - created by archiving change align-tushare-coverage. Update Purpose after archive.
## Requirements
### Requirement: Tushare rt_k 实时报价
`TushareFetcher` SHALL 实现 `fetch_realtime_quote(code)`，调用 Tushare `rt_k`（或权限中心开通的等价盘中接口），返回含 `date,open,high,low,close,volume` 的字典，`close` 为最新价。系统 MUST NOT 使用 `daily` 历史日线接口冒充盘中实时报价。

#### Scenario: 有权限时返回实时
- **WHEN** 已开通 `rt_k` 且交易时段调用成功
- **THEN** 返回 `close > 0` 的当日报价字典

#### Scenario: 无权限明确失败
- **WHEN** Token 无 `rt_k` 权限
- **THEN** 抛出可识别的权限/能力错误，供 Failover 或 EOD 降级；不得静默改调 `daily`

### Requirement: 无 rt_k 时 sync realtime 降级
当 `sync --realtime` 路径上所有实时源失败（含未开通 `rt_k` 且无其他实时源）时，系统 SHALL 降级为 EOD（`quote_mode = eod_fallback` 或等价），并 MUST 向 CLI 进度/警告输出明确说明，不得静默当作实时成功。

#### Scenario: 降级带警告
- **WHEN** `rt_k` 不可用且无其他实时源成功
- **THEN** K 线流程不中断为硬失败（按既有 eod_fallback 行为），且用户可见警告含实时不可用原因

