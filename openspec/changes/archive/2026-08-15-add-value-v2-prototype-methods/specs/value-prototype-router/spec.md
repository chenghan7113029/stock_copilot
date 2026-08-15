## ADDED Requirements

### Requirement: Router 支持 V2 原型键增量注册

`PrototypeRouter` SHALL 允许注册并路由下列 V2 prototype 键（随 Phase 增量启用，未启用前不得把样本静默当成已实现）：`growth_manufacturing`、`cashflow_ad_cycle`、`defense_orders`、`insurance`、`growth_tech`（名称以实现为准，但 MUST 稳定写入 `_PROTOTYPE_METHODS`）。

每个已启用键 SHALL 有非空 `method_keys` 最小集；code 白名单或行业映射 SHALL 优先于错误的 V1 启发（例如比亚迪不得在 P1 启用后仍静默 `value_growth`）。

#### Scenario: P1 启用后比亚迪不再 value_growth

- **WHEN** `growth_manufacturing` 已启用且 code=`002594`
- **THEN** route 结果 prototype 为该键（除非人工 override）

#### Scenario: 未启用的 V2 键不出现在 route 成功路径

- **WHEN** 某 V2 键尚未在本 Phase 启用
- **THEN** 对应样本保持诚实 unknown/降级路径，不返回该键
