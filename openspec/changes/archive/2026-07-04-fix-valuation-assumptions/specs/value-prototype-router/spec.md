## MODIFIED Requirements

### Requirement: 路由返回原型与 method_keys
`PrototypeRouter.route(stock: StockData) -> tuple[str, list[str]]` SHALL 返回 `(prototype, method_keys)`，其中 prototype 为 `"bank"` / `"high_dividend"` / `"value_growth"` / `"unknown"` 之一。**route() 执行后 SHALL 将 prototype 写入 stock.proto 字段。**

#### Scenario: 工行路由为银行原型
- **WHEN** stock.code="601398"（硬编码覆盖表中的工行）
- **THEN** prototype="bank"，method_keys 包含 "pb"、"residual_income"、"altman_z"，不包含 "dcf"，且 stock.proto="bank"

#### Scenario: 长江电力路由为高股息原型
- **WHEN** stock.code="600900"（硬编码覆盖表）
- **THEN** prototype="high_dividend"，method_keys 包含 "ddm"、"two_stage_ddm"，且 stock.proto="high_dividend"

#### Scenario: 茅台路由为价值成长原型
- **WHEN** stock.code="600519"（硬编码覆盖表）
- **THEN** prototype="value_growth"，method_keys 包含 "dcf"、"epv"、"owner_earnings"，且 stock.proto="value_growth"

#### Scenario: 数据不足降级为 unknown
- **WHEN** stock.code 不在覆盖表，且 total_assets=None、dividend_yield=None、growth_rate=None
- **THEN** prototype="unknown"，method_keys 为通用集合（含 "graham_number"、"altman_z"、"value_trap"），且 stock.proto="unknown"
