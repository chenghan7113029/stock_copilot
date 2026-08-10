## MODIFIED Requirements

### Requirement: 路由返回原型与 method_keys

`PrototypeRouter.route(stock: StockData, override: str | None = None) -> tuple[str, list[str]]` SHALL 返回 `(prototype, method_keys)`，其中 prototype 为 `"bank"` / `"high_dividend"` / `"value_growth"` / `"unknown"` 之一。**route() 执行后 SHALL 将 prototype 写入 stock.proto 字段。**

**新增前置规则（最高优先级）**：若 `override` 参数非 `None` 且是 `_PROTOTYPE_METHODS` 的合法键，SHALL 直接返回 `(override, list(_PROTOTYPE_METHODS[override]))`，`stock.proto = override`，且**不执行**内部 `_classify()` 判定（硬编码覆盖表、行业映射、财务启发式均被跳过）。若 `override` 非法（不在 `_PROTOTYPE_METHODS` 键集合中），SHALL 忽略该参数并回退到正常 `_classify()` 判定流程，不抛异常。

#### Scenario: 工行路由为银行原型（无覆盖）

- **WHEN** stock.code="601398"（硬编码覆盖表中的工行），`override=None`
- **THEN** prototype="bank"，method_keys 包含 "pb"、"residual_income"、"altman_z"，不包含 "dcf"，且 stock.proto="bank"

#### Scenario: 长江电力路由为高股息原型（无覆盖）

- **WHEN** stock.code="600900"（硬编码覆盖表），`override=None`
- **THEN** prototype="high_dividend"，method_keys 包含 "ddm"、"two_stage_ddm"，且 stock.proto="high_dividend"

#### Scenario: 茅台路由为价值成长原型（无覆盖）

- **WHEN** stock.code="600519"（硬编码覆盖表），`override=None`
- **THEN** prototype="value_growth"，method_keys 包含 "dcf"、"epv"、"owner_earnings"，且 stock.proto="value_growth"

#### Scenario: 数据不足降级为 unknown（无覆盖）

- **WHEN** stock.code 不在覆盖表，且 industry 不含「银行」，且 total_assets=None、dividend_yield=None、growth_rate=None，`override=None`
- **THEN** prototype="unknown"，method_keys 为通用集合（含 "graham_number"、"altman_z"、"value_trap"），且 stock.proto="unknown"

#### Scenario: 人工覆盖优先于硬编码覆盖表

- **WHEN** stock.code="601398"（硬编码覆盖表判定为 "bank"），但 `override="high_dividend"`
- **THEN** 返回 prototype="high_dividend"（覆盖生效，忽略硬编码表判定），`stock.proto="high_dividend"`，`_classify()` 内部逻辑不被执行

#### Scenario: 非法覆盖值被忽略，回退正常判定

- **WHEN** stock.code="601398"，`override="not_a_real_prototype"`（不在 `_PROTOTYPE_METHODS` 键集合中）
- **THEN** 忽略 `override`，按 `_classify()` 正常判定返回 prototype="bank"（硬编码覆盖表命中），不抛异常
