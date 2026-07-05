## MODIFIED Requirements

### Requirement: 银行原型分类对商业银行股票生效
`PrototypeRouter._classify(stock)` SHALL 将 `StockData.industry` 包含「银行」（包括"商业银行"、"银行"等）的股票归类为 `bank` 原型。

#### Scenario: 601398（工商银行）分类为 bank
- **WHEN** `StockData(code="601398", industry="银行")` 传入 `route()`
- **THEN** 返回的 prototype = `"bank"`，`stock.proto = "bank"`

#### Scenario: 行业字段为空时不误分类为 bank
- **WHEN** `StockData.industry = None`
- **THEN** prototype 由其他规则（如 ROE/股息率）决定，不默认为 bank
