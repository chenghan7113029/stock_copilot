## ADDED Requirements

### Requirement: EPV 零增长盈利力价值估算
系统 SHALL 实现 `EPV`（Earnings Power Value）估值方法，
代表"假设公司无增长、仅维持当前盈利能力"的保守内在价值基准。

核心公式：
```
调整后 EBIT = Revenue × operating_margin / 100
税后调整盈利 = 调整后 EBIT × (1 - tax_rate / 100)
维护性 CapEx = Revenue × maintenance_capex_pct（默认 3%）
正常化盈利 = 税后调整盈利 - 维护性 CapEx
EPV_公司 = 正常化盈利 / discount_rate
EPV_每股 = (EPV_公司 - net_debt) / shares_outstanding
```

维护性 CapEx 比例（`maintenance_capex_pct`）、折现率（`discount_rate`）均可通过 `__init__` 覆盖；
`operating_margin` 为 None 且 `ebit` 和 `revenue` 均有值时，SHALL 从 `ebit/revenue × 100` 推导；
`operating_margin` 为 None 且上述条件不满足时，返回 `missing_fields = ["operating_margin"]`。

#### Scenario: 正常 EPV 计算
- **WHEN** `StockData.revenue = 100e9`, `operating_margin = 35.0`, `tax_rate = 25.0`,
  `net_debt = 0`, `shares_outstanding = 1.26e9`, `current_price = 1800.0`，discount_rate=10%, capex_pct=3%
- **THEN** `调整后EBIT = 35e9`，`税后 = 26.25e9`，`维护capex = 3e9`，
  `正常化盈利 = 23.25e9`，`EPV公司 = 232.5e9`，`EPV每股 ≈ 184.52`，
  与 ref/valueinvest.EPV 同输入偏差 ≤ ±0.1%

#### Scenario: operating_margin 为 None 但可从 ebit/revenue 推导
- **WHEN** `StockData.operating_margin = None`, `ebit = 35e9`, `revenue = 100e9`
- **THEN** 推导 `operating_margin = 35.0`，计算正常进行，`warnings` 含推导说明

#### Scenario: 所有盈利字段缺失时 missing_fields
- **WHEN** `StockData.operating_margin = None`, `ebit = None`, `revenue = None`
- **THEN** `missing_fields` 含 `"operating_margin"`，`error` 非空，不抛异常

#### Scenario: net_debt 为正时从 EPV 公司价值中扣除
- **WHEN** `net_debt = 20e9`, `EPV_公司 = 100e9`, `shares = 1e9`
- **THEN** `EPV_每股 = (100e9 - 20e9) / 1e9 = 80.0`

#### Scenario: EPV 每股为负时标记局限性
- **WHEN** 扣除 `net_debt` 后 `EPV_公司 - net_debt < 0`
- **THEN** `applicability = "Limited"`，`fair_value < 0`，`analysis` 含负债超过盈利力的说明，不抛异常
