# governance-event-data-provider Specification

## Purpose
TBD - created by archiving change add-governance-flow-events. Update Purpose after archive.
## Requirements
### Requirement: 治理事件与北向资金数据采集与持久化
系统 SHALL 提供 `EventProvider`，封装治理事件接口（`stk_holdertrade` 股东增减持、`repurchase` 回购、`share_float` 解禁、`pledge_stat` 质押、`block_trade` 大宗）与市场级流动性接口（`moneyflow_hsgt` 北向资金）的联网获取与持久化，遵循既有 `data_provider/` Fetcher 模式（`FetchResult`、`retry_with_backoff`）与 `ChipDistributionProvider` 的 Router 能力链 + 离线缓存降级模式。治理事件 SHALL 使用按 `(code, 事件日期)` 分区的表（`holder_trade`/`repurchase`/`share_float`/`pledge_stat`/`block_trade`），北向资金 SHALL 使用市场级日度表（`northbound_flow`，按 `trade_date` 分区），MUST NOT 复用 `stock_snapshots` 或 `market_sentiment_snapshot`。

#### Scenario: 联网拉取治理事件并落库
- **WHEN** 调用 `EventProvider.sync(code)` 且 5 个治理接口均可用
- **THEN** SHALL 拉取该股治理事件写入对应表，并返回成功状态

#### Scenario: 单一接口失败时部分成功
- **WHEN** `block_trade` 接口异常，其余 4 个接口成功
- **THEN** SHALL 其余接口数据正常落库，`warnings` 说明大宗数据缺失，MUST NOT 因单一接口失败回滚其余接口成果

#### Scenario: 北向资金市场级拉取
- **WHEN** 调用 `EventProvider.fetch_northbound_flow()` 且 `moneyflow_hsgt` 可用
- **THEN** SHALL 写入 `northbound_flow`（市场级，无 code），北向净流入字段按 `north_money` 归一

### Requirement: 严格离线读取治理事件
系统 SHALL 提供 `EventProvider.get_latest(code, offline=True)`，不发起任何网络请求，仅从本地治理事件表读取最新事件集合；北向资金 SHALL 通过独立市场级读取方法离线读取。

#### Scenario: 本地有事件时返回最新集合
- **WHEN** 本地 `holder_trade`/`share_float` 等表有该股事件，调用 `get_latest(code, offline=True)`
- **THEN** SHALL 返回该股最近事件集合，不触发网络

#### Scenario: 本地无事件时返回空集合并记录原因
- **WHEN** 本地无该股任何治理事件
- **THEN** SHALL 返回空集合（或 `None`），`warnings` 说明「无治理事件缓存」，不抛异常

