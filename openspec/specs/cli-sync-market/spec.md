# cli-sync-market Specification

## Purpose
TBD - created by archiving change add-sentiment-module. Update Purpose after archive.
## Requirements
### Requirement: `sync market` 联网同步市场级情绪数据
CLI SHALL 新增 `python -m apps.cli sync market` 子命令，不接受 `<code>` 位置参数（区别于 `sync <code>`），联网调用 `MarketSentimentProvider.fetch_and_persist_today()` 并写入本地缓存。

#### Scenario: 成功同步市场情绪快照
- **WHEN** 执行 `python -m apps.cli sync market`
- **THEN** SHALL 输出同步进度与结果摘要（涨跌停家数、指数是否计算成功），并将当日快照写入 `market_sentiment_snapshot`

#### Scenario: 数据源全部失败时的错误提示
- **WHEN** 情绪面数据源接口均调用失败
- **THEN** SHALL 输出明确错误信息（区分是"接口不可用"还是"当日无数据"），不写入残缺/全 NULL 记录覆盖已有有效数据

### Requirement: sync market 回填龙虎榜交易日数据
`sync market` SHALL 在完成市场情绪快照与北向资金同步之后，追加回填最近 `N` 个交易日的龙虎榜数据（`N` 默认 20，可通过 `--top-list-days` 调整）。回填 SHALL 逐交易日调用 `top_list`（并尽力调用 `top_inst`），已在水位表中的交易日 SHALL 跳过。单日失败 SHALL 记 warning 并继续其余交易日，MUST NOT 使整次 `sync market` 失败。

#### Scenario: 首次回填建立覆盖
- **WHEN** 本地无龙虎榜数据，执行 `sync market`（默认 20 日）
- **THEN** SHALL 回填最近 20 个交易日中可获取的榜单数据，`top_list_sync_marker` 相应写入，输出回填天数摘要

#### Scenario: 增量执行只补新增交易日
- **WHEN** 本地已覆盖最近 19 个交易日，执行 `sync market`
- **THEN** SHALL 只对未覆盖的 1 个交易日发起调用，其余跳过

#### Scenario: 自定义回填窗口
- **WHEN** 执行 `sync market --top-list-days 60`
- **THEN** SHALL 按 60 个交易日窗口回填，`N <= 0` 时 SHALL 跳过龙虎榜步骤并给出提示

#### Scenario: 单日失败不影响整体
- **WHEN** 回填过程中某交易日 `top_list` 抛异常
- **THEN** SHALL 输出该日失败 warning 并继续后续交易日，市场情绪快照与北向资金结果不受影响

