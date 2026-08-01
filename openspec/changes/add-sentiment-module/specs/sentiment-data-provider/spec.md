## ADDED Requirements

### Requirement: 市场级情绪数据采集与持久化
系统 SHALL 提供 `MarketSentimentProvider`，封装市场级情绪数据（涨跌停家数、两融余额环比变化率输入分量、换手率分位输入分量）的联网获取与持久化，遵循既有 `data_provider/` Fetcher 模式（`BaseFetcher`/`FetchResult`/`retry_with_backoff`）。持久化 SHALL 使用按交易日为主键的市场级快照表（`market_sentiment_snapshot`），不得复用 `stock_snapshots` 表的 `(code, source, report_period)` 语义。

#### Scenario: 联网获取当日市场情绪快照并落库
- **WHEN** 调用 `MarketSentimentProvider.fetch_and_persist_today()`
- **THEN** SHALL 调用底层 Fetcher 获取当日涨跌停家数等字段，写入 `market_sentiment_snapshot`（若当日已存在记录则 upsert）

#### Scenario: 单一分量接口失败时不阻断整体同步
- **WHEN** 换手率分位数据源调用异常
- **THEN** SHALL 记录该字段缺失（对应列写 `NULL`），其余可用字段正常持久化，不整体失败

### Requirement: 离线读取最新市场情绪快照
系统 SHALL 提供 `MarketSentimentProvider.get_latest_offline() -> MarketSentimentSnapshot | None`，不发起任何网络请求，仅从本地数据库读取最新一条记录。

#### Scenario: 本地有历史快照时返回最新一条
- **WHEN** 本地 `market_sentiment_snapshot` 表有多条记录
- **THEN** SHALL 返回 `trade_date` 最大的一条记录

#### Scenario: 本地无记录时返回 None
- **WHEN** 本地 `market_sentiment_snapshot` 表为空
- **THEN** SHALL 返回 `None`，不抛异常
