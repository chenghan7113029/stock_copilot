## ADDED Requirements

### Requirement: 离线价值面数据重建
`StockDataProvider` SHALL 提供 `get_stock_data_offline(code: str) -> StockData | None` 方法，从 `StockSnapshotRepo.find_by_code(code)` 读取所有来源的历史快照，合并为 `StockData` 对象，不触发任何网络请求。

合并字段优先级 SHALL 与联网路径 `_merge_result()` 保持一致（高优先级 source 的字段不被低优先级覆盖）。

#### Scenario: 有快照数据时离线重建
- **WHEN** `get_stock_data_offline("600519")` 被调用且 `StockSnapshotRepo` 有该代码的快照
- **THEN** 返回合并后的 `StockData` 对象，字段优先级与联网路径一致
- **THEN** 不调用任何外部 API

#### Scenario: 无快照数据时返回 None
- **WHEN** `get_stock_data_offline("600519")` 被调用且 `StockSnapshotRepo` 无该代码的数据
- **THEN** 返回 `None`，不抛异常

#### Scenario: 离线重建结果与联网结果字段一致性
- **WHEN** 对同一代码执行联网 `get_stock_data()` 后再执行 `get_stock_data_offline()`
- **THEN** 关键字段（eps、roe、current_price 等）的值 SHALL 一致（偏差在浮点精度内）
