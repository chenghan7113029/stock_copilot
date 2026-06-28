## ADDED Requirements

### Requirement: net_debt 从资产负债表计算
`TushareFetcher` SHALL 在 `fetch_fundamentals` 完成后，基于 `short_term_debt + long_term_debt - cash` 推导 `net_debt`，负值代表净现金状态（如茅台），直接参与 EV/EBITDA 和 DCF 企业价值桥梁计算。

#### Scenario: 三项数据均可获取
- **WHEN** `short_term_debt`、`long_term_debt`、`cash` 均在 FetchResult.data 中
- **THEN** `net_debt = short_term_debt + long_term_debt - cash`，写入 `data["net_debt"]`

#### Scenario: 净现金状态（net_debt < 0）
- **WHEN** 计算结果 `net_debt < 0`（如茅台：cash ≈ 1,800 亿，financial_debt ≈ 0）
- **THEN** net_debt 保持负值（不 clamp 为 0），EV/EBITDA 和 DCF 可用此值提高股权价值

#### Scenario: cash 字段缺失
- **WHEN** `cash`（money_cap）未取到
- **THEN** net_debt 不写入，沿用 `StockData.net_debt` 默认值（`None` 或 0），EV/EBITDA 回退到无净债调整版本

#### Scenario: Tushare net_debt 覆盖 Baostock 估算值
- **WHEN** Baostock 数据合并后 `net_debt = 0`（默认），而 Tushare 提供了有效 `net_debt`
- **THEN** Tushare 的 `net_debt` SHALL 覆盖 Baostock 的默认值
