## ADDED Requirements

### Requirement: StockData 携带 proto 字段
`StockData` SHALL 新增 `proto: str = ""` 字段，表示该股票被路由到的估值原型。该字段由 `PrototypeRouter.route()` 在路由后写入，默认为空字符串（表示尚未路由）。该字段为元数据字段，与 `field_sources`、`missing_fields` 同类，MUST NOT 由 LLM 生成或修改。

#### Scenario: 路由后 proto 字段有值
- **WHEN** `PrototypeRouter.route(stock)` 被调用且 stock.code="600519"
- **THEN** stock.proto SHALL 被设置为 "value_growth"

#### Scenario: 未路由时 proto 为空字符串
- **WHEN** `StockData` 被构建但尚未经过 `PrototypeRouter.route()`
- **THEN** stock.proto SHALL 为 ""（空字符串，不为 None）

#### Scenario: 下游可通过 StockDataAdapter 访问 proto
- **WHEN** `StockDataAdapter(stock)` 创建后调用 `adapter.proto`
- **THEN** 返回值与 `stock.proto` 一致（通过 `__getattr__` 透传）
