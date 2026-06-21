## ADDED Requirements

### Requirement: 路由返回原型与 method_keys
`PrototypeRouter.route(stock: StockData) -> tuple[str, list[str]]` SHALL 返回 `(prototype, method_keys)`，其中 prototype 为 `"bank"` / `"high_dividend"` / `"value_growth"` / `"unknown"` 之一。

#### Scenario: 工行路由为银行原型
- **WHEN** stock.code="601398"（硬编码覆盖表中的工行）
- **THEN** prototype="bank"，method_keys 包含 "pb"、"residual_income"、"altman_z"，不包含 "dcf"

#### Scenario: 长江电力路由为高股息原型
- **WHEN** stock.code="600900"（硬编码覆盖表）
- **THEN** prototype="high_dividend"，method_keys 包含 "ddm"、"two_stage_ddm"

#### Scenario: 茅台路由为价值成长原型
- **WHEN** stock.code="600519"（硬编码覆盖表）
- **THEN** prototype="value_growth"，method_keys 包含 "dcf"、"epv"、"owner_earnings"

#### Scenario: 数据不足降级为 unknown
- **WHEN** stock.code 不在覆盖表，且 total_assets=None、dividend_yield=None、growth_rate=None
- **THEN** prototype="unknown"，method_keys 为通用集合（含 "graham_number"、"altman_z"、"value_trap"）

### Requirement: 财务特征启发式路由
在硬编码覆盖表未命中时，SHALL 按以下顺序判断：
1. `total_liabilities / total_assets > 0.85` → `"bank"`
2. `dividend_yield > 4.0` 且 `growth_rate is not None` 且 `growth_rate < 10` → `"high_dividend"`
3. 有效财务数据 → `"value_growth"`（兜底）
4. 关键字段全为 None → `"unknown"`

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
