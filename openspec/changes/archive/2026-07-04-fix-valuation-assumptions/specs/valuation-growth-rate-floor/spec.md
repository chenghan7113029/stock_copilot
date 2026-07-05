## ADDED Requirements

### Requirement: growth_rate_1_5 设置按原型可配的下限
`AssumptionProvider.get_growth_rate_1_5(stock)` SHALL 在返回增速前，将 `stock.growth_rate`（若存在）与 `growth_rate_floor_by_proto` 中对应原型的下限值取 max，防止周期低谷年份的 2yr CAGR 拉低 DCF 长期增速假设。若 `stock.proto` 不在 floor 配置中，则不设下限（直接用 stock.growth_rate 或 config 默认值）。

#### Scenario: 2yr CAGR 低于下限时使用下限
- **WHEN** stock.growth_rate=3.1（2025行业下行年），stock.proto="value_growth"，growth_rate_floor_by_proto.value_growth=8.0
- **THEN** get_growth_rate_1_5(stock) 返回 8.0

#### Scenario: growth_rate 正常时不受影响
- **WHEN** stock.growth_rate=15.0，stock.proto="value_growth"，growth_rate_floor_by_proto.value_growth=8.0
- **THEN** get_growth_rate_1_5(stock) 返回 15.0

#### Scenario: growth_rate 为 None 时使用配置默认值
- **WHEN** stock.growth_rate=None，stock.proto="value_growth"，config growth_rate_1_5=8.0
- **THEN** get_growth_rate_1_5(stock) 返回 8.0

#### Scenario: 未知原型不设下限
- **WHEN** stock.growth_rate=2.0，stock.proto="unknown"（不在 floor 配置中）
- **THEN** get_growth_rate_1_5(stock) 返回 2.0（不强制 floor）

### Requirement: growth_rate_floor 只作用于 1-5 年段
`get_growth_rate_6_10()` 和 `get_terminal_growth()` SHALL 不受 `growth_rate_floor_by_proto` 影响，各自使用 config 中的独立配置值。

#### Scenario: 6-10 年增速不受 floor 影响
- **WHEN** stock.growth_rate=1.0，stock.proto="value_growth"，growth_rate_floor_by_proto.value_growth=8.0
- **THEN** get_growth_rate_6_10(stock) 返回 value_analysis.growth_rate_6_10（默认 3.0），不被 floor 修改
