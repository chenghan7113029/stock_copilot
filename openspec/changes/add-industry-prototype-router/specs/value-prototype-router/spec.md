## MODIFIED Requirements

### Requirement: 银行原型分类对商业银行股票生效

`PrototypeRouter._classify(stock)` SHALL 将 `StockData.industry` 命中 `_INDUSTRY_PROTOTYPE_MAP["bank"]` 子串（包括"银行"、"商业银行"等变体）的股票归类为 `bank` 原型。行业映射判断 SHALL 优先于财务特征启发式（杠杆率等）与"关键字段全 None → unknown"的降级规则。

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

在硬编码覆盖表与行业映射均未命中时，SHALL 按以下顺序判断：
1. `total_liabilities / total_assets > 0.85` → `"bank"`
2. `dividend_yield > 4.0` 且 `growth_rate is not None` 且 `growth_rate < 10` → `"high_dividend"`
3. 有效财务数据 → `"value_growth"`（兜底）
4. 关键字段全为 None 且行业映射未命中 → `"unknown"`

**前置条件变更**：本需求仅在 `_classify_by_industry(stock.industry)` 返回 `None`（即行业字段为空，或行业名称既不在 `_INDUSTRY_PROTOTYPE_MAP` 也不在 `_INDUSTRY_V2_UNIMPLEMENTED` 中）时才被触发；若行业映射已给出判定结果（无论是已实现原型还是显式 `unknown`），本需求描述的启发式判断 SHALL 被跳过。

#### Scenario: 高杠杆特征路由为银行（行业字段为空）

- **WHEN** stock.code 不在覆盖表，`industry=""`，total_liabilities=9e12，total_assets=10e12（杠杆率 0.9）
- **THEN** prototype="bank"

#### Scenario: 高股息低成长路由为高股息（行业字段为空）

- **WHEN** stock.code 不在覆盖表，`industry=""`，dividend_yield=5.5，growth_rate=3.0
- **THEN** prototype="high_dividend"

#### Scenario: 普通股票兜底为价值成长

- **WHEN** stock.code 不在覆盖表，`industry=""`，杠杆率正常（<0.85），dividend_yield=1.5，growth_rate=18.0
- **THEN** prototype="value_growth"

#### Scenario: 高杠杆但行业为保险时不再触发银行启发式

- **WHEN** stock.code 不在覆盖表，`industry="保险"`，total_liabilities=9e12，total_assets=10e12（杠杆率 0.9，若无行业拦截会被判定为 bank）
- **THEN** 行业映射先命中 `_INDUSTRY_V2_UNIMPLEMENTED`，返回 `"unknown"`，财务启发式 SHALL 不被执行，prototype = `"unknown"`（而不是 `"bank"`）

## ADDED Requirements

### Requirement: 行业映射优先于财务启发式（新增判定层）

`PrototypeRouter._classify_by_industry(industry: str) -> str | None` SHALL 实现以下三分支判定，作为 `_classify()` 中「硬编码覆盖表」之后、「财务特征启发式」之前的判定层：

1. `industry` 为空字符串 → 返回 `None`
2. `industry` 命中 `_INDUSTRY_PROTOTYPE_MAP`（子串匹配）→ 返回对应已实现 prototype（`"bank"` 或 `"high_dividend"`）
3. `industry` 命中 `_INDUSTRY_V2_UNIMPLEMENTED`（子串匹配，如"保险"、"国防军工"、"军工"）→ 返回 `"unknown"`
4. 均未命中 → 返回 `None`

`_classify()` SHALL 在 `_classify_by_industry()` 返回非 `None` 时直接采用该结果，不再执行后续财务启发式步骤。

#### Scenario: 高股息行业直接命中，不依赖启发式阈值

- **WHEN** `StockData(code="600900", industry="电力")`，且股息率/成长率数据缺失（`dividend_yield=None`, `growth_rate=None`）
- **THEN** `_classify_by_industry("电力")` 返回 `"high_dividend"`，最终 prototype = `"high_dividend"`（即使按原有启发式因字段缺失会走向别的分支）

#### Scenario: 已识别 V2 行业短路到 unknown，不进入启发式

- **WHEN** `StockData(code="601318", industry="保险", total_liabilities=9e12, total_assets=10e12)`
- **THEN** `_classify_by_industry("保险")` 返回 `"unknown"`，最终 prototype = `"unknown"`，且高杠杆特征启发式（第 4 步）SHALL 不被执行

#### Scenario: 行业名称未收录时返回 None，交由启发式处理

- **WHEN** `industry="某未收录的新兴行业名称"`
- **THEN** `_classify_by_industry()` 返回 `None`，`_classify()` 继续执行原有财务启发式步骤，行为与本 change 之前一致
