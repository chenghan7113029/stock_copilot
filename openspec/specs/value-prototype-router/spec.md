# value-prototype-router Specification

## Purpose
TBD - created by archiving change add-value-analyzer-core. Update Purpose after archive.
## Requirements
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
- **WHEN** stock.code 不在覆盖表，且 industry 不含「银行」，且 total_assets=None、dividend_yield=None、growth_rate=None
- **THEN** prototype="unknown"，method_keys 为通用集合（含 "graham_number"、"altman_z"、"value_trap"），且 stock.proto="unknown"

### Requirement: 银行原型分类对商业银行股票生效
`PrototypeRouter._classify(stock)` SHALL 将 `StockData.industry` 包含「银行」（包括"商业银行"、"银行"等）的股票归类为 `bank` 原型。行业判断 SHALL 优先于「关键字段全 None → unknown」的降级规则。

#### Scenario: 601398（工商银行）分类为 bank
- **WHEN** `StockData(code="601398", industry="银行")` 传入 `route()`
- **THEN** 返回的 prototype = `"bank"`，`stock.proto = "bank"`

#### Scenario: 601288 仅含行业字段时分类为 bank
- **WHEN** `StockData(code="601288", industry="商业银行")` 且无 total_assets/dividend_yield/growth_rate
- **THEN** prototype = `"bank"`

#### Scenario: 行业字段为空时不误分类为 bank
- **WHEN** `StockData.industry` 为空且 code 不在银行覆盖表
- **THEN** prototype 由其他规则（杠杆/股息率等）决定，不默认为 bank

### Requirement: 财务特征启发式路由
在硬编码覆盖表未命中时，SHALL 按以下顺序判断：
1. `stock.industry` 含「银行」 → `"bank"`
2. `total_liabilities / total_assets > 0.85` → `"bank"`
3. `dividend_yield > 4.0` 且 `growth_rate is not None` 且 `growth_rate < 10` → `"high_dividend"`
4. 有效财务数据 → `"value_growth"`（兜底）
5. 关键字段全为 None 且 industry 不含「银行」 → `"unknown"`

#### Scenario: 高杠杆特征路由为银行
- **WHEN** stock.code 不在覆盖表，total_liabilities=9e12，total_assets=10e12（杠杆率 0.9）
- **THEN** prototype="bank"

#### Scenario: 高股息低成长路由为高股息
- **WHEN** stock.code 不在覆盖表，dividend_yield=5.5，growth_rate=3.0
- **THEN** prototype="high_dividend"

#### Scenario: 普通股票兜底为价值成长
- **WHEN** stock.code 不在覆盖表，杠杆率正常（<0.85），dividend_yield=1.5，growth_rate=18.0
- **THEN** prototype="value_growth"

### Requirement: 各原型 method_keys 满足最小集合约束
每个原型 SHALL 覆盖以下最小集合：

| 原型 | 最小 method_keys |
|------|-----------------|
| bank | pb, residual_income, altman_z, value_trap |
| high_dividend | ddm, two_stage_ddm, altman_z, value_trap |
| value_growth | dcf, epv, owner_earnings, piotroski_f, beneish_m, value_trap |
| unknown | graham_number, graham_formula, epv, altman_z, value_trap |

明确排除的方法不应出现在对应原型的 method_keys 中：
- bank：不含 "dcf"、"reverse_dcf"、"peg"、"garp"、"rule_of_40"
- value_growth：不含 "ncav"

#### Scenario: 银行方法集排除 DCF
- **WHEN** prototype="bank"
- **THEN** "dcf" 不在 method_keys 中，"pb" 和 "residual_income" 在 method_keys 中

#### Scenario: 价值成长方法集排除 NCAV
- **WHEN** prototype="value_growth"
- **THEN** "ncav" 不在 method_keys 中，"dcf" 和 "piotroski_f" 在 method_keys 中

