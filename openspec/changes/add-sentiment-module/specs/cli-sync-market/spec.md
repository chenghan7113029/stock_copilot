## ADDED Requirements

### Requirement: `sync market` 联网同步市场级情绪数据
CLI SHALL 新增 `python -m apps.cli sync market` 子命令，不接受 `<code>` 位置参数（区别于 `sync <code>`），联网调用 `MarketSentimentProvider.fetch_and_persist_today()` 并写入本地缓存。

#### Scenario: 成功同步市场情绪快照
- **WHEN** 执行 `python -m apps.cli sync market`
- **THEN** SHALL 输出同步进度与结果摘要（涨跌停家数、指数是否计算成功），并将当日快照写入 `market_sentiment_snapshot`

#### Scenario: 数据源全部失败时的错误提示
- **WHEN** 情绪面数据源接口均调用失败
- **THEN** SHALL 输出明确错误信息（区分是"接口不可用"还是"当日无数据"），不写入残缺/全 NULL 记录覆盖已有有效数据
