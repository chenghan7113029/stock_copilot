## ADDED Requirements

### Requirement: 个股两融与主力资金流数据采集与持久化
系统 SHALL 提供 `FundFlowProvider`，封装个股两融（`margin_detail`：融资余额 `rzye`、融券余额 `rqye`、融资融券余额 `rzrqye`、融资买入额 `rzmre`、融资偿还额 `rzche`、融券余量 `rqyl`、融券卖出量 `rqmcl`）与主力资金流（`moneyflow`：净流入额 `net_mf_amount`、特大单买卖额、大单买卖额）的联网获取与持久化，遵循既有 `data_provider/` Fetcher 模式（`FetchResult`、`retry_with_backoff`）与 `ChipDistributionProvider` 的 Router 能力链 + 离线缓存降级模式。持久化 SHALL 使用两张按 `(code, trade_date)` 为主键的表（`stock_margin_detail`、`stock_moneyflow`），MUST NOT 复用 `stock_snapshots` 的 `(code, source, report_period)` 语义或市场级的 `market_sentiment_snapshot`。

#### Scenario: 联网拉取个股两融与资金流并落库
- **WHEN** 调用 `FundFlowProvider.get_latest(code, offline=False)` 且 Tushare `margin_detail`/`moneyflow` 均可用
- **THEN** SHALL 拉取该股最近交易日的两融与资金流，写入 `stock_margin_detail`、`stock_moneyflow`，并返回最新记录

#### Scenario: 单一接口失败时部分成功并降级到缓存
- **WHEN** `moneyflow` 接口调用异常，但本地已有该股两融缓存
- **THEN** SHALL 保留两融数据可用、资金流字段记为缺失（`warnings` 说明），MUST NOT 因单一接口失败导致整体失败

### Requirement: 严格离线读取个股资金面
系统 SHALL 提供 `FundFlowProvider.get_latest(code, offline=True)`，不发起任何网络请求，仅从本地 `stock_margin_detail`/`stock_moneyflow` 读取最新记录。

#### Scenario: 本地有缓存时返回最新记录
- **WHEN** 本地 `stock_margin_detail`/`stock_moneyflow` 有该股多条记录，调用 `get_latest(code, offline=True)`
- **THEN** SHALL 返回 `trade_date` 最大的记录，不触发网络

#### Scenario: 本地无缓存时返回 None 并记录原因
- **WHEN** 本地无该股任何两融/资金流记录
- **THEN** SHALL 返回 `None` 或 `(None, warnings)`，warnings 说明「无资金面缓存」，不抛异常

### Requirement: Tushare 资金面字段归一化
`FundFlowProvider` SHALL 将 Tushare 原始字段映射为内部确定性字段：融资融券余额取 `rzrqye`（或 `rzye + rqye` 之和）、主力净流入取 `net_mf_amount`（单位归一为元或万元并显式标注）、主力买卖额取大单 + 特大单买卖额。单位 MUST 在报告/字段注释中显式标明，MUST NOT 混用不同单位的列。

#### Scenario: 字段与单位归一
- **WHEN** `margin_detail` 返回 `rzye`/`rqye`/`rzrqye` 且 `moneyflow` 返回 `net_mf_amount`
- **THEN** 内部字段 SHALL 使用统一单位并保留来源字段语义，缺失字段 SHALL 记为 `None` 而非 0
